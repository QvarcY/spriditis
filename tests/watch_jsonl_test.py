from __future__ import annotations

import json
import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.cli import (
    _append_watch_jsonl,
    _load_watch_project,
    _parser,
)


def diff_with_events(events: list[dict]) -> dict:
    return {
        "before_run": {
            "id": 10,
            "finished_at": "2026-09-25T00:00:00+00:00",
        },
        "after_run": {
            "id": 11,
            "finished_at": "2026-09-25T01:00:00+00:00",
        },
        "events": events,
    }


event_a = {
    "change_type": "PRICE_DROP",
    "title": "Koka dāvana",
    "entity_key": "entity-a",
    "source_url": "https://example.com/a",
    "source_domain": "example.com",
    "before": {"price": 20.0, "currency": "EUR"},
    "after": {"price": 18.0, "currency": "EUR"},
    "evidence": {"reason": "historical_observation_snapshots"},
}

event_b = {
    "change_type": "NEW_ENTITY",
    "title": "Jauna prece",
    "entity_key": "entity-b",
    "source_url": "https://example.com/b",
    "source_domain": "example.com",
    "before": {},
    "after": {"entity_keys": ["entity-b"]},
    "evidence": {},
}


with TemporaryDirectory() as tmp:
    root = _BootstrapPath(tmp)
    output = root / "nested" / "watch.jsonl"

    assert _append_watch_jsonl(
        output,
        project_id="watch_jsonl",
        cycle_number=1,
        diff=None,
    ) == 0
    assert not output.exists()

    assert _append_watch_jsonl(
        output,
        project_id="watch_jsonl",
        cycle_number=2,
        diff=diff_with_events([]),
    ) == 0
    assert not output.exists()

    assert _append_watch_jsonl(
        output,
        project_id="watch_jsonl",
        cycle_number=3,
        diff=diff_with_events([event_a, event_b]),
    ) == 2

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["schema"] == "spriditis.watch.change.v1"
    assert first["record_type"] == "change_event"
    assert first["project_id"] == "watch_jsonl"
    assert first["cycle"] == 3
    assert first["before_run_id"] == 10
    assert first["after_run_id"] == 11
    assert first["before_finished_at"] == "2026-09-25T00:00:00+00:00"
    assert first["after_finished_at"] == "2026-09-25T01:00:00+00:00"
    assert first["event"]["change_type"] == "PRICE_DROP"
    assert first["event"]["title"] == "Koka dāvana"
    assert second["event"]["change_type"] == "NEW_ENTITY"

    assert _append_watch_jsonl(
        output,
        project_id="watch_jsonl",
        cycle_number=4,
        diff=diff_with_events([event_b]),
    ) == 1

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert json.loads(lines[2])["cycle"] == 4

    try:
        _load_watch_project(root / "missing-project.json")
    except ValueError as exc:
        assert "Projekta fails nav atrasts" in str(exc)
    else:
        raise AssertionError("Missing watch project must fail cleanly")

args = _parser().parse_args(
    [
        "watch",
        "--project",
        "projects/example.json",
        "--once",
        "--jsonl",
        "exports/changes.jsonl",
    ]
)
assert args.jsonl == "exports/changes.jsonl"

print("WATCH JSONL TEST OK")
print("baseline=no_output")
print("no_changes=no_output")
print("one_event=one_jsonl_line")
print("append=preserved")
print("utf8=preserved")
print("schema=spriditis.watch.change.v1")
print("missing_project=clean_error")
