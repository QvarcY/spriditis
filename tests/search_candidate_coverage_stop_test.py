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
                "text/html; charset=utf-8",
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


query = "engraved keychain"

retained = (
    "https://retained.example/"
    "product/engraved-keychain"
)

overflow = "https://overflow.example/catalog"
third = "https://third.example/catalog"


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
                "price": "12.50",
                "priceCurrency": "EUR"
              }}
            }}
            </script>
        </head>
        <body>{name}</body>
        </html>
    """


pages = {
    retained: product_html("Primary engraved keychain"),
    overflow: product_html("Overflow keychain"),
    third: product_html("Third keychain"),
}


def make_project(
    project_id: str,
    *,
    max_probe_domains: int,
    max_probe_pages_total: int,
) -> ResearchProject:
    return ResearchProject.model_validate({
        "id": project_id,
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
            "max_pages_total": 10,
            "max_pages_per_domain": 4,
            "max_domains": 1,
            "max_probe_domains": max_probe_domains,
            "max_probe_pages_total": max_probe_pages_total,
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


def make_hits(include_third: bool) -> list[SearchHit]:
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
    ]

    if include_third:
        hits.append(
            SearchHit(
                url=third,
                title="Keychain",
                snippet="Custom gift",
            )
        )

    return hits


def run_case(
    project: ResearchProject,
    *,
    include_third: bool,
):
    crawler = ResearchCrawler(
        settings,
        project,
        NoOpAI(),
        search_provider=FakeSearchProvider({
            query: make_hits(include_third),
        }),
    )

    crawler.session = FakeSession(pages)

    result = crawler.crawl()

    stop = [
        decision
        for decision in result.adaptive_decisions
        if decision.stage == "stop"
    ]

    assert len(stop) == 1

    return crawler, result, stop[0]


# --------------------------------------------------
# CASE 1 — DOMAIN PROBE BUDGET
# --------------------------------------------------

crawler, result, stop = run_case(
    make_project(
        "c2-stop-domain-budget",
        max_probe_domains=1,
        max_probe_pages_total=5,
    ),
    include_third=True,
)

assert result.stop_reason == "probe_domain_budget_exhausted"
assert stop.decision == "probe_domain_budget_exhausted"
assert stop.signals["coverage_status"] == "resource_limited"
assert stop.signals["candidate_domains_remaining"] == [
    "third.example",
]
assert stop.signals["candidate_domains_remaining_count"] == 1
assert stop.signals["search_candidate_domains_discovered"] == 3
assert stop.signals["search_candidate_domains_probed"] == 2


# --------------------------------------------------
# CASE 2 — PAGE PROBE BUDGET
# --------------------------------------------------

crawler, result, stop = run_case(
    make_project(
        "c2-stop-page-budget",
        max_probe_domains=3,
        max_probe_pages_total=1,
    ),
    include_third=True,
)

assert result.stop_reason == "probe_page_budget_exhausted"
assert stop.decision == "probe_page_budget_exhausted"
assert stop.signals["coverage_status"] == "resource_limited"
assert stop.signals["candidate_domains_remaining"] == [
    "third.example",
]
assert stop.signals["overflow_probe_pages"] == 1


# --------------------------------------------------
# CASE 3 — PROVIDER CANDIDATE POOL EXHAUSTED
# --------------------------------------------------

crawler, result, stop = run_case(
    make_project(
        "c2-stop-candidates-exhausted",
        max_probe_domains=5,
        max_probe_pages_total=10,
    ),
    include_third=False,
)

assert result.stop_reason == "search_candidates_exhausted"
assert stop.decision == "search_candidates_exhausted"
assert (
    stop.signals["coverage_status"]
    == "candidate_pool_exhausted"
)
assert stop.signals["candidate_domains_remaining"] == []
assert stop.signals["candidate_domains_remaining_count"] == 0
assert stop.signals["search_candidate_domains_discovered"] == 2
assert stop.signals["search_candidate_domains_probed"] == 2

print("SEARCH CANDIDATE COVERAGE STOP TEST OK")
