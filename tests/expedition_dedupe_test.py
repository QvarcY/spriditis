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
        return EntityEnrichment(is_relevant=True, confidence=1.0, relevance_score=1.0, category="test", tags=[], attributes={}, opportunity_notes="")


project = ResearchProject.model_validate({
    "id": "expedition_dedupe",
    "name": "Expedition dedupe",
    "languages": ["en"],
    "countries": ["LV"],
    "keywords": ["ergonomic chair", "lumbar support"],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition", "max_pages_total": 2, "max_pages_per_domain": 1,
        "max_domains": 2, "max_depth": 1, "delay_seconds": 0,
        "respect_robots": False, "discover_sitemaps": False,
        "max_sitemap_urls_per_domain": 0
    },
    "search": {
        "provider": "none", "max_queries": 2, "results_per_query": 5,
        "result_threshold": 20, "safesearch": 1,
        "queries": ["ergonomic chair", "lumbar support chair"]
    },
    "analysis": {"ai_enabled": False, "ai_provider": "none"}
})

url = "https://market.example/product/ergonomic-chair"
provider = FakeSearchProvider({
    "ergonomic chair": [SearchHit(url=url, title="Ergonomic chair", snippet="lumbar support")],
    "lumbar support chair": [SearchHit(url=url + "#details", title="Same chair", snippet="ergonomic chair")],
})

settings = AppSettings(
    gemini_api_key="", gemini_model="none", gemini_batch_size=10,
    gemini_requests_per_minute=5, gemini_max_retries=0, gemini_retry_base_seconds=1,
    db_path=Path("data/test.db"), legacy_db_path=None, report_dir=Path("reports"),
    smtp_host="", smtp_port=465, smtp_user="", smtp_app_password="", report_to="",
    send_email=False, user_agent="SpriditisTest/1.0", request_timeout_seconds=1,
)

crawler = ResearchCrawler(settings, project, NoOpAI(), search_provider=provider)
crawler.session = FakeSession({url: "<html><body>chair</body></html>"})
result = crawler.crawl()

assert result.search_results_seen == 2
assert result.search_results_unique == 1
assert result.search_results_duplicates == 1
assert result.visited_pages == 1
assert len([d for d in result.domain_discoveries if d.discovered_via == "search_provider"]) == 1
print("EXPEDITION DEDUPE TEST OK")
