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
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers = {}

    def get(self, url, **kwargs):
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


def _project() -> ResearchProject:
    return ResearchProject.model_validate(
        {
            "id": "progress-callback-test",
            "name": "Progress callback test",
            "keywords": ["ergonomic", "office", "chair"],
            "seed_urls": ["https://seed.example/catalog"],
            "crawl": {
                "mode": "discovery",
                "max_pages_total": 3,
                "max_pages_per_domain": 2,
                "max_domains": 2,
                "max_depth": 2,
                "delay_seconds": 0,
                "respect_robots": False,
                "external_link_threshold": 30,
                "discover_sitemaps": False,
                "discover_feeds": False,
            },
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
                "min_relevance_score": 0.0,
                "categories": ["chair"],
                "desired_attributes": [],
            },
        }
    )


def _settings() -> AppSettings:
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


PAGES = {
    "https://seed.example/catalog": """
    <html><body>
      <a href="https://shop.example/products/ergonomic-office-chair">
        ergonomic office chair
      </a>
    </body></html>
    """,
    "https://shop.example/products/ergonomic-office-chair": """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Ergonomic Office Chair",
          "offers": {
            "@type": "Offer",
            "price": "199.00",
            "priceCurrency": "EUR"
          }
        }
        </script>
      </head>
      <body><h1>Ergonomic Office Chair</h1></body>
    </html>
    """,
}


def _crawler(callback):
    crawler = ResearchCrawler(
        _settings(),
        _project(),
        NoOpAI(),
        progress_callback=callback,
    )
    crawler.session = FakeSession(PAGES)
    return crawler


def test_progress_callback_reports_structured_crawl_events():
    events: list[tuple[str, dict[str, object]]] = []

    result = _crawler(
        lambda kind, data: events.append((kind, data))
    ).crawl()

    assert result.visited_pages == 2
    kinds = [kind for kind, _ in events]

    assert kinds[0] == "source_activated"
    assert events[0][1] == {
        "domain": "seed.example",
        "origin": "seed",
    }

    page_events = [
        data for kind, data in events
        if kind == "page_checked"
    ]
    assert [item["domain"] for item in page_events] == [
        "seed.example",
        "shop.example",
    ]
    assert [item["visited_pages"] for item in page_events] == [1, 2]

    source_events = [
        data for kind, data in events
        if kind == "source_activated"
    ]
    assert {
        "domain": "shop.example",
        "origin": "link",
    } in source_events

    entity_events = [
        data for kind, data in events
        if kind == "entities_found"
    ]
    assert entity_events
    assert entity_events[-1]["domain"] == "shop.example"
    assert entity_events[-1]["count"] == 1
    assert entity_events[-1]["total"] == 1

    assert "analysis_started" in kinds
    assert kinds[-1] == "crawl_finished"
    assert events[-1][1]["visited_pages"] == 2
    assert events[-1][1]["entity_count"] == 1


def test_progress_callback_failure_does_not_break_research():
    def broken_callback(kind, data):
        raise RuntimeError("consumer failed")

    result = _crawler(broken_callback).crawl()

    assert result.visited_pages == 2
    assert len(result.entities) == 1
