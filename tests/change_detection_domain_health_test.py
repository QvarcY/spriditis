from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "change_detection_domain_health",
    "name": "Change Detection domain health",
    "keywords": ["product"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


def visit(
    domain: str,
    *,
    outcome: str,
    http_status: int | None = None,
    path: str = "/",
) -> PageVisit:
    url = f"https://{domain}{path}"
    return PageVisit(
        url=url,
        final_url=url,
        domain=domain,
        source_type="seed",
        outcome=outcome,
        http_status=http_status,
        content_type="text/html",
    )


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 12
        db.save_project(project)

        run_a = db.start_run(project)
        result_a = ResearchRunResult(
            project_id=project.id,
            page_visits=[
                visit(
                    "fail.example",
                    outcome="html_ok",
                    http_status=200,
                ),
                visit(
                    "recover.example",
                    outcome="http_status",
                    http_status=503,
                ),
                visit(
                    "mixed.example",
                    outcome="html_ok",
                    http_status=200,
                ),
                visit(
                    "fourxx.example",
                    outcome="html_ok",
                    http_status=200,
                ),
                visit(
                    "robots.example",
                    outcome="html_ok",
                    http_status=200,
                ),
                visit(
                    "unsafe.example",
                    outcome="http_error:ConnectTimeout",
                ),
                visit(
                    "old-only.example",
                    outcome="html_ok",
                    http_status=200,
                ),
            ],
        )
        db.save_page_visits(project, run_a, result_a)

        run_b = db.start_run(project)
        result_b = ResearchRunResult(
            project_id=project.id,
            page_visits=[
                visit(
                    "fail.example",
                    outcome="http_error:ConnectTimeout",
                ),
                visit(
                    "recover.example",
                    outcome="html_ok",
                    http_status=200,
                ),
                visit(
                    "mixed.example",
                    outcome="http_status",
                    http_status=503,
                    path="/broken",
                ),
                visit(
                    "mixed.example",
                    outcome="non_html",
                    http_status=200,
                    path="/asset.pdf",
                ),
                visit(
                    "fourxx.example",
                    outcome="http_status",
                    http_status=404,
                ),
                visit(
                    "robots.example",
                    outcome="robots_blocked",
                ),
                visit(
                    "unsafe.example",
                    outcome="unsafe_redirect",
                    http_status=302,
                ),
                visit(
                    "new-only.example",
                    outcome="html_ok",
                    http_status=200,
                ),
            ],
        )
        db.save_page_visits(project, run_b, result_b)

        diff = db.compare_runs(project.id, run_a, run_b)

        assert diff["comparison_basis"] == {
            "entity_facts": "historical_observation_snapshots",
            "domain_health": "historical_page_visits",
            "feed_state": "historical_feed_snapshots",
            "identity": "current_canonical_membership",
        }
        assert diff["before_run"]["domain_count"] == 7
        assert diff["after_run"]["domain_count"] == 7

        assert diff["counts"] == {
            "NEW_ENTITY": 0,
            "ENTITY_DISAPPEARED": 0,
            "PRICE_DROP": 0,
            "PRICE_INCREASE": 0,
            "SELLER_CHANGED": 0,
            "DESCRIPTION_CHANGED": 0,
            "IMAGE_CHANGED": 0,
            "SOURCE_CHANGED": 0,
            "DOMAIN_FAILED": 1,
            "DOMAIN_RECOVERED": 1,
            "FEED_APPEARED": 0,
            "FEED_DISAPPEARED": 0,
            "FEED_NEW_ENTRIES": 0,
            "FEED_FAILED": 0,
            "FEED_RECOVERED": 0,
        }

        assert len(diff["events"]) == 2
        by_type = {
            event["change_type"]: event
            for event in diff["events"]
        }

        failed = by_type["DOMAIN_FAILED"]
        assert failed["source_domain"] == "fail.example"
        assert failed["before"] == {"state": "reachable"}
        assert failed["after"] == {"state": "failed"}
        assert len(failed["evidence"]["before_reachable_visit_ids"]) == 1
        assert len(failed["evidence"]["after_failure_visit_ids"]) == 1
        assert (
            failed["evidence"]["after_outcomes"][0]["outcome"]
            == "http_error:ConnectTimeout"
        )

        recovered = by_type["DOMAIN_RECOVERED"]
        assert recovered["source_domain"] == "recover.example"
        assert recovered["before"] == {"state": "failed"}
        assert recovered["after"] == {"state": "reachable"}
        assert (
            recovered["evidence"]["before_outcomes"][0]["http_status"]
            == 503
        )
        assert (
            recovered["evidence"]["after_outcomes"][0]["outcome"]
            == "html_ok"
        )

        event_domains = {
            event["source_domain"]
            for event in diff["events"]
        }

        # Mixed 5xx + successful reachability stays reachable.
        assert "mixed.example" not in event_domains

        # HTTP 4xx proves the server answered; it is not a domain outage.
        assert "fourxx.example" not in event_domains

        # Policy/safety-only outcomes are unknown, never failure/recovery.
        assert "robots.example" not in event_domains
        assert "unsafe.example" not in event_domains

        # A domain present in only one run has no transition evidence.
        assert "old-only.example" not in event_domains
        assert "new-only.example" not in event_domains
    finally:
        db.close()

print("CHANGE DETECTION DOMAIN HEALTH TEST OK")
print("domain_failed=reachable_to_transport_or_5xx_failure")
print("domain_recovered=failed_to_reachable")
print("http_4xx=reachable_not_failed")
print("robots_and_unsafe=unknown_no_event")
print("mixed_success_and_5xx=reachable_no_event")
print("one_run_only=no_transition_event")
print(f"schema_version={CURRENT_SCHEMA_VERSION}")
