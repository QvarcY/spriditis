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

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            return FakeResponse(
                url=url,
                text="<html><body>not found</body></html>",
                status_code=404,
            )
        return FakeResponse(url=url, text=self.pages[url])


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


def project():
    return ResearchProject.model_validate(
        {
            "id": "controlled_discovery",
            "name": "Controlled discovery",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": [
                "ergonomic",
                "office chair",
                "chair",
            ],
            "negative_keywords": [],
            "seed_urls": [
                "https://seed.example/catalog"
            ],
            "crawl": {
                "mode": "discovery",
                "max_pages_total": 5,
                "max_pages_per_domain": 1,
                "max_domains": 2,
                "max_depth": 4,
                "delay_seconds": 0,
                "respect_robots": False,
                "external_link_threshold": 45,
                "discover_sitemaps": False,
                "max_sitemap_urls_per_domain": 0,
            },
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
                "min_relevance_score": 0.35,
                "categories": ["chair"],
                "desired_attributes": [],
            },
        }
    )


def settings():
    return AppSettings(
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
        user_agent="SpriditisTest/1.0",
        request_timeout_seconds=1,
    )


def main():
    pages = {
        "https://seed.example/catalog": """
        <html><body>
          <a href="https://relevant.example/product/ergonomic-office-chair">
            ergonomic office chair
          </a>
          <a href="https://third.example/product/ergonomic-office-chair">
            ergonomic office chair
          </a>
          <a href="https://facebook.com/ergonomic-office-chair">
            ergonomic office chair
          </a>
        </body></html>
        """,
        "https://relevant.example/product/ergonomic-office-chair": """
        <html><body>
          <h1>Relevant domain reached</h1>
          <a href="/product/second-chair">office chair</a>
        </body></html>
        """,
        "https://relevant.example/product/second-chair": """
        <html><body>
          This page must not be visited because max_pages_per_domain=1.
        </body></html>
        """,
    }

    crawler = ResearchCrawler(
        settings(),
        project(),
        NoOpAI(),
    )
    fake = FakeSession(pages)
    crawler.session = fake

    result = crawler.crawl()

    assert result.visited_pages == 2
    assert fake.calls == [
        "https://seed.example/catalog",
        "https://relevant.example/product/ergonomic-office-chair",
    ]

    assert result.domains["seed.example"].status == "active"
    assert result.domains["relevant.example"].status == "active"
    assert result.domains["relevant.example"].pages_seen == 1

    assert result.domains["third.example"].status == "candidate"
    assert result.domains["third.example"].reason == "domain_budget_reached"

    assert result.domains["facebook.com"].status == "blocked"
    assert result.domains["facebook.com"].reason == "blocked_host"

    activated = [
        item for item in result.domain_discoveries
        if item.action == "activated"
    ]
    assert len(activated) == 1
    assert activated[0].target_domain == "relevant.example"

    budget_candidates = [
        item for item in result.domain_discoveries
        if item.reason == "domain_budget_reached"
    ]
    assert len(budget_candidates) == 1
    assert budget_candidates[0].target_domain == "third.example"

    blocked = [
        item for item in result.domain_discoveries
        if item.action == "blocked"
    ]
    assert len(blocked) == 1
    assert blocked[0].target_domain == "facebook.com"

    print("CONTROLLED DISCOVERY INTEGRATION TEST OK")
    print("visited_pages=2")
    print("activated=relevant.example")
    print("candidate_due_to_budget=third.example")
    print("blocked=facebook.com")


if __name__ == "__main__":
    main()
