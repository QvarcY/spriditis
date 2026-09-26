from __future__ import annotations

import ipaddress
import sys
from pathlib import Path as _BootstrapPath

import requests

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.crawler.safe_http import (
    SafeHTTPAdapter,
    SafeSession,
    UnsafeNetworkTarget,
    resolve_network_target,
)


PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:4700:4700::1111"


def expect_unsafe(url, reason, resolver=lambda host, port: [PUBLIC_V4]):
    try:
        resolve_network_target(
            url,
            resolver=resolver,
        )
    except UnsafeNetworkTarget as exc:
        assert exc.reason == reason, (exc.reason, reason)
    else:
        raise AssertionError(
            f"{url} should be rejected as {reason}"
        )


# Public DNS answers are accepted and the chosen TCP destination is pinned
# to one of the exact addresses returned by the resolver.
target = resolve_network_target(
    "https://public.example/catalog",
    resolver=lambda host, port: [
        PUBLIC_V4,
        PUBLIC_V6,
        PUBLIC_V4,
    ],
)

assert target.scheme == "https"
assert target.hostname == "public.example"
assert target.port == 443
assert target.connect_ip == PUBLIC_V4
assert target.resolved_ips == (
    PUBLIC_V4,
    ipaddress.ip_address(PUBLIC_V6).compressed,
)
assert target.host_header == "public.example"


# Explicit public non-default ports remain represented in Host.
port_target = resolve_network_target(
    "http://public.example:8080/path",
    resolver=lambda host, port: [PUBLIC_V4],
)
assert port_target.port == 8080
assert port_target.host_header == "public.example:8080"


# Literal and named private targets fail before any connection.
expect_unsafe(
    "http://127.0.0.1/private",
    "non_public_ip",
)
expect_unsafe(
    "http://10.0.0.7/private",
    "non_public_ip",
)
expect_unsafe(
    "http://169.254.169.254/latest/meta-data/",
    "non_public_ip",
)
expect_unsafe(
    "http://[::1]/private",
    "non_public_ip",
)
expect_unsafe(
    "http://[fe80::1]/private",
    "non_public_ip",
)
expect_unsafe(
    "http://localhost/private",
    "local_host",
)
expect_unsafe(
    "http://printer.local/private",
    "local_host",
)


# A hostname is rejected if even one DNS answer is not globally routable.
# This avoids "pick the safe address, keep a private alternate" bypasses.
expect_unsafe(
    "https://mixed.example/",
    "non_public_dns_address",
    resolver=lambda host, port: [
        PUBLIC_V4,
        "10.10.10.10",
    ],
)

expect_unsafe(
    "https://mixed-v6.example/",
    "non_public_dns_address",
    resolver=lambda host, port: [
        PUBLIC_V4,
        "fd00::1234",
    ],
)


# Shared/CGNAT and documentation ranges are also non-global.
expect_unsafe(
    "https://shared.example/",
    "non_public_dns_address",
    resolver=lambda host, port: [
        "100.64.0.10",
    ],
)
expect_unsafe(
    "https://docs-v6.example/",
    "non_public_dns_address",
    resolver=lambda host, port: [
        "2001:db8::1234",
    ],
)


# Credentials and local IPv6 scope hints are not accepted from crawler input.
expect_unsafe(
    "https://user:pass@public.example/",
    "credentials_in_url",
)
expect_unsafe(
    "http://[fe80::1%25eth0]/",
    "scoped_ip",
)


# DNS is re-evaluated for every request/validation. A hostname that changes
# from public to private is rejected on the next resolution.
answers = iter([
    [PUBLIC_V4],
    ["127.0.0.1"],
])


def rebinding_resolver(host, port):
    return next(answers)


first = resolve_network_target(
    "https://rebind.example/resource",
    resolver=rebinding_resolver,
)
assert first.connect_ip == PUBLIC_V4

try:
    resolve_network_target(
        "https://rebind.example/resource",
        resolver=rebinding_resolver,
    )
except UnsafeNetworkTarget as exc:
    assert exc.reason == "non_public_dns_address"
else:
    raise AssertionError("DNS rebinding private answer was accepted")


# Resolver failures remain ordinary network failures, not safety bypasses.
def failing_resolver(host, port):
    raise OSError("synthetic DNS failure")


try:
    resolve_network_target(
        "https://dns-failure.example/",
        resolver=failing_resolver,
    )
except requests.ConnectionError:
    pass
else:
    raise AssertionError("DNS failure should raise ConnectionError")


# The connection pool is keyed to the validated IP, while HTTPS identity is
# kept as the original hostname for SNI/certificate verification.
adapter = SafeHTTPAdapter(
    resolver=lambda host, port: [PUBLIC_V4],
)
adapter._target_local.value = target
pool = adapter.get_connection(
    "https://public.example/catalog",
)
assert pool.host == PUBLIC_V4
assert pool.port == 443
adapter.close()


# SafeSession disables environment proxy inheritance and mounts the guarded
# adapter on both HTTP and HTTPS schemes.
session = SafeSession(
    resolver=lambda host, port: [PUBLIC_V4],
)
assert session.trust_env is False
assert isinstance(
    session.get_adapter("http://public.example/"),
    SafeHTTPAdapter,
)
assert isinstance(
    session.get_adapter("https://public.example/"),
    SafeHTTPAdapter,
)
session.close()


print("SAFE HTTP SECURITY TEST OK")
print("literal_private_ip=blocked")
print("localhost_and_local_suffix=blocked")
print("mixed_public_private_dns=blocked")
print("ipv6_private_linklocal=blocked")
print("cgnat_and_reserved=blocked")
print("credentials_and_scope_id=blocked")
print("dns_rebinding_second_resolution=blocked")
print("validated_connection_ip=pinned")
print("environment_proxy_inheritance=disabled")
