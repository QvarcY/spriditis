from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(
        _BootstrapPath(__file__)
        .resolve()
        .parents[1]
    ),
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


topic = (
    "Opel Zafira 2005 cenas automašīnām "
    "ar tehnisko apskati"
)

constraint_query = (
    "Opel Zafira 2005 tehnisko apskati"
)

project = ResearchProject.model_validate(
    {
        "id": "global-domain-budget-test",
        "name": topic,
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": [
            "Opel",
            "Zafira",
            "2005",
            "cenas",
            "automašīnām",
            "tehnisko",
            "apskati",
        ],
        "seed_urls": [],
        "crawl": {
            "mode": "expedition",
            "max_pages_total": 9,
            "max_pages_per_domain": 4,
            "max_domains": 3,
            "max_depth": 2,
            "delay_seconds": 0,
            "respect_robots": False,
            "external_link_threshold": 45,
            "discover_sitemaps": False,
            "max_sitemap_urls_per_domain": 0,
        },
        "search": {
            "provider": "none",
            "max_queries": 2,
            "results_per_query": 5,
            "result_threshold": 35,
            "safesearch": 1,
            "queries": [topic],
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
            "required_evidence_terms": [
                "2005",
                "tehnisk",
                "apskat",
            ],
        },
    }
)


provider = FakeSearchProvider(
    {
        topic: [
            SearchHit(
                url=(
                    "https://motorfy.example/"
                    "auto/opel-zafira-2005"
                ),
                title="Opel Zafira 2005 1500 EUR",
                snippet=(
                    "Apskati detalizēto tehnisko "
                    "aprakstu"
                ),
            ),
            SearchHit(
                url=(
                    "https://auto-abc.example/"
                    "Opel-Zafira/g826-2005"
                ),
                title="Opel Zafira 2005",
                snippet=(
                    "tehniskie dati un cenas"
                ),
            ),
            SearchHit(
                url=(
                    "https://csdd.example/"
                    "tehniska-apskate/maksajumi"
                ),
                title=(
                    "Maksājumi par tehnisko apskati"
                ),
                snippet="Opel Zafira",
            ),
        ],
        constraint_query: [
            SearchHit(
                url=(
                    "https://motorfy.example/"
                    "auto/opel-zafira-2005-b"
                ),
                title="Opel Zafira 2005 1500 EUR",
                snippet=(
                    "Apskati detalizēto tehnisko "
                    "aprakstu"
                ),
            ),
            SearchHit(
                url=(
                    "https://ss.example/"
                    "archive/opel/zafira"
                ),
                title="Opel Zafira sludinājumi",
                snippet=(
                    "2005 gada Opel Zafira ar "
                    "svaigu tehnisko apskati "
                    "1300 EUR"
                ),
            ),
        ],
    }
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
    search_provider=provider,
)

frontier = URLFrontier()
registry = DomainRegistry(project)
result = ResearchRunResult(
    project_id=project.id
)

crawler._seed_from_search(
    frontier,
    registry,
    result,
)


active = {
    domain
    for domain, record in registry.records.items()
    if record.status == "active"
}

print("ACTIVE DOMAINS:", sorted(active))

for domain, record in sorted(
    registry.records.items()
):
    print(
        domain,
        record.status,
        record.relevance_score,
        record.reason,
    )


assert "motorfy.example" in active
assert "ss.example" in active

assert (
    registry.records["ss.example"].reason
    == "search_relevance_threshold"
)

assert (
    registry.records["csdd.example"].status
    == "candidate"
)

assert (
    registry.records["csdd.example"].reason
    == "domain_budget_reached"
)

assert len(active) == 3

budget_decisions = [
    d
    for d in result.adaptive_decisions
    if d.stage == "search_domain_budget"
]

assert len(budget_decisions) == 1

assert (
    budget_decisions[0]
    .signals["strategy"]
    == "all_queries_before_activation"
)

print(
    "SEARCH GLOBAL DOMAIN BUDGET TEST OK"
)
