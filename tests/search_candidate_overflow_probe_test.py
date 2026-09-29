from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.crawler.policy import text_relevance_score
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200

    @property
    def headers(self):
        return {
            "Content-Type":
                "text/html; charset=utf-8"
        }


class FakeSession:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers = {}
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        return FakeResponse(
            url=url,
            text=self.pages[url],
        )


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


query = "engraved keychain"

retained = (
    "https://retained.example/"
    "product/engraved-keychain"
)

overflow = (
    "https://overflow.example/catalog"
)

unprobed = (
    "https://unprobed.example/catalog"
)


project = ResearchProject.model_validate({
    "id": "c2-overflow-probe",
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
        "max_pages_total": 4,
        "max_pages_per_domain": 4,
        "max_domains": 1,
        "max_probe_domains": 1,
        "max_probe_pages_total": 2,
        "max_depth": 1,
        "delay_seconds": 0,
        "respect_robots": False,
        "discover_sitemaps": False,
        "discover_feeds": False,
        "saturation_window": 0,
        "diminishing_returns_window": 0,
    },
    "search": {
        "provider": "none",
        "max_queries": 1,
        "results_per_query": 3,
        "result_threshold": 35,
        "queries": [query],
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


hits = [
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
    SearchHit(
        url=unprobed,
        title="Keychain",
        snippet="Custom gift",
    ),
]

assert (
    text_relevance_score(
        project,
        retained,
        "Engraved keychain Custom engraved keychain",
    )
    >= project.search.result_threshold
)

assert (
    text_relevance_score(
        project,
        overflow,
        "Keychain Custom gift",
    )
    < project.search.result_threshold
)


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


def product_html(name: str, price: str) -> str:
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
                "price": "{price}",
                "priceCurrency": "EUR"
              }}
            }}
            </script>
        </head>
        <body>{name}</body>
        </html>
    """


crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({
        query: hits,
    }),
)

crawler.session = FakeSession({
    retained: product_html(
        "Primary engraved keychain",
        "15.00",
    ),
    overflow: product_html(
        "Overflow personalized keychain",
        "12.50",
    ),
    unprobed: product_html(
        "Should not be probed",
        "9.99",
    ),
})


result = crawler.crawl()


# max_domains=1 retains the highest-priority productive source.
assert crawler._coverage.retained_domains == {
    "retained.example",
}

# The second candidate is still actually inspected through
# the bounded overflow probe lane.
assert crawler.session.calls == [
    retained,
    overflow,
]

assert crawler._coverage.productive_domains == {
    "retained.example",
    "overflow.example",
}

assert crawler._coverage.overflow_probe_domains == {
    "overflow.example",
}

assert crawler._coverage.overflow_probe_attempted_urls == {
    overflow,
}

# Probe-domain budget prevents silently probing the third source.
assert "unprobed.example" not in crawler._coverage.attempted_domains

# Discovery telemetry knows about all provider candidate domains,
# including the one not reached because the explicit probe budget ended.
assert crawler._coverage.search_candidate_domains == {
    "retained.example",
    "overflow.example",
    "unprobed.example",
}

snapshot = crawler._coverage.snapshot()

assert snapshot["search_candidate_domains_discovered"] == 3
assert snapshot["search_candidate_domains_probed"] == 2
assert snapshot["overflow_probe_pages"] == 1

assert len(result.entities) == 2

assert {
    entity.source_domain
    for entity in result.entities
} == {
    "retained.example",
    "overflow.example",
}

assert any(
    item.stage == "search_candidate_probe"
    and item.target == overflow
    and item.signals["overflow_probe"] is True
    for item in result.adaptive_decisions
)

print("SEARCH CANDIDATE OVERFLOW PROBE TEST OK")
