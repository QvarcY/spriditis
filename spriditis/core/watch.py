from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass(frozen=True)
class WatchCycleResult:
    project_id: str
    cycle_number: int
    run_id: int
    previous_run_id: int | None
    baseline: bool
    change_count: int
    counts: dict[str, int] = field(default_factory=dict)
    suppressed_uncertain: int = 0
    suppressed_counts: dict[str, int] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        return self.change_count > 0


WatchHook = Callable[[WatchCycleResult], None]


@dataclass(frozen=True)
class WatchHookFailure:
    hook_kind: str
    hook_name: str
    error_type: str
    message: str


def _hook_name(hook: WatchHook) -> str:
    name = getattr(hook, "__name__", "")
    if name:
        return str(name)
    return hook.__class__.__name__


def dispatch_watch_hooks(
    result: WatchCycleResult,
    *,
    cycle_hooks: Iterable[WatchHook] = (),
    change_hooks: Iterable[WatchHook] = (),
) -> list[WatchHookFailure]:
    failures: list[WatchHookFailure] = []

    def run(kind: str, hooks: Iterable[WatchHook]) -> None:
        for hook in hooks:
            try:
                hook(result)
            except Exception as exc:
                failures.append(
                    WatchHookFailure(
                        hook_kind=kind,
                        hook_name=_hook_name(hook),
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )

    run("cycle", cycle_hooks)
    if result.has_changes:
        run("change", change_hooks)

    return failures
