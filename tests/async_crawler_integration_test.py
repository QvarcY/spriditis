from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path as _BootstrapPath
from urllib.parse import urlparse

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.async_http import AsyncHTTPResult
from spriditis.crawler.engine import ResearchCrawler


class NoOpAI(AIProvider):
    def enrich(self, entity, project):
        return EntityEnrichment(
            is_relevant=True,
            confidence=1.0,
            relevance_score=1.0,
            category="test",
            tags=[],
            attributes={},
            opportunity_notes="",
        )


class ForbiddenSyncSession:
    def __init__(self):
        self.headers = {}
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        raise AssertionError(
            f"async main-page fetch fell back to sync session: {url}"
        )


class FakeAsyncTransport:
    def __init__(self, *, fail_urls=None):
        self.fail_urls = set(fail_urls or [])
        self.calls: list[str] = []
        self.active = 0
        self.peak_active = 0
        self.domain_active: dict[str, int] = defaultdict(int)
        self.peak_domain_active: dict[str, int] = defaultdict(int)
        self.starts: dict[str, list[float]] = defaultdict(list)
        self.closed = False

    async def fetch(self, url: str) -> AsyncHTTPResult:
        domain = urlparse(url).hostname or ""

        self.calls.append(url)
        self.starts[domain].append(time.monotonic())

        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        self.domain_active[domain] += 1
        self.peak_domain_active[domain] = max(
            self.peak_domain_active[domain],
            self.domain_active[domain],
        )

        try:
            await asyncio.sleep(0.03)

            if url in self.fail_urls:
                return AsyncHTTPResult(
                    requested_url=url,
                    final_url=url,
                    status_code=None,
                    elapsed_seconds=0.03,
                    error_type="ConnectionError",
                    error_message="synthetic async connection error",
                )

            return AsyncHTTPResult(
                requested_url=url,
                final_url=url,
                status_code=200,
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                },
                text=(
                    "<html><body>"
                    f"<h1>{url}</h1>"
                    "</body></html>"
                ),
                elapsed_seconds=0.03,
            )
        finally:
            self.domain_active[domain] -= 1
            self.active -= 1

    def close(self) -> None:
        self.closed = True


def settings() -> AppSettings:
    return AppSettings(
        gemini_api_key="",
        gemini_model="none",
        gemini_batch_size=10,
        gemini_requests_per_minute=5,
        gemini_max_retries=0,
        gemini_retry_base_seconds=1.0,
        db_path=_BootstrapPath("data/test.db"),
        legacy_db_path=None,
        report_dir=_BootstrapPath("reports"),
        smtp_host="",
        smtp_port=465,
        smtp_user="",
        smtp_app_password="",
        report_to="",
        send_email=False,
        user_agent="SpriditisAsyncCrawlerTest/1.0",
        request_timeout_seconds=1,
    )


SEEDS = [
    "https://a.example/1",
    "https://a.example/2",
    "https://b.example/1",
    "https://b.example/2",
]

project = ResearchProject.model_validate(
    {
        "id": "async_crawler_integration",
        "name": "Async crawler integration",
        "keywords": ["test"],
        "seed_urls": SEEDS,
        "crawl": {
            "mode": "domain",
            "max_pages_total": 4,
            "max_pages_per_domain": 2,
            "max_domains": 2,
            "max_depth": 0,
            "delay_seconds": 0.01,
            "respect_robots": False,
            "discover_sitemaps": False,
            "discover_feeds": False,
            "async_enabled": True,
            "async_global_concurrency": 3,
            "async_per_domain_concurrency": 1,
            "async_max_pending": 3,
        },
        "search": {
            "provider": "none",
            "max_queries": 0,
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    }
)

transport = FakeAsyncTransport()
crawler = ResearchCrawler(
    settings(),
    project,
    NoOpAI(),
    async_transport=transport,
)
sync_session = ForbiddenSyncSession()
crawler.session = sync_session

result = crawler.crawl()

assert result.visited_pages == 4
assert result.failed_pages == 0
assert result.stop_reason == "max_pages"

# Main page fetches are supplied exclusively by the async transport.
assert sync_session.calls == []
assert set(transport.calls) == set(SEEDS)
assert len(transport.calls) == len(SEEDS)

# Network waiting overlaps across domains, while each domain remains serial.
assert transport.peak_active >= 2
assert all(
    peak == 1
    for peak in transport.peak_domain_active.values()
)

# Research processing order remains deterministic despite async completion.
assert [visit.url for visit in result.page_visits] == SEEDS
assert all(
    visit.outcome == "html_ok"
    for visit in result.page_visits
)

assert result.async_fetch_waves == 2
assert result.async_fetch_submitted == 4
assert result.async_fetch_failures == 0
assert result.async_peak_active >= 2
assert result.async_peak_active <= 3
assert all(
    peak == 1
    for peak in result.async_peak_domain_active.values()
)

# Injected transports are caller-owned and are not closed by the crawler.
assert transport.closed is False


# Structured async transport failures must enter the same page-visit audit
# path without silently retrying through the synchronous session.
good_url = "https://good.example/item"
bad_url = "https://bad.example/item"
failure_project = ResearchProject.model_validate(
    {
        "id": "async_crawler_failure",
        "name": "Async crawler failure",
        "keywords": ["test"],
        "seed_urls": [good_url, bad_url],
        "crawl": {
            "mode": "domain",
            "max_pages_total": 2,
            "max_pages_per_domain": 1,
            "max_domains": 2,
            "max_depth": 0,
            "delay_seconds": 0,
            "respect_robots": False,
            "discover_sitemaps": False,
            "discover_feeds": False,
            "async_enabled": True,
            "async_global_concurrency": 2,
            "async_per_domain_concurrency": 1,
            "async_max_pending": 2,
        },
        "search": {
            "provider": "none",
            "max_queries": 0,
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    }
)

failure_transport = FakeAsyncTransport(fail_urls={bad_url})
failure_crawler = ResearchCrawler(
    settings(),
    failure_project,
    NoOpAI(),
    async_transport=failure_transport,
)
failure_sync = ForbiddenSyncSession()
failure_crawler.session = failure_sync

failure_result = failure_crawler.crawl()

assert failure_sync.calls == []
assert failure_result.visited_pages == 1
assert failure_result.failed_pages == 1
assert failure_result.async_fetch_submitted == 2
assert failure_result.async_fetch_failures == 1
assert [visit.url for visit in failure_result.page_visits] == [
    good_url,
    bad_url,
]
assert [visit.outcome for visit in failure_result.page_visits] == [
    "html_ok",
    "http_error:ConnectionError",
]


print("ASYNC CRAWLER INTEGRATION TEST OK")
print("async_mode=main_page_fetch_enabled")
print("sync_main_page_fallback=unused")
print("cross_domain_network_wait=overlapped")
print("per_domain_network_concurrency=bounded")
print("research_processing_order=deterministic")
print("frontier_priority=processed_after_prefetch_restore")
print("async_run_diagnostics=exposed")
print("async_transport_error=audited_without_sync_retry")
