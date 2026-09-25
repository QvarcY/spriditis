from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Mapping

import requests


SessionFactory = Callable[[], requests.Session]


@dataclass(frozen=True)
class AsyncHTTPResult:
    requested_url: str
    final_url: str
    status_code: int | None
    headers: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    text: str = ""
    elapsed_seconds: float = 0.0
    error_type: str = ""
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return not self.error_type

    def header(self, name: str, default: str = "") -> str:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return default


class AsyncHTTPTransport:
    """
    Async wrapper around the existing requests transport.

    Each executor thread gets its own requests.Session. The transport does
    not apply crawler policy, robots rules, retry semantics, or persistence;
    those remain explicit higher-level concerns.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: int,
        accept: str = "text/html,application/xhtml+xml",
        accept_language: str = "",
        session_factory: SessionFactory = requests.Session,
    ):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.accept = accept
        self.accept_language = accept_language
        self.session_factory = session_factory

        self._local = threading.local()
        self._sessions_lock = threading.Lock()
        self._sessions: list[requests.Session] = []
        self._closed = False

    def _build_session(self) -> requests.Session:
        session = self.session_factory()
        headers = {
            "User-Agent": self.user_agent,
            "Accept": self.accept,
        }
        if self.accept_language:
            headers["Accept-Language"] = self.accept_language
        session.headers.update(headers)

        with self._sessions_lock:
            if self._closed:
                session.close()
                raise RuntimeError("AsyncHTTPTransport jau ir aizvērts.")
            self._sessions.append(session)

        return session

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._build_session()
            self._local.session = session
        return session

    def _fetch_sync(
        self,
        url: str,
        headers: Mapping[str, str] | None,
    ) -> AsyncHTTPResult:
        started = time.monotonic()

        try:
            response = self._session().get(
                url,
                timeout=self.timeout_seconds,
                allow_redirects=True,
                headers=dict(headers or {}),
            )
        except requests.RequestException as exc:
            return AsyncHTTPResult(
                requested_url=url,
                final_url=url,
                status_code=None,
                elapsed_seconds=time.monotonic() - started,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except Exception as exc:
            return AsyncHTTPResult(
                requested_url=url,
                final_url=url,
                status_code=None,
                elapsed_seconds=time.monotonic() - started,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        return AsyncHTTPResult(
            requested_url=url,
            final_url=str(response.url or url),
            status_code=int(response.status_code),
            headers=MappingProxyType(
                {
                    str(key): str(value)
                    for key, value in response.headers.items()
                }
            ),
            text=str(response.text),
            elapsed_seconds=time.monotonic() - started,
        )

    async def fetch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> AsyncHTTPResult:
        if self._closed:
            raise RuntimeError("AsyncHTTPTransport jau ir aizvērts.")

        return await asyncio.to_thread(
            self._fetch_sync,
            url,
            headers,
        )

    def close(self) -> None:
        with self._sessions_lock:
            if self._closed:
                return
            self._closed = True
            sessions = list(self._sessions)
            self._sessions.clear()

        for session in sessions:
            try:
                session.close()
            except Exception:
                pass

    async def __aenter__(self) -> "AsyncHTTPTransport":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.close()
