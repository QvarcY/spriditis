from __future__ import annotations

import asyncio
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath

import requests

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.crawler.async_coordinator import (
    AsyncCrawlCoordinator,
    AsyncCrawlPolicy,
)
from spriditis.crawler.async_http import AsyncHTTPTransport


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int
    headers: dict[str, str]


created_sessions: list["FakeSession"] = []
created_lock = threading.Lock()


class FakeSession:
    def __init__(self):
        self.headers: dict[str, str] = {}
        self.closed = False
        self.thread_ids: set[int] = set()
        self.active = 0
        self.peak_active = 0
        self.calls: list[tuple[str, dict[str, str]]] = []

        with created_lock:
            created_sessions.append(self)

    def get(
        self,
        url: str,
        *,
        timeout: int,
        allow_redirects: bool,
        headers: dict[str, str],
    ) -> FakeResponse:
        thread_id = threading.get_ident()
        self.thread_ids.add(thread_id)
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)

        try:
            self.calls.append((url, dict(headers)))
            time.sleep(0.025)

            if url.endswith("/network-error"):
                raise requests.ConnectionError("synthetic connection error")

            if url.endswith("/redirect"):
                return FakeResponse(
                    url="https://final.example/landing",
                    text="<html>redirected</html>",
                    status_code=200,
                    headers={
                        "Content-Type": "text/html; charset=utf-8",
                        "X-Test": "redirect",
                    },
                )

            return FakeResponse(
                url=url,
                text=f"<html>{url}</html>",
                status_code=200,
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "X-Test": "ok",
                },
            )
        finally:
            self.active -= 1

    def close(self) -> None:
        self.closed = True


async def main() -> None:
    transport = AsyncHTTPTransport(
        user_agent="SpriditisAsyncHTTPTest/1.0",
        timeout_seconds=3,
        accept_language="lv,en;q=0.7",
        session_factory=FakeSession,
    )

    coordinator = AsyncCrawlCoordinator(
        AsyncCrawlPolicy(
            global_concurrency=3,
            per_domain_concurrency=2,
            max_pending=3,
        )
    )

    urls = [
        "https://a.example/1",
        "https://b.example/1",
        "https://c.example/redirect",
        "https://a.example/2",
        "https://b.example/network-error",
    ]

    async def worker(url: str):
        return await transport.fetch(
            url,
            headers={"X-Request": url.rsplit("/", 1)[-1]},
        )

    task_results, stats = await coordinator.run(urls, worker)

    assert stats.submitted == 5
    assert stats.completed == 5
    assert stats.failed == 0

    fetch_results = [item.value for item in task_results]
    assert all(result is not None for result in fetch_results)

    first = fetch_results[0]
    assert first is not None
    assert first.ok is True
    assert first.status_code == 200
    assert first.final_url == "https://a.example/1"
    assert first.header("content-type").startswith("text/html")
    assert first.header("X-Test") == "ok"
    assert first.elapsed_seconds > 0

    redirected = fetch_results[2]
    assert redirected is not None
    assert redirected.ok is True
    assert redirected.final_url == "https://final.example/landing"
    assert redirected.header("x-test") == "redirect"

    failed = fetch_results[4]
    assert failed is not None
    assert failed.ok is False
    assert failed.status_code is None
    assert failed.error_type == "ConnectionError"
    assert "synthetic connection error" in failed.error_message

    assert len(created_sessions) >= 2
    assert all(len(session.thread_ids) == 1 for session in created_sessions)
    assert all(session.peak_active == 1 for session in created_sessions)

    all_calls = [
        call
        for session in created_sessions
        for call in session.calls
    ]
    assert len(all_calls) == len(urls)

    request_headers = {
        url: headers
        for url, headers in all_calls
    }
    assert request_headers["https://a.example/1"]["X-Request"] == "1"

    for session in created_sessions:
        assert session.headers["User-Agent"] == "SpriditisAsyncHTTPTest/1.0"
        assert session.headers["Accept"] == "text/html,application/xhtml+xml"
        assert session.headers["Accept-Language"] == "lv,en;q=0.7"

    transport.close()
    assert all(session.closed for session in created_sessions)

    try:
        await transport.fetch("https://a.example/after-close")
    except RuntimeError as exc:
        assert "aizvērts" in str(exc)
    else:
        raise AssertionError("fetch pēc close bija jābūt noraidītam")


asyncio.run(main())

print("ASYNC HTTP TRANSPORT TEST OK")
print("requests_io=asyncio_to_thread")
print("session_scope=thread_local")
print("shared_session_across_threads=no")
print("redirect_result=structured")
print("request_error=structured")
print("response_headers=read_only_snapshot")
print("transport_close=all_sessions_closed")
