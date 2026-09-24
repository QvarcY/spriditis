from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.watch import (
    WatchCycleResult,
    dispatch_watch_hooks,
)


calls: list[tuple[str, int, int]] = []


def cycle_hook(result: WatchCycleResult) -> None:
    calls.append(
        ("cycle", result.cycle_number, result.change_count)
    )


def change_hook(result: WatchCycleResult) -> None:
    calls.append(
        ("change", result.cycle_number, result.change_count)
    )


baseline = WatchCycleResult(
    project_id="watch_hooks",
    cycle_number=1,
    run_id=10,
    previous_run_id=None,
    baseline=True,
    change_count=0,
)
failures = dispatch_watch_hooks(
    baseline,
    cycle_hooks=[cycle_hook],
    change_hooks=[change_hook],
)
assert failures == []
assert calls == [("cycle", 1, 0)]
assert baseline.has_changes is False


calls.clear()
unchanged = WatchCycleResult(
    project_id="watch_hooks",
    cycle_number=2,
    run_id=11,
    previous_run_id=10,
    baseline=False,
    change_count=0,
    suppressed_uncertain=4,
    suppressed_counts={
        "NEW_ENTITY": 2,
        "ENTITY_DISAPPEARED": 2,
    },
)
failures = dispatch_watch_hooks(
    unchanged,
    cycle_hooks=[cycle_hook],
    change_hooks=[change_hook],
)
assert failures == []
assert calls == [("cycle", 2, 0)]
assert unchanged.has_changes is False


calls.clear()
changed = WatchCycleResult(
    project_id="watch_hooks",
    cycle_number=3,
    run_id=12,
    previous_run_id=11,
    baseline=False,
    change_count=2,
    counts={
        "PRICE_DROP": 1,
        "DESCRIPTION_CHANGED": 1,
    },
)
failures = dispatch_watch_hooks(
    changed,
    cycle_hooks=[cycle_hook],
    change_hooks=[change_hook],
)
assert failures == []
assert calls == [
    ("cycle", 3, 2),
    ("change", 3, 2),
]
assert changed.has_changes is True


calls.clear()


def failing_cycle_hook(result: WatchCycleResult) -> None:
    raise RuntimeError("cycle adapter failed")


def later_cycle_hook(result: WatchCycleResult) -> None:
    calls.append(
        ("cycle_after_failure", result.cycle_number, result.change_count)
    )


failures = dispatch_watch_hooks(
    changed,
    cycle_hooks=[
        failing_cycle_hook,
        later_cycle_hook,
    ],
    change_hooks=[change_hook],
)

assert calls == [
    ("cycle_after_failure", 3, 2),
    ("change", 3, 2),
]
assert len(failures) == 1
failure = failures[0]
assert failure.hook_kind == "cycle"
assert failure.hook_name == "failing_cycle_hook"
assert failure.error_type == "RuntimeError"
assert failure.message == "cycle adapter failed"


print("WATCH HOOKS TEST OK")
print("cycle_hook=every_completed_cycle")
print("change_hook=verified_changes_only")
print("baseline=change_hook_skipped")
print("no_change=change_hook_skipped")
print("hook_failure=isolated_nonfatal")
print("future_scheduler_adapter=cycle_hook")
print("future_notification_adapter=change_hook")
