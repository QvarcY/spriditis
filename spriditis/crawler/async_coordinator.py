from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Generic, Iterable, TypeVar

from .policy import host_key


T = TypeVar("T")


@dataclass(frozen=True)
class AsyncCrawlPolicy:
    global_concurrency: int = 4
    per_domain_concurrency: int = 1
    min_domain_delay_seconds: float = 0.0
    max_pending: int = 8

    def __post_init__(self) -> None:
        if self.global_concurrency < 1:
            raise ValueError("global_concurrency jābūt vismaz 1.")
        if self.per_domain_concurrency < 1:
            raise ValueError("per_domain_concurrency jābūt vismaz 1.")
        if self.per_domain_concurrency > self.global_concurrency:
            raise ValueError(
                "per_domain_concurrency nevar pārsniegt global_concurrency."
            )
        if self.min_domain_delay_seconds < 0:
            raise ValueError(
                "min_domain_delay_seconds nevar būt negatīvs."
            )
        if self.max_pending < 1:
            raise ValueError("max_pending jābūt vismaz 1.")


@dataclass(frozen=True)
class AsyncTaskResult(Generic[T]):
    index: int
    url: str
    value: T | None = None
    error_type: str = ""
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return not self.error_type


@dataclass(frozen=True)
class AsyncRunStats:
    submitted: int
    completed: int
    failed: int
    peak_active: int
    peak_pending: int
    peak_domain_active: dict[str, int] = field(default_factory=dict)


Worker = Callable[[str], Awaitable[T]]


class AsyncCrawlCoordinator:
    """
    Domain-aware bounded async dispatcher for alpha10.

    Pending work is bounded, but blocked same-domain items do not consume
    global execution slots. The dispatcher may skip over temporarily
    ineligible pending items so other domains can continue making progress.
    Results are returned in original input order.
    """

    def __init__(self, policy: AsyncCrawlPolicy):
        self.policy = policy

    async def _run_worker(
        self,
        index: int,
        url: str,
        worker: Worker[T],
    ) -> AsyncTaskResult[T]:
        try:
            value = await worker(url)
            return AsyncTaskResult(
                index=index,
                url=url,
                value=value,
            )
        except Exception as exc:
            return AsyncTaskResult(
                index=index,
                url=url,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    async def run(
        self,
        urls: Iterable[str],
        worker: Worker[T],
    ) -> tuple[list[AsyncTaskResult[T]], AsyncRunStats]:
        iterator = iter(urls)
        pending: deque[tuple[int, str, str]] = deque()
        active: dict[
            asyncio.Task[AsyncTaskResult[T]],
            tuple[int, str, str],
        ] = {}

        results: list[AsyncTaskResult[T]] = []
        domain_active: dict[str, int] = defaultdict(int)
        peak_domain_active: dict[str, int] = defaultdict(int)
        next_domain_start: dict[str, float] = {}

        submitted = 0
        completed = 0
        failed = 0
        peak_active = 0
        peak_pending = 0
        exhausted = False

        def fill_pending() -> None:
            nonlocal submitted, peak_pending, exhausted

            while (
                not exhausted
                and len(pending) < self.policy.max_pending
            ):
                try:
                    url = next(iterator)
                except StopIteration:
                    exhausted = True
                    return

                index = submitted
                submitted += 1
                domain = host_key(url)

                if not domain:
                    results.append(
                        AsyncTaskResult(
                            index=index,
                            url=url,
                            error_type="InvalidURL",
                            error_message="URL nav nosakāms domēns.",
                        )
                    )
                    continue

                pending.append((index, url, domain))
                peak_pending = max(
                    peak_pending,
                    len(pending),
                )

        def find_eligible(now: float) -> int | None:
            if len(active) >= self.policy.global_concurrency:
                return None

            for offset, (_, _, domain) in enumerate(pending):
                if (
                    domain_active[domain]
                    >= self.policy.per_domain_concurrency
                ):
                    continue

                if now < next_domain_start.get(domain, 0.0):
                    continue

                return offset

            return None

        def pop_offset(offset: int) -> tuple[int, str, str]:
            pending.rotate(-offset)
            item = pending.popleft()
            pending.rotate(offset)
            return item

        fill_pending()

        while pending or active or not exhausted:
            made_progress = False

            while len(active) < self.policy.global_concurrency:
                fill_pending()
                if not pending:
                    break

                now = time.monotonic()
                offset = find_eligible(now)
                if offset is None:
                    break

                index, url, domain = pop_offset(offset)

                domain_active[domain] += 1
                peak_domain_active[domain] = max(
                    peak_domain_active[domain],
                    domain_active[domain],
                )

                next_domain_start[domain] = (
                    now + self.policy.min_domain_delay_seconds
                )

                task = asyncio.create_task(
                    self._run_worker(index, url, worker)
                )
                active[task] = (index, url, domain)
                peak_active = max(peak_active, len(active))
                made_progress = True

            fill_pending()

            if not active:
                if not pending and exhausted:
                    break

                if pending:
                    now = time.monotonic()
                    waits = [
                        max(
                            0.0,
                            next_domain_start.get(domain, 0.0) - now,
                        )
                        for _, _, domain in pending
                        if (
                            domain_active[domain]
                            < self.policy.per_domain_concurrency
                        )
                    ]
                    wait_for = min(waits) if waits else 0.001
                    await asyncio.sleep(max(wait_for, 0.001))
                    continue

            if made_progress and len(active) < self.policy.global_concurrency:
                continue

            now = time.monotonic()
            delay_waits = [
                max(
                    0.0,
                    next_domain_start.get(domain, 0.0) - now,
                )
                for _, _, domain in pending
                if (
                    domain_active[domain]
                    < self.policy.per_domain_concurrency
                )
            ]
            timeout = min(delay_waits) if delay_waits else None
            if timeout is not None and timeout <= 0:
                timeout = 0.001

            done, _ = await asyncio.wait(
                set(active),
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                _, _, domain = active.pop(task)
                domain_active[domain] -= 1

                result = task.result()
                results.append(result)
                completed += 1
                if not result.ok:
                    failed += 1

        # Invalid URLs are completed synchronously during submission.
        invalid_count = sum(
            1
            for item in results
            if item.error_type == "InvalidURL"
        )
        completed += invalid_count
        failed += invalid_count

        results.sort(key=lambda item: item.index)

        return results, AsyncRunStats(
            submitted=submitted,
            completed=completed,
            failed=failed,
            peak_active=peak_active,
            peak_pending=peak_pending,
            peak_domain_active=dict(peak_domain_active),
        )
