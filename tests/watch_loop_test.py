from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.cli import (
    MIN_WATCH_INTERVAL_SECONDS,
    _parser,
    _run_watch_loop,
    _watch_schedule,
)


assert _watch_schedule(
    once=True,
    interval_seconds=None,
    max_cycles=None,
) == (None, 1)

interval, limit = _watch_schedule(
    once=False,
    interval_seconds=60,
    max_cycles=3,
)
assert interval == 60.0
assert limit == 3

for kwargs in (
    {
        "once": False,
        "interval_seconds": None,
        "max_cycles": None,
    },
    {
        "once": False,
        "interval_seconds": MIN_WATCH_INTERVAL_SECONDS - 1,
        "max_cycles": None,
    },
    {
        "once": False,
        "interval_seconds": 60,
        "max_cycles": 0,
    },
    {
        "once": True,
        "interval_seconds": 60,
        "max_cycles": None,
    },
    {
        "once": True,
        "interval_seconds": None,
        "max_cycles": 2,
    },
):
    try:
        _watch_schedule(**kwargs)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Expected invalid watch schedule: {kwargs}")

cycles: list[int] = []
sleeps: list[float] = []

completed = _run_watch_loop(
    lambda cycle: cycles.append(cycle),
    once=False,
    interval_seconds=60,
    max_cycles=3,
    sleep_fn=lambda seconds: sleeps.append(seconds),
)

assert completed == 3
assert cycles == [1, 2, 3]
assert sleeps == [60.0, 60.0]

once_cycles: list[int] = []
once_sleeps: list[float] = []

completed_once = _run_watch_loop(
    lambda cycle: once_cycles.append(cycle),
    once=True,
    interval_seconds=None,
    max_cycles=None,
    sleep_fn=lambda seconds: once_sleeps.append(seconds),
)

assert completed_once == 1
assert once_cycles == [1]
assert once_sleeps == []

interrupt_cycles: list[int] = []
interrupt_sleeps: list[float] = []


def interrupt_on_second(cycle: int) -> None:
    if cycle == 2:
        raise KeyboardInterrupt
    interrupt_cycles.append(cycle)


completed_interrupted = _run_watch_loop(
    interrupt_on_second,
    once=False,
    interval_seconds=60,
    max_cycles=None,
    sleep_fn=lambda seconds: interrupt_sleeps.append(seconds),
)

assert completed_interrupted == 1
assert interrupt_cycles == [1]
assert interrupt_sleeps == [60.0]

args = _parser().parse_args(
    [
        "watch",
        "--project",
        "project.json",
        "--interval-seconds",
        "120",
        "--max-cycles",
        "4",
    ]
)

assert args.command == "watch"
assert args.once is False
assert args.interval_seconds == 120.0
assert args.max_cycles == 4

print("WATCH LOOP TEST OK")
print("repeat_mode=explicit_interval")
print("minimum_interval_seconds=60")
print("bounded_cycles=3")
print("once_mode=single_cycle_no_sleep")
print("keyboard_interrupt=graceful_stop")
print("unfinished_interrupted_cycle=not_counted")
