from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


def project() -> ResearchProject:
    return ResearchProject.model_validate(
        {
            "id": "memory_duplicate_rate_test",
            "name": "Research Memory duplicate rate test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["chair"],
            "seed_urls": [],
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
            },
        }
    )


def save_search_run(
    db: Database,
    p: ResearchProject,
    *,
    raw: int,
    unique: int,
    duplicates: int,
    queries: int,
    errors: int = 0,
):
    run_id = db.start_run(p)
    result = ResearchRunResult(project_id=p.id)
    result.finished_at = datetime.now(timezone.utc).isoformat()
    result.search_queries_issued = queries
    result.search_results_seen = raw
    result.search_results_unique = unique
    result.search_results_duplicates = duplicates
    result.search_provider_errors = errors
    db.finish_run(run_id, result)
    return run_id


def main():
    p = project()

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "memory.db")
        try:
            db.save_project(p)

            first_run = save_search_run(
                db,
                p,
                raw=5,
                unique=3,
                duplicates=2,
                queries=2,
            )
            second_run = save_search_run(
                db,
                p,
                raw=4,
                unique=2,
                duplicates=1,
                queries=1,
                errors=1,
            )

            memory = db.search_duplication_memory(p.id)

            assert memory["scope"] == "normalized_search_url_across_run"
            assert memory["runs"] == 2
            assert memory["queries"] == 3
            assert memory["raw_results"] == 9
            assert memory["unique_results"] == 5
            assert memory["duplicates"] == 3
            assert memory["filtered_results"] == 1
            assert abs(memory["duplicate_rate"] - (3 / 9)) < 1e-9
            assert memory["provider_errors"] == 1

            assert len(memory["recent_runs"]) == 2

            latest = memory["recent_runs"][0]
            assert latest["run_id"] == second_run
            assert latest["raw_results"] == 4
            assert latest["unique_results"] == 2
            assert latest["duplicates"] == 1
            assert latest["filtered_results"] == 1
            assert latest["duplicate_rate"] == 0.25
            assert latest["provider_errors"] == 1

            older = memory["recent_runs"][1]
            assert older["run_id"] == first_run
            assert older["raw_results"] == 5
            assert older["unique_results"] == 3
            assert older["duplicates"] == 2
            assert older["filtered_results"] == 0
            assert older["duplicate_rate"] == 0.4
        finally:
            db.close()

    print("RESEARCH MEMORY DUPLICATE RATE TEST OK")
    print("runs=2 raw=9 unique=5 duplicates=3 filtered=1")
    print("duplicate_rate=0.3333")


if __name__ == "__main__":
    main()
