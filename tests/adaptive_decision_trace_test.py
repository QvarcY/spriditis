from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


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
    "id": "adaptive_decision_trace",
    "name": "Adaptive Decision Trace",
    "keywords": ["ergonomic chair"],
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
        "queries": ["ergonomic chair"],
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

target_url = "https://trace.example/product/ergonomic-chair/item"
provider = FakeSearchProvider({
    "ergonomic chair": [
        SearchHit(
            url=target_url,
            title="Ergonomic chair",
            snippet="Ergonomic chair",
        ),
    ],
})

query_memory = [
    {
        "provider": "fake",
        "query_text": "ergonomic chair",
        "productive_domain_rate": 1.0,
        "productive_domains": 1,
        "unique_domains": 1,
        "runs": 2,
    },
]

source_profiles = [
    {
        "domain": "trace.example",
        "status": "active",
        "crawl_runs": 2,
        "productive_runs": 2,
        "productive_run_rate": 1.0,
        "entity_yield": 0.5,
        "success_rate": 1.0,
        "is_stale": False,
    },
]

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=provider,
    query_memory=query_memory,
    source_profiles=source_profiles,
)
crawler.session = FakeSession({
    target_url: "<html><body>end</body></html>",
})
result = crawler.crawl()

stages = [item.stage for item in result.adaptive_decisions]
assert stages == [
    "query_priority",
    "search_result_priority",
    "stop",
]

query_decision = result.adaptive_decisions[0]
assert query_decision.target == "ergonomic chair"
assert query_decision.signals["position"] == 1
assert query_decision.signals["memory_state"] == "productive"
assert query_decision.signals["productive_domain_rate"] == 1.0

source_decision = result.adaptive_decisions[1]
assert source_decision.target == target_url
assert source_decision.signals["position"] == 1
assert source_decision.signals["source_memory_state"] == "productive_fresh"
assert source_decision.signals["productive_run_rate"] == 1.0
assert source_decision.signals["bm25"] > 0

stop_decision = result.adaptive_decisions[2]
assert stop_decision.decision == "max_pages"
assert stop_decision.signals["visited_pages"] == 1
assert stop_decision.signals["max_pages_total"] == 1

with TemporaryDirectory() as tmp:
    db = Database(Path(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        db.save_project(project)
        run_id = db.start_run(project)
        db.save_domain_registry(project, run_id, result)
        db.save_page_visits(project, run_id, result)
        db.save_adaptive_decisions(project, run_id, result)
        db.finish_run(run_id, result)

        trace = db.trace_run(project.id, run_id)
        assert trace is not None
        persisted = trace["adaptive_decisions"]

        assert [item["sequence"] for item in persisted] == [1, 2, 3]
        assert [item["stage"] for item in persisted] == stages
        assert persisted[0]["signals"]["memory_state"] == "productive"
        assert (
            persisted[1]["signals"]["source_memory_state"]
            == "productive_fresh"
        )
        assert persisted[2]["decision"] == "max_pages"
        assert persisted[2]["signals"]["visited_pages"] == 1
    finally:
        db.close()

print("ADAPTIVE DECISION TRACE TEST OK")
print("stages=query_priority > search_result_priority > stop")
print(f"schema_version={CURRENT_SCHEMA_VERSION}")
print("sqlite_roundtrip=ok")
