from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(_BootstrapPath(__file__).resolve().parents[1]),
)

from pathlib import Path

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.crawler.discovery import DomainRegistry
from spriditis.crawler.engine import ResearchCrawler
from spriditis.crawler.frontier import URLFrontier
from spriditis.crawler.policy import text_relevance_score
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


# ------------------------------------------------------------------
# Production regression:
# useful SearXNG results all score below the legacy threshold.
# The expedition must still receive a safe ranked bootstrap.
# ------------------------------------------------------------------

topic = (
    "izpēti personalizētu lāzergravētu "
    "atslēgu piekariņu piedāvājumu"
)

project = ResearchProject.model_validate({
    "id": "ranked-bootstrap-fallback",
    "name": topic,
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["lv"],
    "countries": ["LV"],
    "keywords": [
        "personalizētu",
        "lāzergravētu",
        "atslēgu",
        "piekariņu",
    ],
    "negative_keywords": ["vakance"],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 6,
        "max_pages_per_domain": 3,
        "max_domains": 2,
        "max_depth": 2,
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
        "safesearch": 1,
        "queries": [topic],
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})

hits = [
    SearchHit(
        url="https://nela.example/keychain",
        title="Atslēgu piekariņš ar personalizētu tekstu",
        snippet="Dāvana pēc individuāla pasūtījuma.",
    ),
    SearchHit(
        url="https://lazerlux.example/engraving",
        title="Lāzergravētu dāvanu un atslēgu katalogs",
        snippet="Personalizēti izstrādājumi.",
    ),
    SearchHit(
        url="https://vacancies.example/jobs",
        title="Atslēgu piekariņu vakance",
        snippet="Darba sludinājums.",
    ),
]

for hit in hits[:2]:
    score = text_relevance_score(
        project,
        hit.url,
        f"{hit.title} {hit.snippet}",
    )
    assert 0 < score < project.search.result_threshold

crawler = ResearchCrawler(
    settings,
    project,
    NoOpAI(),
    search_provider=FakeSearchProvider({
        topic: hits,
    }),
)

frontier = URLFrontier()
registry = DomainRegistry(project)
result = ResearchRunResult(project_id=project.id)

crawler._seed_from_search(
    frontier,
    registry,
    result,
)

assert registry.run_active_domains == {
    "nela.example",
    "lazerlux.example",
}

assert (
    registry.records["nela.example"].reason
    == "search_ranked_bootstrap_fallback"
)
assert (
    registry.records["lazerlux.example"].reason
    == "search_ranked_bootstrap_fallback"
)

assert "vacancies.example" not in registry.run_active_domains
assert result.search_domains_activated == 2

assert {
    item.source_type
    for item in frontier.pending_items()
} == {"search_ranked_bootstrap"}

fallback_decisions = [
    item
    for item in result.adaptive_decisions
    if item.stage == "search_bootstrap_fallback"
]

assert len(fallback_decisions) == 2


# ------------------------------------------------------------------
# Safety guard:
# a specific-target research must not bootstrap a generic wrong-model
# result merely because the provider gave it a positive score.
# ------------------------------------------------------------------

target_topic = "Bambu Lab P1S Combo"

target_project = ResearchProject.model_validate({
    "id": "ranked-bootstrap-target-guard",
    "name": target_topic,
    "research_type": "product_market",
    "entity_type": "product",
    "languages": ["lv"],
    "countries": ["LV"],
    "keywords": [
        "Bambu",
        "Lab",
        "P1S",
        "Combo",
    ],
    "seed_urls": [],
    "crawl": {
        "mode": "expedition",
        "max_pages_total": 4,
        "max_pages_per_domain": 2,
        "max_domains": 1,
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
        "result_threshold": 95,
        "safesearch": 1,
        "queries": [target_topic],
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
        "target_identity_terms": ["P1S", "Combo"],
        "target_identity_anchor_terms": ["P1S"],
    },
})

generic_hit = SearchHit(
    url="https://generic.example/bambu-printers",
    title="Bambu Lab 3D printeri",
    snippet="Plašs Bambu Lab printeru piedāvājums.",
    provider_score=10.0,
)

target_crawler = ResearchCrawler(
    settings,
    target_project,
    NoOpAI(),
    search_provider=FakeSearchProvider({
        target_topic: [generic_hit],
    }),
)

target_frontier = URLFrontier()
target_registry = DomainRegistry(target_project)

target_crawler._seed_from_search(
    target_frontier,
    target_registry,
    ResearchRunResult(project_id=target_project.id),
)

assert not target_frontier
assert not target_registry.run_active_domains

print("SEARCH RANKED BOOTSTRAP FALLBACK TEST OK")
print("generic_market_fallback=PASS")
print("specific_target_guard=PASS")
