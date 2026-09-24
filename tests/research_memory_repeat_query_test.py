from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.domains import DomainDiscovery, DomainRecord
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


QUERY = "ergonomic office chair"


def project() -> ResearchProject:
    return ResearchProject.model_validate(
        {
            "id": "query_memory_repeat",
            "name": "Query memory repeat test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["ergonomic", "chair"],
            "seed_urls": [],
            "crawl": {
                "mode": "expedition",
                "max_pages_total": 3,
                "max_pages_per_domain": 1,
                "max_domains": 1,
                "max_depth": 1,
                "delay_seconds": 0,
                "respect_robots": False,
                "discover_sitemaps": False,
                "max_sitemap_urls_per_domain": 0,
            },
            "search": {
                "provider": "none",
                "max_queries": 1,
                "results_per_query": 5,
                "result_threshold": 20,
                "safesearch": 1,
                "queries": [QUERY],
            },
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
            },
        }
    )


def discovery(domain: str, action: str, reason: str) -> DomainDiscovery:
    return DomainDiscovery(
        target_domain=domain,
        target_url=f"https://{domain}/result",
        relevance_score=0.8 if domain == "market.example" else 0.2,
        action=action,
        reason=reason,
        discovered_via="search_provider",
        provider="fake",
        query_text=QUERY,
    )


def save_run(
    db: Database,
    p: ResearchProject,
    *,
    market_action: str,
):
    run_id = db.start_run(p)
    result = ResearchRunResult(project_id=p.id)
    result.finished_at = datetime.now(timezone.utc).isoformat()
    result.search_queries_issued = 1
    result.search_results_seen = 3
    result.search_results_unique = 3
    result.search_domains_activated = 1 if market_action == "activated" else 0

    result.domains = {
        "market.example": DomainRecord(
            domain="market.example",
            status="active",
            discovered_via="search_provider",
            relevance_score=0.8,
            reason="search_relevance_threshold",
        ),
        "candidate.example": DomainRecord(
            domain="candidate.example",
            status="candidate",
            discovered_via="search_provider",
            relevance_score=0.2,
            reason="domain_budget_reached",
        ),
        "facebook.com": DomainRecord(
            domain="facebook.com",
            status="blocked",
            discovered_via="search_provider",
            relevance_score=0.2,
            reason="blocked_host",
        ),
    }

    result.domain_discoveries = [
        discovery(
            "market.example",
            market_action,
            (
                "search_relevance_threshold"
                if market_action == "activated"
                else "already_active"
            ),
        ),
        discovery(
            "candidate.example",
            "recorded",
            "domain_budget_reached",
        ),
        discovery(
            "facebook.com",
            "blocked",
            "blocked_host",
        ),
    ]

    db.save_domain_registry(p, run_id, result)
    db.finish_run(run_id, result)
    return run_id


def main():
    p = project()

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "memory.db")
        try:
            db.save_project(p)
            save_run(db, p, market_action="activated")
            save_run(db, p, market_action="known")

            rows = db.query_memory(p.id)
            assert len(rows) == 1
            row = rows[0]

            assert row["query_text"] == QUERY
            assert row["runs"] == 2
            assert row["result_events"] == 6
            assert row["unique_domains"] == 3
            assert row["activated"] == 1
            assert row["known"] == 1
            assert row["blocked"] == 2
            assert row["recorded"] == 2

            # First-activation rate falls on repeat runs and is retained only
            # as an auditable historical metric.
            assert abs(row["activation_rate"] - (1 / 6)) < 1e-9

            # Query yield stays stable because the same useful domain is still
            # productive when it is seen again as "known".
            assert row["productive_domains"] == 1
            assert row["blocked_domains"] == 1
            assert abs(row["productive_domain_rate"] - (1 / 3)) < 1e-9
        finally:
            db.close()

    print("RESEARCH MEMORY REPEAT QUERY TEST OK")
    print("runs=2 events=6 unique_domains=3")
    print("first_activation_rate=0.1667")
    print("productive_domain_rate=0.3333")


if __name__ == "__main__":
    main()
