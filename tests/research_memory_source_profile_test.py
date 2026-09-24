from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.domains import DomainRecord
from spriditis.core.entities import MarketEntity
from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


DOMAIN = "market.example"
URL = "https://market.example/product/chair"


def project() -> ResearchProject:
    return ResearchProject.model_validate(
        {
            "id": "source_memory_repeat",
            "name": "Source memory repeat test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["chair"],
            "seed_urls": [URL],
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
            },
        }
    )


def save_run(
    db: Database,
    p: ResearchProject,
    *,
    with_entity: bool,
):
    run_id = db.start_run(p)
    result = ResearchRunResult(project_id=p.id)
    result.finished_at = datetime.now(timezone.utc).isoformat()
    result.visited_pages = 1
    result.domains = {
        DOMAIN: DomainRecord(
            domain=DOMAIN,
            status="active",
            discovered_via="seed",
            relevance_score=1.0,
            pages_seen=1,
            entities_found=1 if with_entity else 0,
            robots_status="allowed",
            reason="seed",
        )
    }
    result.page_visits = [
        PageVisit(
            url=URL,
            final_url=URL,
            domain=DOMAIN,
            source_type="seed",
            depth=0,
            priority=100,
            outcome="html_ok",
            http_status=200,
            content_type="text/html",
        )
    ]

    if with_entity:
        db.upsert_entity(
            p,
            run_id,
            MarketEntity(
                title="Ergonomic chair",
                source_url=URL,
                source_domain=DOMAIN,
                price=199.0,
                currency="EUR",
                extraction_method="json-ld",
                relevance_score=0.9,
            ),
        )

    db.save_domain_registry(p, run_id, result)
    db.save_page_visits(p, run_id, result)
    db.finish_run(run_id, result)
    return run_id


def main():
    p = project()

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "memory.db")
        try:
            db.save_project(p)
            save_run(db, p, with_entity=True)
            save_run(db, p, with_entity=False)

            profiles = db.source_profiles(p.id)
            row = next(item for item in profiles if item["domain"] == DOMAIN)

            assert row["pages_seen"] == 2
            assert row["entities_found"] == 1
            assert row["visit_count"] == 2
            assert row["crawl_runs"] == 2
            assert row["successful_visits"] == 2
            assert row["success_rate"] == 1.0
            assert row["observation_count"] == 1
            assert row["productive_runs"] == 1
            assert row["productive_run_rate"] == 0.5
            assert row["last_useful_at"]
        finally:
            db.close()

    print("RESEARCH MEMORY SOURCE PROFILE TEST OK")
    print("crawl_runs=2 productive_runs=1 productive_run_rate=0.50")
    print("pages=2 entities=1 observations=1")


if __name__ == "__main__":
    main()
