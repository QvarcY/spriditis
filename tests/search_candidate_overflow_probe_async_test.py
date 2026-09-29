from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.async_http import AsyncHTTPResult
from spriditis.crawler.engine import ResearchCrawler
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit


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

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        raise AssertionError(
            f"unexpected sync main-page fetch: {url}"
        )


class FakeAsyncTransport:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.calls: list[str] = []
        self.closed = False

    async def fetch(self, url: str) -> AsyncHTTPResult:
        self.calls.append(url)
        await asyncio.sleep(0)

        return AsyncHTTPResult(
            requested_url=url,
            final_url=url,
            status_code=200,
            headers={
                "Content-Type":
                    "text/html; charset=utf-8",
            },
            text=self.pages[url],
        )

    def close(self) -> None:
        self.closed = True


def product_html(name: str) -> str:
    return f"""
        <html>
        <head>
            <script type="application/ld+json">
            {{
              "@context": "https://schema.org",
              "@type": "Product",
              "name": "{name}",
              "offers": {{
                "@type": "Offer",
                "price": "15.00",
                "priceCurrency": "EUR"
              }}
            }}
            </script>
        </head>
        <body>{name}</body>
        </html>
    """


query = "engraved keychain"

retained = (
    "https://retained.example/"
    "product/engraved-keychain"
)

overflow = "https://overflow.example/catalog"

probe_one = (
    "https://overflow.example/"
    "product/engraved-keychain-one"
)

probe_two = (
    "https://overflow.example/"
    "product/engraved-keychain-two"
)


project = ResearchProject.model_validate({
    "id": "c2-async-probe-budget",
    "name": query,
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["en"],
    "countries": [],
    "keywords": [
        "engraved",
        "keychain",
    ],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 6,
        "max_pages_per_domain": 4,
        "max_domains": 1,
        "max_probe_domains": 1,
        "max_probe_pages_total": 2,
        "max_depth": 2,
        "delay_seconds": 0,
        "respect_robots": False,
        "discover_sitemaps": False,
        "discover_feeds": False,
        "saturation_window": 0,
        "diminishing_returns_window": 0,
        "async_enabled": True,
        "async_global_concurrency": 3,
        "async_per_domain_concurrency": 2,
        "async_max_pending": 3,
        "async_max_retries": 0,
    },
    "search": {
        "provider": "none",
        "max_queries": 1,
        "results_per_query": 2,
        "result_threshold": 35,
        "queries": [query],
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


settings = AppSettings(
    gemini_api_key="",
    gemini_model="none",
    gemini_batch_size=10,
    gemini_requests_per_minute=5,
    gemini_max_retries=0,
    gemini_retry_base_seconds=1.0,
    db_path=Path("data/test.db"),
    legacy_db_path=None,
    report_dir=Path("reports"),
    smtp_host="",
    smtp_port=465,
    smtp_user="",
    smtp_app_password="",
    report_to="",
    send_email=False,
    user_agent="SpriditisTest/3.3",
    request_timeout_seconds=1,
)


pages = {
    retained: product_html(
        "Primary engraved keychain"
    ),
    overflow: f"""
        <html>
        <body>
            <a href="{probe_one}">
                Engraved keychain one
            </a>
            <a href="{probe_two}">
                Engraved keychain two
            </a>
        </body>
        </html>
    """,
    probe_one: """
        <html>
        <body>No product entity here.</body>
        </html>
    """,
    probe_two: """
        <html>
        <body>No product entity here either.</body>
        </html>
    """,
}


transport = FakeAsyncTransport(pages)

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({
        query: [
            SearchHit(
                url=retained,
                title="Engraved keychain",
                snippet="Custom engraved keychain",
            ),
            SearchHit(
                url=overflow,
                title="Keychain",
                snippet="Custom gift",
            ),
        ],
    }),
    async_transport=transport,
)

sync_session = ForbiddenSyncSession()
crawler.session = sync_session

result = crawler.crawl()


assert sync_session.calls == []

assert retained in transport.calls
assert overflow in transport.calls

# max_probe_pages_total=2 means:
#   1. overflow landing page
#   2. exactly one evidence-backed continuation
#
# The second continuation must never reach the network,
# even though the async wave could reserve both.
probe_network_calls = [
    url
    for url in transport.calls
    if url.startswith(
        "https://overflow.example/"
    )
]

assert len(probe_network_calls) == 2
assert overflow in probe_network_calls
assert probe_one in probe_network_calls
assert probe_two not in probe_network_calls

assert (
    crawler._coverage
    .overflow_probe_attempted_urls
    == {
        overflow,
        probe_one,
    }
)

assert (
    len(
        crawler._coverage
        .overflow_probe_attempted_urls
    )
    == project.crawl.max_probe_pages_total
)

assert probe_two not in crawler._coverage.attempted_urls

assert crawler._coverage.retained_domains == {
    "retained.example",
}

assert crawler._coverage.overflow_probe_domains == {
    "overflow.example",
}

assert len(result.entities) == 1
assert (
    result.entities[0].title
    == "Primary engraved keychain"
)

print("ASYNC CANDIDATE PROBE BUDGET TEST OK")
