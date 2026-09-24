from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.feeds import FeedState
from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "change_detection_feed",
    "name": "Change Detection feed",
    "keywords": ["product"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


def state(
    feed_url: str,
    *,
    status: str,
    new_entries: int,
    last_entry_id: str,
    last_error: str = "",
) -> FeedState:
    domain = feed_url.split("/")[2]
    return FeedState(
        feed_url=feed_url,
        domain=domain,
        feed_type="rss",
        status=status,
        last_entry_id=last_entry_id,
        last_checked="2026-09-24T20:00:00+00:00",
        last_success=(
            "2026-09-24T20:00:00+00:00"
            if status == "active"
            else ""
        ),
        entries_seen=max(new_entries, 1),
        new_entries=new_entries,
        last_error=last_error,
        first_seen="2026-09-24T18:00:00+00:00",
        last_seen="2026-09-24T20:00:00+00:00",
    )


feed_new = "https://new.example/feed.xml"
feed_fail = "https://fail.example/feed.xml"
feed_recover = "https://recover.example/feed.xml"
feed_steady = "https://steady.example/feed.xml"
feed_reset = "https://reset.example/feed.xml"
feed_old_only = "https://old-only.example/feed.xml"
feed_new_only = "https://new-only.example/feed.xml"
feed_unchecked_old = "https://unchecked.example/feed.xml"


def visit(domain: str) -> PageVisit:
    url = f"https://{domain}/"
    return PageVisit(
        url=url,
        final_url=url,
        domain=domain,
        source_type="seed",
        outcome="html_ok",
        http_status=200,
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
                visit("old-only.example"),
                visit("new-only.example"),
                visit("unchecked.example"),
            ],
        )
        result_a.feed_states = {
            feed_new: state(
                feed_new,
                status="active",
                new_entries=2,
                last_entry_id="entry-2",
            ),
            feed_fail: state(
                feed_fail,
                status="active",
                new_entries=0,
                last_entry_id="entry-a",
            ),
            feed_recover: state(
                feed_recover,
                status="error",
                new_entries=4,
                last_entry_id="entry-r",
                last_error="http_status:503",
            ),
            feed_steady: state(
                feed_steady,
                status="active",
                new_entries=8,
                last_entry_id="entry-s",
            ),
            feed_reset: state(
                feed_reset,
                status="active",
                new_entries=10,
                last_entry_id="entry-reset-a",
            ),
            feed_old_only: state(
                feed_old_only,
                status="active",
                new_entries=1,
                last_entry_id="entry-old",
            ),
            feed_unchecked_old: state(
                feed_unchecked_old,
                status="active",
                new_entries=1,
                last_entry_id="entry-unchecked",
            ),
        }
        db.save_page_visits(project, run_a, result_a)
        db.save_feed_states(project, run_a, result_a)

        run_b = db.start_run(project)
        result_b = ResearchRunResult(
            project_id=project.id,
            page_visits=[
                visit("old-only.example"),
                visit("new-only.example"),
            ],
        )
        result_b.feed_states = {
            feed_new: state(
                feed_new,
                status="active",
                new_entries=5,
                last_entry_id="entry-5",
            ),
            feed_fail: state(
                feed_fail,
                status="error",
                new_entries=0,
                last_entry_id="entry-a",
                last_error="http_error:ConnectTimeout",
            ),
            feed_recover: state(
                feed_recover,
                status="active",
                new_entries=4,
                last_entry_id="entry-r",
            ),
            feed_steady: state(
                feed_steady,
                status="active",
                new_entries=8,
                last_entry_id="entry-s",
            ),
            feed_reset: state(
                feed_reset,
                status="active",
                new_entries=2,
                last_entry_id="entry-reset-b",
            ),
            feed_new_only: state(
                feed_new_only,
                status="active",
                new_entries=3,
                last_entry_id="entry-new-only",
            ),
        }
        db.save_page_visits(project, run_b, result_b)
        db.save_feed_states(project, run_b, result_b)

        snapshots_a = db.feed_snapshots(project.id, run_a)
        snapshots_b = db.feed_snapshots(project.id, run_b)
        assert len(snapshots_a) == 7
        assert len(snapshots_b) == 6

        diff = db.compare_runs(project.id, run_a, run_b)

        assert diff["comparison_basis"] == {
            "entity_facts": "historical_observation_snapshots",
            "domain_health": "historical_page_visits",
            "feed_state": "historical_feed_snapshots",
            "identity": "current_canonical_membership",
        }
        assert diff["before_run"]["feed_count"] == 7
        assert diff["after_run"]["feed_count"] == 6

        assert diff["counts"] == {
            "NEW_ENTITY": 0,
            "ENTITY_DISAPPEARED": 0,
            "PRICE_DROP": 0,
            "PRICE_INCREASE": 0,
            "SELLER_CHANGED": 0,
            "DESCRIPTION_CHANGED": 0,
            "IMAGE_CHANGED": 0,
            "SOURCE_CHANGED": 0,
            "DOMAIN_FAILED": 0,
            "DOMAIN_RECOVERED": 0,
            "FEED_APPEARED": 1,
            "FEED_DISAPPEARED": 1,
            "FEED_NEW_ENTRIES": 1,
            "FEED_FAILED": 1,
            "FEED_RECOVERED": 1,
        }
        assert len(diff["events"]) == 5

        by_type = {
            event["change_type"]: event
            for event in diff["events"]
        }

        appeared = by_type["FEED_APPEARED"]
        assert appeared["source_url"] == feed_new_only
        assert appeared["before"] == {"observed": False}
        assert appeared["after"]["observed"] is True
        assert appeared["after"]["status"] == "active"

        disappeared = by_type["FEED_DISAPPEARED"]
        assert disappeared["source_url"] == feed_old_only
        assert disappeared["before"]["observed"] is True
        assert disappeared["after"] == {"observed": False}
        assert disappeared["evidence"]["after_domain_reachable_visit_ids"]

        new_event = by_type["FEED_NEW_ENTRIES"]
        assert new_event["source_url"] == feed_new
        assert new_event["before"]["new_entries_total"] == 2
        assert new_event["after"]["new_entries_total"] == 5
        assert new_event["evidence"]["new_entries_delta"] == 3

        failed = by_type["FEED_FAILED"]
        assert failed["source_url"] == feed_fail
        assert failed["before"]["status"] == "active"
        assert failed["after"]["status"] == "error"
        assert failed["after"]["last_error"] == "http_error:ConnectTimeout"

        recovered = by_type["FEED_RECOVERED"]
        assert recovered["source_url"] == feed_recover
        assert recovered["before"]["status"] == "error"
        assert recovered["after"]["status"] == "active"

        event_urls = {
            event["source_url"]
            for event in diff["events"]
        }
        assert feed_steady not in event_urls
        assert feed_reset not in event_urls
        assert feed_unchecked_old not in event_urls
        assert feed_old_only in event_urls
        assert feed_new_only in event_urls

        trace_a = db.trace_run(project.id, run_a)
        trace_b = db.trace_run(project.id, run_b)
        assert trace_a is not None
        assert trace_b is not None
        assert len(trace_a["feed_snapshots"]) == 7
        assert len(trace_b["feed_snapshots"]) == 6

        trace_a_by_id = {
            item["id"]: item
            for item in trace_a["feed_snapshots"]
        }
        trace_b_by_id = {
            item["id"]: item
            for item in trace_b["feed_snapshots"]
        }

        for event in diff["events"]:
            before_snapshot_id = event["evidence"].get("before_snapshot_id")
            after_snapshot_id = event["evidence"].get("after_snapshot_id")

            if before_snapshot_id is not None:
                assert before_snapshot_id in trace_a_by_id
                assert (
                    trace_a_by_id[before_snapshot_id]["feed_url"]
                    == event["source_url"]
                )
            if after_snapshot_id is not None:
                assert after_snapshot_id in trace_b_by_id
                assert (
                    trace_b_by_id[after_snapshot_id]["feed_url"]
                    == event["source_url"]
                )

        assert (
            trace_b_by_id[
                new_event["evidence"]["after_snapshot_id"]
            ]["new_entries"]
            == 5
        )
        assert (
            trace_b_by_id[
                failed["evidence"]["after_snapshot_id"]
            ]["last_error"]
            == "http_error:ConnectTimeout"
        )
    finally:
        db.close()

print("CHANGE DETECTION FEED TEST OK")
print("events=appeared+disappeared+new_entries+failed+recovered")
print("new_entries=cumulative_positive_delta")
print("counter_reset=no_event")
print("disappeared=requires_later_reachable_domain")
print("unchecked_domain=no_disappearance_event")
print("one_run_only=no_transition_event")
print("feed_evidence=historical_feed_snapshots")
print("trace_links=event_snapshot_ids_resolve")
print(f"schema_version={CURRENT_SCHEMA_VERSION}")
