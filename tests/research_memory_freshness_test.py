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
AS_OF = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def main():
    project = ResearchProject.model_validate(
        {
            "id": "memory_freshness_test",
            "name": "Research Memory freshness test",
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

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "memory.db")
        try:
            db.save_project(project)
            run_id = db.start_run(project)

            result = ResearchRunResult(project_id=project.id)
            result.finished_at = AS_OF.isoformat()
            result.visited_pages = 1
            result.domains = {
                DOMAIN: DomainRecord(
                    domain=DOMAIN,
                    status="active",
                    discovered_via="seed",
                    relevance_score=1.0,
                    pages_seen=1,
                    entities_found=1,
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
                    visited_at="2026-09-22T12:00:00+00:00",
                )
            ]

            db.upsert_entity(
                project,
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
            db.save_domain_registry(project, run_id, result)
            db.save_page_visits(project, run_id, result)
            db.finish_run(run_id, result)

            db.conn.execute(
                """
                UPDATE domains
                SET last_seen=?, last_crawled=?
                WHERE project_id=? AND domain=?
                """,
                (
                    "2026-09-22T12:00:00+00:00",
                    "2026-09-22T12:00:00+00:00",
                    project.id,
                    DOMAIN,
                ),
            )
            db.conn.execute(
                """
                UPDATE observations
                SET observed_at=?
                WHERE project_id=? AND run_id=?
                """,
                (
                    "2026-08-15T12:00:00+00:00",
                    project.id,
                    run_id,
                ),
            )
            db.conn.commit()

            row = db.source_profiles(
                project.id,
                stale_after_days=30,
                as_of=AS_OF,
            )[0]

            assert row["age_since_last_useful_days"] == 40.0
            assert row["age_since_last_crawl_days"] == 2.0
            assert row["stale_reference"] == "last_useful_at"
            assert row["stale_age_days"] == 40.0
            assert row["stale_after_days"] == 30.0
            assert row["is_stale"] is True
            assert row["freshness"] == "stale"

            relaxed = db.source_profiles(
                project.id,
                stale_after_days=45,
                as_of=AS_OF,
            )[0]
            assert relaxed["is_stale"] is False
            assert relaxed["freshness"] == "fresh"

            explanation = db.explain_domain(
                project.id,
                DOMAIN,
                stale_after_days=30,
                as_of=AS_OF,
            )
            assert explanation is not None
            assert explanation["stale_reference"] == "last_useful_at"
            assert explanation["age_since_last_crawl_days"] == 2.0
            assert explanation["age_since_last_useful_days"] == 40.0
        finally:
            db.close()

    print("RESEARCH MEMORY FRESHNESS TEST OK")
    print("last_useful_age=40.0d last_crawl_age=2.0d")
    print("stale_after=30.0d freshness=stale")


if __name__ == "__main__":
    main()
