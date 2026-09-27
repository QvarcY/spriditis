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


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200

    @property
    def headers(self):
        return {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.responses[url]


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

query = "Bambu Lab P1S Combo Latvija"

project = ResearchProject.model_validate(
    {
        "id": "search_failed_source_backfill",
        "name": query,
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": ["Bambu", "Lab", "P1S", "Combo", "Latvija"],
        "seed_urls": [],
        "crawl": {
            "mode": "expedition",
            "max_pages_total": 3,
            "max_pages_per_domain": 1,
            "max_domains": 2,
            "max_depth": 1,
            "delay_seconds": 0,
            "respect_robots": False,
            "external_link_threshold": 45,
            "discover_sitemaps": False,
            "max_sitemap_urls_per_domain": 0,
        },
        "search": {
            "provider": "none",
            "max_queries": 1,
            "results_per_query": 5,
            "result_threshold": 35,
            "queries": [query],
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    }
)

provider = FakeSearchProvider(
    {
        query: [
            SearchHit(
                url="https://blocked-one.example/bambu-lab-p1s-combo",
                title="Bambu Lab P1S Combo Latvija",
                snippet="P1S Combo cena",
            ),
            SearchHit(
                url="https://blocked-two.example/bambu-lab-p1s-combo",
                title="Bambu Lab P1S Combo Latvija",
                snippet="P1S Combo cena",
            ),
            SearchHit(
                url="https://useful.example/bambu-lab-p1s-combo",
                title="Bambu Lab P1S Combo",
                snippet="P1S Combo cena",
            ),
        ]
    }
)

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=provider,
)
crawler.session = FakeSession(
    {
        "https://blocked-one.example/bambu-lab-p1s-combo": FakeResponse(
            url="https://blocked-one.example/bambu-lab-p1s-combo",
            text="<html><body>Forbidden</body></html>",
            status_code=403,
        ),
        "https://blocked-two.example/bambu-lab-p1s-combo": FakeResponse(
            url="https://blocked-two.example/bambu-lab-p1s-combo",
            text="<html><body>Forbidden</body></html>",
            status_code=403,
        ),
        "https://useful.example/bambu-lab-p1s-combo": FakeResponse(
            url="https://useful.example/bambu-lab-p1s-combo",
            text="<html><body>Bambu Lab P1S Combo 599 EUR</body></html>",
            status_code=200,
        ),
    }
)

result = crawler.crawl()

assert crawler.session.calls == [
    "https://blocked-one.example/bambu-lab-p1s-combo",
    "https://blocked-two.example/bambu-lab-p1s-combo",
    "https://useful.example/bambu-lab-p1s-combo",
]
assert result.domains["blocked-one.example"].status == "failed"
assert result.domains["blocked-two.example"].status == "failed"
assert result.domains["useful.example"].status == "active"
assert result.domains["useful.example"].pages_seen == 1
assert result.search_domains_activated == 3
assert any(
    decision.stage == "search_domain_backfill"
    and decision.target == "https://useful.example/bambu-lab-p1s-combo"
    for decision in result.adaptive_decisions
)

print("SEARCH FAILED SOURCE BACKFILL TEST OK")
