from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.cli import _parser
from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import Database


project = ResearchProject.model_validate(
    {
        "id": "watch_incremental",
        "name": "Watch incremental",
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


def finish(db: Database, run_id: int) -> None:
    db.conn.execute(
        "UPDATE runs SET finished_at=? WHERE id=?",
        (datetime.now(timezone.utc).isoformat(), run_id),
    )
    db.conn.commit()


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        db.save_project(project)

        item_a = entity(
            "Baseline Product",
            "https://watch.example/product/a",
        )
        item_b = entity(
            "New Product",
            "https://watch.example/product/b",
        )

        run_a = db.start_run(project)
        db.upsert_entity(project, run_a, item_a)
        finish(db, run_a)

        assert db.compare_with_previous_run(project.id, run_a) is None

        run_b = db.start_run(project)
        db.upsert_entity(project, run_b, item_a)
        db.upsert_entity(project, run_b, item_b)
        finish(db, run_b)

        diff_b = db.compare_with_previous_run(project.id, run_b)
        assert diff_b is not None
        assert diff_b["before_run"]["id"] == run_a
        assert diff_b["after_run"]["id"] == run_b
        assert diff_b["counts"]["NEW_ENTITY"] == 1
        assert len(diff_b["events"]) == 1
        assert diff_b["events"][0]["change_type"] == "NEW_ENTITY"

        abandoned = db.start_run(project)
        db.upsert_entity(
            project,
            abandoned,
            entity(
                "Interrupted Product",
                "https://watch.example/product/interrupted",
            ),
        )

        run_c = db.start_run(project)
        db.upsert_entity(project, run_c, item_a)
        db.upsert_entity(project, run_c, item_b)
        finish(db, run_c)

        diff_c = db.compare_with_previous_run(project.id, run_c)
        assert diff_c is not None
        assert diff_c["before_run"]["id"] == run_b
        assert diff_c["after_run"]["id"] == run_c
        assert diff_c["events"] == []

        args = _parser().parse_args(
            [
                "watch",
                "--project",
                "project.json",
                "--once",
            ]
        )
        assert args.command == "watch"
        assert args.project == "project.json"
        assert args.once is True
    finally:
        db.close()

print("WATCH INCREMENTAL TEST OK")
print("first_completed_run=baseline")
print("previous_completed_run=selected")
print("unfinished_run=ignored")
print("change_only_diff=new_entity")
print("watch_cli=once")
