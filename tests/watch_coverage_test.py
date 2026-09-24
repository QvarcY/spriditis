from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


project = ResearchProject.model_validate(
    {
        "id": "watch_coverage",
        "name": "Watch coverage",
        "keywords": ["product"],
        "seed_urls": [],
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    }
)


def entity(title: str, url: str) -> MarketEntity:
    return MarketEntity(
        title=title,
        source_url=url,
        source_domain=url.split("/")[2],
        price=10.0,
        currency="EUR",
        extraction_method="json-ld",
    )


def save_visits(db: Database, run_id: int, *urls: str) -> None:
    db.save_page_visits(
        project,
        run_id,
        ResearchRunResult(
            project_id=project.id,
            page_visits=[
                PageVisit(
                    url=url,
                    final_url=url,
                    domain=url.split("/")[2],
                    source_type="watch_coverage_test",
                    outcome="html_ok",
                    http_status=200,
                    content_type="text/html",
                )
                for url in urls
            ],
        ),
    )


def finish(db: Database, run_id: int) -> None:
    db.conn.execute(
        "UPDATE runs SET finished_at=? WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), run_id),
    )
    db.conn.commit()


# Scenario 1: different crawl-budget slice must not masquerade as change.
with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        db.save_project(project)

        stable = entity(
            "Stable Product",
            "https://watch.example/product/stable",
        )
        old_slice = entity(
            "Old Slice Product",
            "https://watch.example/product/old-slice",
        )
        new_slice = entity(
            "New Slice Product",
            "https://watch.example/product/new-slice",
        )

        run_a = db.start_run(project)
        db.upsert_entity(project, run_a, stable)
        db.upsert_entity(project, run_a, old_slice)
        save_visits(
            db,
            run_a,
            stable.source_url,
            old_slice.source_url,
        )
        finish(db, run_a)

        run_b = db.start_run(project)
        db.upsert_entity(project, run_b, stable)
        db.upsert_entity(project, run_b, new_slice)
        save_visits(
            db,
            run_b,
            stable.source_url,
            new_slice.source_url,
        )
        finish(db, run_b)

        raw = db.compare_runs(project.id, run_a, run_b)
        assert raw["counts"]["NEW_ENTITY"] == 1
        assert raw["counts"]["ENTITY_DISAPPEARED"] == 1

        watch = db.compare_with_previous_run(project.id, run_b)
        assert watch is not None
        assert watch["events"] == []
        assert watch["counts"]["NEW_ENTITY"] == 0
        assert watch["counts"]["ENTITY_DISAPPEARED"] == 0

        coverage = watch["coverage"]
        assert coverage["mode"] == "comparable_source_url_recheck"
        assert coverage["suppressed_event_count"] == 2
        assert coverage["suppressed_counts"] == {
            "NEW_ENTITY": 1,
            "ENTITY_DISAPPEARED": 1,
        }
        reasons = {
            item["change_type"]: item["reason"]
            for item in coverage["suppressed_events"]
        }
        assert reasons["NEW_ENTITY"] == (
            "source_url_not_rechecked_in_before_run"
        )
        assert reasons["ENTITY_DISAPPEARED"] == (
            "source_url_not_rechecked_in_after_run"
        )
    finally:
        db.close()


# Scenario 2: comparable URL rechecks support real presence changes.
with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        db.save_project(project)

        stable = entity(
            "Stable Product",
            "https://watch.example/product/stable",
        )
        disappeared = entity(
            "Disappeared Product",
            "https://watch.example/product/disappeared",
        )
        appeared = entity(
            "Appeared Product",
            "https://watch.example/product/appeared",
        )

        run_a = db.start_run(project)
        db.upsert_entity(project, run_a, stable)
        db.upsert_entity(project, run_a, disappeared)
        save_visits(
            db,
            run_a,
            stable.source_url,
            disappeared.source_url,
            appeared.source_url,
        )
        finish(db, run_a)

        run_b = db.start_run(project)
        db.upsert_entity(project, run_b, stable)
        db.upsert_entity(project, run_b, appeared)
        save_visits(
            db,
            run_b,
            stable.source_url,
            disappeared.source_url,
            appeared.source_url,
        )
        finish(db, run_b)

        watch = db.compare_with_previous_run(project.id, run_b)
        assert watch is not None
        assert watch["counts"]["NEW_ENTITY"] == 1
        assert watch["counts"]["ENTITY_DISAPPEARED"] == 1
        assert len(watch["events"]) == 2
        assert watch["coverage"]["suppressed_event_count"] == 0
        assert {
            event["change_type"]
            for event in watch["events"]
        } == {
            "NEW_ENTITY",
            "ENTITY_DISAPPEARED",
        }
    finally:
        db.close()


print("WATCH COVERAGE TEST OK")
print("budget_slice_churn=suppressed")
print("new_entity=requires_prior_source_url_recheck")
print("disappearance=requires_later_source_url_recheck")
print("alpha8_raw_diff=unchanged")
print("coverage_mode=comparable_source_url_recheck")
