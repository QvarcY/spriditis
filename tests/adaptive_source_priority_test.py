from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.domains import DomainRecord
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
        return {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return FakeResponse(
            url=url,
            text=self.pages.get(url, "<html></html>"),
            status_code=200 if url in self.pages else 404,
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


def profile(
    domain: str,
    *,
    status: str = "active",
    crawl_runs: int = 0,
    productive_runs: int = 0,
    productive_run_rate: float = 0.0,
    entity_yield: float = 0.0,
    success_rate: float = 0.0,
    is_stale: bool = False,
):
    return {
        "domain": domain,
        "status": status,
        "crawl_runs": crawl_runs,
        "productive_runs": productive_runs,
        "productive_run_rate": productive_run_rate,
        "entity_yield": entity_yield,
        "success_rate": success_rate,
        "is_stale": is_stale,
    }


project = ResearchProject.model_validate({
    "id": "adaptive_source_priority",
    "name": "Adaptive source priority",
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["en"],
    "countries": ["LV"],
    "keywords": ["ergonomic chair"],
    "negative_keywords": [],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 2,
        "max_pages_per_domain": 1,
        "max_domains": 1,
        "max_depth": 1,
        "delay_seconds": 0,
        "respect_robots": False,
        "external_link_threshold": 35,
        "discover_sitemaps": False,
        "max_sitemap_urls_per_domain": 0,
    },
    "search": {
        "provider": "none",
        "max_queries": 1,
        "results_per_query": 10,
        "result_threshold": 35,
        "safesearch": 1,
        "queries": ["ergonomic chair"],
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

profiles = [
    profile(
        "productive.example",
        crawl_runs=3,
        productive_runs=3,
        productive_run_rate=1.0,
        entity_yield=0.75,
        success_rate=1.0,
    ),
    profile(
        "stale.example",
        crawl_runs=4,
        productive_runs=2,
        productive_run_rate=0.5,
        entity_yield=0.4,
        success_rate=1.0,
        is_stale=True,
    ),
    profile(
        "nonproductive.example",
        crawl_runs=3,
        productive_runs=0,
        productive_run_rate=0.0,
        entity_yield=0.0,
        success_rate=1.0,
    ),
    profile(
        "blocked.example",
        status="blocked",
    ),
]

ranking_hits = [
    SearchHit(url="https://blocked.example/item"),
    SearchHit(url="https://nonproductive.example/item"),
    SearchHit(url="https://stale.example/item"),
    SearchHit(url="https://untested.example/item"),
    SearchHit(url="https://productive.example/item"),
]

ranking_crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({}),
    source_profiles=profiles,
)

ranked = ranking_crawler._rank_search_hits_by_source_memory(ranking_hits)
assert [hit.url for hit in ranked] == [
    "https://productive.example/item",
    "https://untested.example/item",
    "https://stale.example/item",
    "https://nonproductive.example/item",
    "https://blocked.example/item",
]

# Without source memory, provider order must stay untouched.
plain_crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({}),
)
assert [
    hit.url
    for hit in plain_crawler._rank_search_hits_by_source_memory(ranking_hits)
] == [hit.url for hit in ranking_hits]

query = "ergonomic chair"
provider = FakeSearchProvider({
    query: [
        SearchHit(
            url="https://untested.example/item",
            title="Ergonomic chair",
            snippet="chair",
        ),
        SearchHit(
            url="https://productive.example/item",
            title="Ergonomic chair",
            snippet="chair",
        ),
    ],
})

domain_states = {
    "productive.example": DomainRecord(
        domain="productive.example",
        status="active",
        discovered_via="search_provider",
        relevance_score=0.8,
        reason="search_relevance_threshold",
    ),
}

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=provider,
    domain_states=domain_states,
    source_profiles=profiles,
)
crawler.session = FakeSession({
    "https://productive.example/item": "<html><body>known source</body></html>",
})

result = crawler.crawl()

search_events = [
    item
    for item in result.domain_discoveries
    if item.discovered_via == "search_provider"
]

assert [item.target_domain for item in search_events] == [
    "productive.example",
    "untested.example",
]
assert search_events[0].action == "known"
assert result.domains["productive.example"].status == "active"
assert result.domains["untested.example"].status == "candidate"
assert result.domains["untested.example"].reason == "domain_budget_reached"
assert result.visited_pages == 1
assert crawler.session.calls == ["https://productive.example/item"]

print("ADAPTIVE SOURCE PRIORITY TEST OK")
print(
    "productive_fresh > untested > productive_stale "
    "> nonproductive > blocked/rejected"
)
print("domain_budget_winner=productive.example")
