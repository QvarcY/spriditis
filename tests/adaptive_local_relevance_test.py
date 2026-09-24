from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit
from spriditis.search.relevance import local_relevance_signals


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


project = ResearchProject.model_validate({
    "id": "adaptive_local_relevance",
    "name": "Adaptive local relevance",
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["en"],
    "countries": ["LV"],
    "keywords": [
        "ergonomic chair",
        "lumbar support",
    ],
    "negative_keywords": ["vacancy"],
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
        "queries": ["ergonomic chair lumbar support"],
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})

query = "ergonomic chair lumbar support"

weak_url = "https://weak.example/product/ergonomic-chair/item"
exact_url = (
    "https://exact.example/product/ergonomic-chair/"
    "lumbar-support/item"
)

weak_hit = SearchHit(
    url=weak_url,
    title="Ergonomic chair",
    snippet="Office furniture",
)
exact_hit = SearchHit(
    url=exact_url,
    title="Ergonomic chair with lumbar support",
    snippet="Ergonomic office chair with adjustable lumbar support",
)
negative_hit = SearchHit(
    url=(
        "https://negative.example/product/ergonomic-chair/"
        "lumbar-support/vacancy"
    ),
    title="Ergonomic chair lumbar support vacancy",
    snippet="Ergonomic chair with lumbar support vacancy",
)

signals = local_relevance_signals(
    project,
    query,
    [weak_hit, exact_hit, negative_hit],
)

assert len(signals) == 3
assert signals[1].bm25 > signals[0].bm25
assert signals[1].title_matches > signals[0].title_matches
assert signals[1].path_matches > signals[0].path_matches
assert signals[0].negative_matches == 0
assert signals[1].negative_matches == 0
assert signals[2].negative_matches == 1

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

provider = FakeSearchProvider({
    query: [
        negative_hit,
        weak_hit,
        exact_hit,
    ],
})

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=provider,
)
crawler.session = FakeSession({
    exact_url: "<html><body>exact result</body></html>",
})

ranked = crawler._rank_search_hits(
    [negative_hit, weak_hit, exact_hit],
    query,
)
assert [item.hit.url for item in ranked] == [
    exact_url,
    weak_url,
    negative_hit.url,
]

result = crawler.crawl()

search_events = [
    item
    for item in result.domain_discoveries
    if item.discovered_via == "search_provider"
]

assert [item.target_domain for item in search_events] == [
    "exact.example",
    "weak.example",
    "negative.example",
]
assert search_events[0].action == "activated"
assert result.domains["exact.example"].status == "active"
assert result.domains["weak.example"].status == "candidate"
assert result.domains["weak.example"].reason == "domain_budget_reached"
assert result.visited_pages == 1
assert crawler.session.calls == [exact_url]

print("ADAPTIVE LOCAL RELEVANCE TEST OK")
print("provider_first=weak.example")
print("local_relevance_winner=exact.example")
print(
    f"bm25_exact={signals[1].bm25:.3f} "
    f"bm25_weak={signals[0].bm25:.3f}"
)
