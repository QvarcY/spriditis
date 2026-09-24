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


def domain_project(
    project_id: str,
    *,
    max_pages_total: int = 10,
    diminishing_returns_window: int = 0,
    saturation_window: int = 0,
) -> ResearchProject:
    return ResearchProject.model_validate({
        "id": project_id,
        "name": project_id,
        "keywords": ["research"],
        "seed_urls": ["https://stop.example/start"],
        "crawl": {
            "mode": "domain",
            "max_pages_total": max_pages_total,
            "max_pages_per_domain": 10,
            "max_domains": 1,
            "max_depth": 5,
            "delay_seconds": 0,
            "respect_robots": False,
            "discover_sitemaps": False,
            "discover_feeds": False,
            "diminishing_returns_window": diminishing_returns_window,
            "saturation_window": saturation_window,
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


chain_pages = {
    "https://stop.example/start": """
        <html><body>
        <a href="/page-2">research next</a>
        </body></html>
    """,
    "https://stop.example/page-2": """
        <html><body>
        <a href="/page-3">research next</a>
        </body></html>
    """,
    "https://stop.example/page-3": """
        <html><body>
        <a href="/page-4">research next</a>
        </body></html>
    """,
    "https://stop.example/page-4": "<html><body>end</body></html>",
}


def run_domain(project: ResearchProject, pages: dict[str, str]):
    crawler = ResearchCrawler(
        settings,
        project,
        NoOpAI(),
    )
    crawler.session = FakeSession(pages)
    return crawler, crawler.crawl()


# Saturation: no new entities and no new active domains for two HTML pages.
crawler, result = run_domain(
    domain_project(
        "stop_saturation",
        saturation_window=2,
    ),
    chain_pages,
)
assert result.stop_reason == "saturation_reached"
assert result.visited_pages == 2
assert result.saturation_streak == 2
assert result.diminishing_returns_streak == 2
assert len(crawler.session.calls) == 2

# Diminishing returns: no new entities for two HTML pages.
crawler, result = run_domain(
    domain_project(
        "stop_diminishing",
        diminishing_returns_window=2,
    ),
    chain_pages,
)
assert result.stop_reason == "diminishing_returns"
assert result.visited_pages == 2
assert result.diminishing_returns_streak == 2
assert len(crawler.session.calls) == 2

# Hard page budget remains explicit.
crawler, result = run_domain(
    domain_project(
        "stop_max_pages",
        max_pages_total=1,
    ),
    chain_pages,
)
assert result.stop_reason == "max_pages"
assert result.visited_pages == 1

# Natural frontier exhaustion is also explicit.
crawler, result = run_domain(
    domain_project("stop_budget_exhausted"),
    {
        "https://stop.example/start": "<html><body>end</body></html>",
    },
)
assert result.stop_reason == "budget_exhausted"
assert result.visited_pages == 1

# Expedition domain budget has its own reason.
expedition = ResearchProject.model_validate({
    "id": "stop_max_domains",
    "name": "stop max domains",
    "keywords": ["ergonomic chair"],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 5,
        "max_pages_per_domain": 1,
        "max_domains": 1,
        "max_depth": 1,
        "delay_seconds": 0,
        "respect_robots": False,
        "discover_sitemaps": False,
        "discover_feeds": False,
    },
    "search": {
        "provider": "none",
        "max_queries": 1,
        "results_per_query": 5,
        "result_threshold": 35,
        "queries": ["ergonomic chair"],
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})

provider = FakeSearchProvider({
    "ergonomic chair": [
        SearchHit(
            url="https://one.example/product/ergonomic-chair/item",
            title="Ergonomic chair",
            snippet="Ergonomic chair",
        ),
        SearchHit(
            url="https://two.example/product/ergonomic-chair/item",
            title="Ergonomic chair",
            snippet="Ergonomic chair",
        ),
    ],
})

crawler = ResearchCrawler(
    settings,
    expedition,
    NoOpAI(),
    search_provider=provider,
)
crawler.session = FakeSession({
    "https://one.example/product/ergonomic-chair/item":
        "<html><body>end</body></html>",
})
result = crawler.crawl()

assert result.stop_reason == "max_domains"
assert result.visited_pages == 1
assert result.domains["two.example"].reason == "domain_budget_reached"

print("ADAPTIVE STOPPING TEST OK")
print(
    "STOP_REASON=saturation_reached | diminishing_returns | "
    "max_pages | max_domains | budget_exhausted"
)
print("adaptive_windows_default=disabled")
