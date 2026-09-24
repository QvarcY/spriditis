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
    "id": "adaptive_multihop",
    "name": "Adaptive multi-hop discovery",
    "keywords": ["research"],
    "negative_keywords": [],
    "seed_urls": ["https://seed.example/start"],
    "crawl": {
        "mode": "discovery",
        "max_pages_total": 10,
        "max_pages_per_domain": 5,
        "max_domains": 10,
        "max_depth": 6,
        "max_discovery_depth": 2,
        "discovery_depth_budgets": {
            1: 1,
            2: 1,
        },
        "delay_seconds": 0,
        "respect_robots": False,
        "external_link_threshold": 35,
        "discover_sitemaps": False,
        "discover_feeds": False,
    },
    "search": {
        "provider": "none",
        "max_queries": 0,
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

hop1 = "https://hop1.example/product/research/item"
hop1_second = "https://hop1-second.example/product/research/item"
hop1_inside = "https://hop1.example/product/research/inside"
hop2 = "https://hop2.example/product/research/item"
hop3 = "https://hop3.example/product/research/item"

pages = {
    "https://seed.example/start": f"""
        <html><body>
        <a href="{hop1}">research source one</a>
        <a href="{hop1_second}">research source two</a>
        </body></html>
    """,
    hop1: f"""
        <html><body>
        <a href="{hop1_inside}">research inside</a>
        </body></html>
    """,
    hop1_inside: f"""
        <html><body>
        <a href="{hop2}">research second hop</a>
        </body></html>
    """,
    hop2: f"""
        <html><body>
        <a href="{hop3}">research third hop</a>
        </body></html>
    """,
}

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
)
crawler.session = FakeSession(pages)
result = crawler.crawl()

# Seed -> hop1 is discovery depth 1. The second depth-1 domain is kept
# auditable but cannot activate because that depth budget is already spent.
assert result.domains["hop1.example"].status == "active"
assert result.domains["hop1-second.example"].status == "candidate"
assert (
    result.domains["hop1-second.example"].reason
    == "discovery_depth_budget_reached"
)

# Same-domain navigation does not consume another discovery hop.
assert hop1_inside in crawler.session.calls

# hop1 -> hop2 is discovery depth 2 and is allowed.
assert result.domains["hop2.example"].status == "active"
assert hop2 in crawler.session.calls

# hop2 -> hop3 would be discovery depth 3, beyond max_discovery_depth=2.
assert result.domains["hop3.example"].status == "candidate"
assert result.domains["hop3.example"].reason == "discovery_depth_limit"
assert hop3 not in crawler.session.calls

assert result.visited_pages == 4
assert crawler.session.calls == [
    "https://seed.example/start",
    hop1,
    hop1_inside,
    hop2,
]

budget_events = [
    item
    for item in result.domain_discoveries
    if item.reason == "discovery_depth_budget_reached"
]
limit_events = [
    item
    for item in result.domain_discoveries
    if item.reason == "discovery_depth_limit"
]

assert [item.target_domain for item in budget_events] == [
    "hop1-second.example",
]
assert [item.target_domain for item in limit_events] == [
    "hop3.example",
]

print("ADAPTIVE MULTI-HOP TEST OK")
print("same_domain_navigation_preserves_discovery_depth")
print("depth1_budget=1 depth2_budget=1 max_discovery_depth=2")
print("blocked_by_depth_budget=hop1-second.example")
print("blocked_by_depth_limit=hop3.example")
