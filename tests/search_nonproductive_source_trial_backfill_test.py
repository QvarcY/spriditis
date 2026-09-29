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
        return {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers = {}
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        return FakeResponse(url, self.pages[url])


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
first = "https://empty-one.example/product/engraved-keychain"
second = "https://empty-two.example/product/engraved-keychain"
later = "https://useful.example/catalog"

project = ResearchProject.model_validate({
    "id": "nonproductive-source-trial-backfill",
    "name": query,
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["en"],
    "countries": [],
    "keywords": ["engraved", "keychain"],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 4,
        "max_pages_per_domain": 1,
        "max_domains": 2,
        "max_depth": 1,
        "delay_seconds": 0,
        "respect_robots": False,
        "discover_sitemaps": False,
        "discover_feeds": False,
        "saturation_window": 1,
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
    SearchHit(url=first, title="Engraved keychain", snippet="Custom gift"),
    SearchHit(url=second, title="Engraved keychain", snippet="Custom gift"),
    SearchHit(url=later, title="Keychain", snippet="Custom gift"),
]
assert all(
    text_relevance_score(project, hit.url, f"{hit.title} {hit.snippet}")
    >= project.search.result_threshold
    for hit in hits[:2]
)
assert (
    text_relevance_score(project, later, "Keychain Custom gift")
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

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({query: hits}),
)
crawler.session = FakeSession({
    first: "<html><body>Welcome.</body></html>",
    second: "<html><body>Welcome.</body></html>",
    later: """
        <html><head><script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Personalized engraved keychain",
          "offers": {
            "@type": "Offer",
            "price": "12.50",
            "priceCurrency": "EUR"
          }
        }
        </script></head><body>Personalized engraved keychain</body></html>
    """,
})

result = crawler.crawl()

assert crawler.session.calls == [first, second, later]
assert result.visited_pages == 3
assert result.search_domains_activated == 3
assert len(result.entities) == 1
assert result.entities[0].title == "Personalized engraved keychain"
assert result.entities[0].price == 12.5
assert result.domains["useful.example"].status == "active"
assert result.domains["useful.example"].entities_found == 1
assert all(
    result.domains[domain].status == "candidate"
    and result.domains[domain].reason == "nonproductive_source"
    and result.domains[domain].pages_seen == 1
    for domain in ("empty-one.example", "empty-two.example")
)
assert any(
    item.target_url == later and item.reason == "below_search_threshold"
    for item in result.domain_discoveries
)
assert any(
    item.target_url == later and item.reason == "search_candidate_trial"
    and item.action == "activated"
    for item in result.domain_discoveries
)
assert {
    item.target for item in result.adaptive_decisions
    if item.stage == "source_slot"
    and item.decision == "released"
    and item.signals["reason"] == "nonproductive_source"
} == {"empty-one.example", "empty-two.example"}
assert any(
    item.stage == "search_domain_backfill" and item.target == later
    for item in result.adaptive_decisions
)
assert len(crawler._coverage.attempted_urls) <= project.crawl.max_pages_total
assert len(crawler._coverage.released_domains) == 2

# A site with more queued links still gets only two evidence-free pages,
# even when its normal per-domain page cap is higher.
bounded_project = project.model_copy(deep=True)
bounded_project.crawl.max_domains = 1
bounded_project.crawl.max_pages_per_domain = 4
next_one = "https://empty-one.example/product/engraved-keychain/next-one"
next_two = "https://empty-one.example/product/engraved-keychain/next-two"
bounded_crawler = ResearchCrawler(
    settings,
    bounded_project,
    NoOpAI(),
    search_provider=FakeSearchProvider({query: [hits[0], hits[2]]}),
)
bounded_crawler.session = FakeSession({
    first: f"""<html><body>
        <a href="{next_one}">Engraved keychain one</a>
        <a href="{next_two}">Engraved keychain two</a>
        </body></html>""",
    next_one: "<html><body>No products here.</body></html>",
    next_two: "<html><body>No products here either.</body></html>",
    later: crawler.session.pages[later],
})
bounded_result = bounded_crawler.crawl()
assert bounded_crawler.session.calls == [first, next_one, later]
assert bounded_result.domains["empty-one.example"].reason == "nonproductive_source"
assert bounded_result.domains["empty-one.example"].pages_seen == 2
assert bounded_result.domains["useful.example"].entities_found == 1
assert bounded_result.search_domains_activated == 2
print("SEARCH NONPRODUCTIVE SOURCE TRIAL BACKFILL TEST OK")
