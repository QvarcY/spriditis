from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit
from spriditis.storage.database import Database


QUERY = "ergonomic chair"
PRODUCTIVE_URL = "https://productive.example/product/ergonomic-chair/item"
UNTESTED_URL = "https://untested.example/product/ergonomic-chair/item"


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
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url not in self.pages:
            return FakeResponse(
                url=url,
                text="<html><body>not found</body></html>",
                status_code=404,
            )
        return FakeResponse(
            url=url,
            text=self.pages[url],
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


project = ResearchProject.model_validate(
    {
        "id": "watch_research_memory",
        "name": "Watch Research Memory",
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["en"],
        "countries": ["LV"],
        "keywords": ["ergonomic chair"],
        "negative_keywords": [],
        "seed_urls": [],
        "crawl": {
            "mode": "expedition",
            "max_pages_total": 1,
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
            "safesearch": 1,
            "queries": [QUERY],
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    }
)


def settings(db_path):
    return AppSettings(
        gemini_api_key="",
        gemini_model="none",
        gemini_batch_size=10,
        gemini_requests_per_minute=5,
        gemini_max_retries=0,
        gemini_retry_base_seconds=1.0,
        db_path=db_path,
        legacy_db_path=None,
        report_dir=db_path.parent / "reports",
        smtp_host="",
        smtp_port=465,
        smtp_user="",
        smtp_app_password="",
        report_to="",
        send_email=False,
        user_agent="SpriditisWatchMemoryTest/1.0",
        request_timeout_seconds=1,
    )


PRODUCT_HTML = """
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Ergonomic chair",
  "offers": {
    "@type": "Offer",
    "price": "199.00",
    "priceCurrency": "EUR"
  }
}
</script>
</head>
<body><h1>Ergonomic chair</h1></body>
</html>
"""


with TemporaryDirectory() as tmp:
    db_path = _BootstrapPath(tmp) / "spriditis.db"
    app_settings = settings(db_path)
    db = Database(db_path)

    try:
        db.save_project(project)

        # Cycle 1: no prior Research Memory. A productive source is found.
        provider_a = FakeSearchProvider(
            {
                QUERY: [
                    SearchHit(
                        url=PRODUCTIVE_URL,
                        title="Ergonomic chair",
                        snippet="ergonomic chair product",
                    ),
                ],
            }
        )
        crawler_a = ResearchCrawler(
            app_settings,
            project,
            NoOpAI(),
            search_provider=provider_a,
            query_memory=db.query_memory(project.id),
            source_profiles=db.source_profiles(project.id),
            domain_states=db.load_domain_states(project.id),
            feed_states=db.load_feed_states(project.id),
        )
        session_a = FakeSession({PRODUCTIVE_URL: PRODUCT_HTML})
        crawler_a.session = session_a
        result_a = crawler_a.crawl()

        assert result_a.visited_pages == 1
        assert len(result_a.entities) == 1
        assert session_a.calls == [PRODUCTIVE_URL]

        run_a = db.start_run(project)
        for entity in result_a.entities:
            db.upsert_entity(project, run_a, entity)
        db.save_domain_registry(project, run_a, result_a)
        db.save_feed_states(project, run_a, result_a)
        db.save_page_visits(project, run_a, result_a)
        db.save_adaptive_decisions(project, run_a, result_a)
        db.finish_run(run_a, result_a)

        query_memory = db.query_memory(project.id)
        source_profiles = db.source_profiles(project.id)

        assert len(query_memory) == 1
        assert query_memory[0]["query_text"] == QUERY
        assert query_memory[0]["productive_domains"] == 1

        productive_profile = next(
            item
            for item in source_profiles
            if item["domain"] == "productive.example"
        )
        assert productive_profile["productive_runs"] == 1
        assert productive_profile["productive_run_rate"] == 1.0
        assert productive_profile["entity_yield"] > 0

        # Cycle 2: provider intentionally puts the untested source first.
        # Persisted Research Memory must promote the known productive source.
        provider_b = FakeSearchProvider(
            {
                QUERY: [
                    SearchHit(
                        url=UNTESTED_URL,
                        title="Ergonomic chair",
                        snippet="ergonomic chair product",
                    ),
                    SearchHit(
                        url=PRODUCTIVE_URL,
                        title="Ergonomic chair",
                        snippet="ergonomic chair product",
                    ),
                ],
            }
        )
        crawler_b = ResearchCrawler(
            app_settings,
            project,
            NoOpAI(),
            search_provider=provider_b,
            query_memory=db.query_memory(project.id),
            source_profiles=db.source_profiles(project.id),
            domain_states=db.load_domain_states(project.id),
            feed_states=db.load_feed_states(project.id),
        )
        session_b = FakeSession(
            {
                PRODUCTIVE_URL: PRODUCT_HTML,
                UNTESTED_URL: "<html><body>untested</body></html>",
            }
        )
        crawler_b.session = session_b
        result_b = crawler_b.crawl()

        assert result_b.visited_pages == 1
        assert session_b.calls == [PRODUCTIVE_URL]

        query_decisions = [
            item
            for item in result_b.adaptive_decisions
            if item.stage == "query_priority"
        ]
        assert len(query_decisions) == 1
        assert query_decisions[0].target == QUERY
        assert query_decisions[0].signals["memory_state"] == "productive"
        assert (
            query_decisions[0].signals["productive_domain_rate"]
            > 0
        )

        source_decisions = [
            item
            for item in result_b.adaptive_decisions
            if item.stage == "search_result_priority"
        ]
        assert len(source_decisions) == 2
        assert source_decisions[0].target == PRODUCTIVE_URL
        assert (
            source_decisions[0].signals["source_memory_state"]
            == "productive_fresh"
        )
        assert source_decisions[0].signals["productive_run_rate"] == 1.0
        assert source_decisions[1].target == UNTESTED_URL
        assert (
            source_decisions[1].signals["source_memory_state"]
            == "untested"
        )

        run_b = db.start_run(project)
        for entity in result_b.entities:
            db.upsert_entity(project, run_b, entity)
        db.save_domain_registry(project, run_b, result_b)
        db.save_feed_states(project, run_b, result_b)
        db.save_page_visits(project, run_b, result_b)
        db.save_adaptive_decisions(project, run_b, result_b)
        db.finish_run(run_b, result_b)

        trace_b = db.trace_run(project.id, run_b)
        assert trace_b is not None
        persisted = trace_b["adaptive_decisions"]

        query_trace = next(
            item for item in persisted
            if item["stage"] == "query_priority"
        )
        assert query_trace["signals"]["memory_state"] == "productive"

        source_trace = [
            item for item in persisted
            if item["stage"] == "search_result_priority"
        ]
        assert source_trace[0]["target"] == PRODUCTIVE_URL
        assert (
            source_trace[0]["signals"]["source_memory_state"]
            == "productive_fresh"
        )
    finally:
        db.close()


print("WATCH RESEARCH MEMORY TEST OK")
print("cycle1=productive_history_persisted")
print("cycle2=query_memory_reused")
print("cycle2=source_profile_reused")
print("query_memory_state=productive")
print("source_memory_state=productive_fresh")
print("provider_order=overridden_by_memory")
print("decision_trace=persisted")
