from __future__ import annotations

import ipaddress
import socket
import threading
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool


AddressResolver = Callable[[str, int], Iterable[str]]


class UnsafeNetworkTarget(requests.RequestException):
    """
    Raised before any socket connection when a crawler target is not public.

    Keeping this inside the requests exception hierarchy lets the existing
    crawler/robots/sitemap/feed error handling fail closed without exposing
    transport internals to callers.
    """

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Unsafe network target ({reason}): {url}")


@dataclass(frozen=True)
class ResolvedNetworkTarget:
    scheme: str
    hostname: str
    port: int
    host_header: str
    connect_ip: str
    resolved_ips: tuple[str, ...]


def _default_resolver(hostname: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(
        hostname,
        port,
        type=socket.SOCK_STREAM,
    )

    result: list[str] = []
    seen: set[str] = set()

    for family, _socktype, _proto, _canonname, sockaddr in infos:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue

        raw = str(sockaddr[0]).split("%", 1)[0]
        if raw in seen:
            continue

        seen.add(raw)
        result.append(raw)

    return result


def _validated_public_ip(
    raw: str,
    *,
    url: str,
    reason: str,
) -> str:
    try:
        address = ipaddress.ip_address(raw)
    except ValueError as exc:
        raise UnsafeNetworkTarget(url, f"{reason}:invalid_ip") from exc

    # is_global is deliberately stricter than checking only RFC1918 ranges:
    # it also excludes loopback, link-local, CGNAT/shared, documentation,
    # multicast, reserved and unspecified IPv4/IPv6 space.
    if not address.is_global:
        raise UnsafeNetworkTarget(url, reason)

    return address.compressed


def resolve_network_target(
    url: str,
    *,
    resolver: AddressResolver = _default_resolver,
) -> ResolvedNetworkTarget:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme not in {"http", "https"}:
        raise UnsafeNetworkTarget(url, "unsupported_scheme")

    if parsed.username is not None or parsed.password is not None:
        raise UnsafeNetworkTarget(url, "credentials_in_url")

    hostname = (parsed.hostname or "").strip().rstrip(".").lower()

    if not hostname:
        raise UnsafeNetworkTarget(url, "missing_host")

    if (
        hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
    ):
        raise UnsafeNetworkTarget(url, "local_host")

    if "%" in hostname:
        # Scoped IPv6 zone identifiers are local-interface routing hints and
        # must never be accepted from untrusted crawler input.
        raise UnsafeNetworkTarget(url, "scoped_ip")

    try:
        explicit_port = parsed.port
    except ValueError as exc:
        raise UnsafeNetworkTarget(url, "invalid_port") from exc

    default_port = 443 if scheme == "https" else 80
    port = explicit_port or default_port

    literal_ip: str | None = None
    try:
        literal_ip = ipaddress.ip_address(hostname).compressed
    except ValueError:
        pass

    if literal_ip is not None:
        resolved_ips = (
            _validated_public_ip(
                literal_ip,
                url=url,
                reason="non_public_ip",
            ),
        )
    else:
        try:
            raw_addresses = list(resolver(hostname, port))
        except UnsafeNetworkTarget:
            raise
        except (OSError, socket.gaierror) as exc:
            raise requests.ConnectionError(
                f"DNS resolution failed for {hostname}"
            ) from exc

        if not raw_addresses:
            raise requests.ConnectionError(
                f"DNS resolution returned no addresses for {hostname}"
            )

        normalized: list[str] = []
        seen: set[str] = set()

        for raw in raw_addresses:
            address = _validated_public_ip(
                str(raw).split("%", 1)[0],
                url=url,
                reason="non_public_dns_address",
            )
            if address in seen:
                continue
            seen.add(address)
            normalized.append(address)

        if not normalized:
            raise requests.ConnectionError(
                f"DNS resolution returned no usable addresses for {hostname}"
            )

        resolved_ips = tuple(normalized)

    host_display = hostname
    try:
        if ipaddress.ip_address(hostname).version == 6:
            host_display = f"[{hostname}]"
    except ValueError:
        pass

    host_header = host_display
    if explicit_port is not None and explicit_port != default_port:
        host_header = f"{host_display}:{port}"

    return ResolvedNetworkTarget(
        scheme=scheme,
        hostname=hostname,
        port=port,
        host_header=host_header,
        connect_ip=resolved_ips[0],
        resolved_ips=resolved_ips,
    )


class SafeHTTPAdapter(HTTPAdapter):
    """
    requests adapter that resolves, validates and pins each connection.

    The hostname is resolved immediately before each request. Every returned
    address must be globally routable. The TCP connection is then opened to a
    validated IP directly, so requests/urllib3 cannot perform a second DNS
    lookup between validation and connect (DNS-rebinding/TOCTOU protection).

    Redirects remain handled by requests.Session; each redirected PreparedRequest
    goes through this adapter again and is independently resolved/validated
    before a socket is opened.
    """

    def __init__(
        self,
        *,
        resolver: AddressResolver = _default_resolver,
        **kwargs,
    ):
        self.resolver = resolver
        self._target_local = threading.local()
        self._safe_pools: dict[
            tuple[str, str, int, str],
            HTTPConnectionPool | HTTPSConnectionPool,
        ] = {}
        self._safe_pools_lock = threading.Lock()
        super().__init__(**kwargs)

    def send(
        self,
        request,
        stream=False,
        timeout=None,
        verify=True,
        cert=None,
        proxies=None,
    ):
        target = resolve_network_target(
            request.url,
            resolver=self.resolver,
        )

        request.headers["Host"] = target.host_header
        self._target_local.value = target

        try:
            # Crawler traffic is intentionally direct. Environment or caller
            # proxy settings must not create an unvalidated alternate network
            # path around IP pinning.
            return super().send(
                request,
                stream=stream,
                timeout=timeout,
                verify=verify,
                cert=cert,
                proxies={},
            )
        finally:
            self._target_local.value = None

    def _current_target(self) -> ResolvedNetworkTarget:
        target = getattr(self._target_local, "value", None)
        if target is None:
            raise requests.ConnectionError(
                "SafeHTTPAdapter target context is missing."
            )
        return target

    def _connection_for_target(
        self,
        target: ResolvedNetworkTarget,
    ) -> HTTPConnectionPool | HTTPSConnectionPool:
        key = (
            target.scheme,
            target.connect_ip,
            target.port,
            target.hostname,
        )

        with self._safe_pools_lock:
            pool = self._safe_pools.get(key)
            if pool is not None:
                return pool

            common = {
                "host": target.connect_ip,
                "port": target.port,
                "maxsize": self._pool_maxsize,
                "block": self._pool_block,
            }

            if target.scheme == "https":
                pool = HTTPSConnectionPool(
                    **common,
                    assert_hostname=target.hostname,
                    server_hostname=target.hostname,
                )
            else:
                pool = HTTPConnectionPool(**common)

            self._safe_pools[key] = pool
            return pool

    # requests >= 2.32
    def get_connection_with_tls_context(
        self,
        request,
        verify,
        proxies=None,
        cert=None,
    ):
        return self._connection_for_target(
            self._current_target()
        )

    # requests 2.31 compatibility
    def get_connection(self, url, proxies=None):
        return self._connection_for_target(
            self._current_target()
        )

    def close(self) -> None:
        with self._safe_pools_lock:
            pools = list(self._safe_pools.values())
            self._safe_pools.clear()

        for pool in pools:
            try:
                pool.close()
            except Exception:
                pass

        super().close()


class SafeSession(requests.Session):
    """
    requests-compatible crawler session with fail-closed network routing.
    """

    def __init__(
        self,
        *,
        resolver: AddressResolver = _default_resolver,
    ):
        super().__init__()

        # Never inherit HTTP(S)_PROXY / ALL_PROXY from the process.
        self.trust_env = False

        self.mount(
            "http://",
            SafeHTTPAdapter(resolver=resolver),
        )
        self.mount(
            "https://",
            SafeHTTPAdapter(resolver=resolver),
        )
