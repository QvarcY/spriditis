from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.crawler.discovery import DomainRegistry
from spriditis.crawler.frontier import URLFrontier
from spriditis.core.run import ResearchRunResult
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit


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

project = ResearchProject.model_validate(
    {
        "id": "target_relevance_test",
        "name": "Bambu Lab P1S Combo",
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": [
            "Bambu",
            "Lab",
            "P1S",
            "Combo",
            "Latvija",
            "cena",
        ],
        "analysis": {
            "target_identity_terms": ["P1S", "Combo"],
            "target_identity_anchor_terms": ["P1S"],
        },
    }
)

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({}),
)

ranked = crawler._rank_search_hits(
    [
        SearchHit(
            url="https://generic.example/bambu-lab",
            title="Bambu Lab 3D printeri Latvijas veikalos",
            snippet="Salīdzini cenas un piedāvājumus.",
        ),
        SearchHit(
            url="https://wrong.example/bambu-lab-p2s-combo",
            title="Bambu Lab P2S Combo cena",
            snippet="Jauns modelis Latvijas veikalā.",
        ),
        SearchHit(
            url="https://right.example/bambu-lab-p1s-combo",
            title="Bambu Lab P1S Combo cena",
            snippet="P1S Combo piedāvājums Latvijā.",
        ),
    ],
    "Atrodi Latvijas veikalos Bambu Lab P1S Combo piedāvājumus",
)

assert ranked[0].hit.url == "https://right.example/bambu-lab-p1s-combo"
assert ranked[0].target_identity_matches == 2
assert ranked[0].target_identity_anchor_matches == 1
assert ranked[1].hit.url == "https://wrong.example/bambu-lab-p2s-combo"
assert ranked[2].hit.url == "https://generic.example/bambu-lab"

# Generic historical productivity must not outrank the requested model.
crawler.source_profiles["wrong.example"] = {
    "productive_runs": 10, "crawl_runs": 10,
    "productive_run_rate": 1.0, "entity_yield": 100.0,
}
ranked = crawler._rank_search_hits([item.hit for item in reversed(ranked)], "P1S Combo")
assert ranked[0].hit.url == "https://right.example/bambu-lab-p1s-combo"

# The global pool, not only each provider result list, must keep that priority.
project.crawl.mode = "expedition"
project.crawl.max_domains = 1
project.search.max_queries = 1
project.search.queries = ["P1S Combo"]
crawler.search_provider = FakeSearchProvider({"P1S Combo": [item.hit for item in ranked]})
registry = DomainRegistry(project)
crawler._seed_from_search(URLFrontier(), registry, ResearchRunResult(project_id=project.id))
assert registry.run_active_domains == {"right.example"}

print("SEARCH TARGET RELEVANCE TEST OK")
