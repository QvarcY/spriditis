from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from dataclasses import dataclass
from pathlib import Path

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
        return {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(url)
        return FakeResponse(url=url, text=self.pages.get(url, "<html></html>"), status_code=200 if url in self.pages else 404)


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
    "id": "expedition_test",
    "name": "Expedition test",
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["en"],
    "countries": ["LV"],
    "keywords": ["ergonomic office chair", "lumbar support", "mesh chair"],
    "negative_keywords": [],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 3,
        "max_pages_per_domain": 1,
        "max_domains": 1,
        "max_depth": 2,
        "delay_seconds": 0,
        "respect_robots": False,
        "external_link_threshold": 45,
        "discover_sitemaps": False,
        "max_sitemap_urls_per_domain": 0
    },
    "search": {
        "provider": "none",
        "max_queries": 1,
        "results_per_query": 5,
        "result_threshold": 35,
        "safesearch": 1,
        "queries": ["ergonomic office chair lumbar support"]
    },
    "analysis": {"ai_enabled": False, "ai_provider": "none"}
})

query = "ergonomic office chair lumbar support"
provider = FakeSearchProvider({
    query: [
        SearchHit(
            url="https://market-one.example/product/ergonomic-office-chair",
            title="Ergonomic office chair",
            snippet="Lumbar support mesh chair",
        ),
        SearchHit(
            url="https://market-two.example/product/ergonomic-office-chair",
            title="Ergonomic office chair",
            snippet="Lumbar support mesh chair",
        ),
        SearchHit(
            url="https://facebook.com/ergonomic-office-chair",
            title="Ergonomic office chair",
            snippet="Lumbar support mesh chair",
        ),
    ]
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
    "https://market-one.example/product/ergonomic-office-chair": """
    <html><body><h1>Search-discovered market</h1></body></html>
    """
}

crawler = ResearchCrawler(settings, project, NoOpAI(), search_provider=provider)
crawler.session = FakeSession(pages)
result = crawler.crawl()

assert result.search_queries_issued == 1
assert result.search_results_seen == 3
assert result.search_results_unique == 3
assert result.search_results_duplicates == 0
assert result.search_domains_activated == 1
assert result.search_provider_errors == 0
assert result.visited_pages == 1
assert result.domains["market-one.example"].status == "active"
assert result.domains["market-one.example"].discovered_via == "search_provider"
assert result.domains["market-two.example"].status == "candidate"
assert result.domains["market-two.example"].reason == "domain_budget_reached"
assert result.domains["facebook.com"].status == "blocked"

search_events = [d for d in result.domain_discoveries if d.discovered_via == "search_provider"]
assert len(search_events) == 3
assert search_events[0].provider == "fake"
assert search_events[0].query_text == query
assert any(d.action == "activated" and d.target_domain == "market-one.example" for d in search_events)

print("EXPEDITION INTEGRATION TEST OK")
print("seed_urls=0")
print("search_queries=1")
print("search_results=3")
print("activated=market-one.example")
print("candidate_due_to_budget=market-two.example")
print("blocked=facebook.com")
