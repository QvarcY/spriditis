from __future__ import annotations

import asyncio
import time
from collections import defaultdict
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
    Small async orchestration primitive for alpha10.

    This class deliberately does not know about requests, extraction,
    Domain Registry, or persistence. It only enforces concurrency,
    per-domain politeness, and bounded pending work.
    """

    def __init__(self, policy: AsyncCrawlPolicy):
        self.policy = policy

        self._global_semaphore = asyncio.Semaphore(
            policy.global_concurrency
        )
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
        self._domain_start_locks: dict[str, asyncio.Lock] = {}
        self._last_domain_start: dict[str, float] = {}

        self._active = 0
        self._peak_active = 0
        self._domain_active: dict[str, int] = defaultdict(int)
        self._peak_domain_active: dict[str, int] = defaultdict(int)

    def _domain_semaphore(self, domain: str) -> asyncio.Semaphore:
        semaphore = self._domain_semaphores.get(domain)
        if semaphore is None:
            semaphore = asyncio.Semaphore(
                self.policy.per_domain_concurrency
            )
            self._domain_semaphores[domain] = semaphore
        return semaphore

    def _domain_start_lock(self, domain: str) -> asyncio.Lock:
        lock = self._domain_start_locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self._domain_start_locks[domain] = lock
        return lock

    async def _wait_for_domain_slot(self, domain: str) -> None:
        delay = self.policy.min_domain_delay_seconds
        if delay <= 0:
            return

        async with self._domain_start_lock(domain):
            now = time.monotonic()
            previous = self._last_domain_start.get(domain)

            if previous is not None:
                wait_for = delay - (now - previous)
                if wait_for > 0:
                    await asyncio.sleep(wait_for)

            self._last_domain_start[domain] = time.monotonic()

    async def _execute(
        self,
        index: int,
        url: str,
        worker: Worker[T],
    ) -> AsyncTaskResult[T]:
        domain = host_key(url)
        if not domain:
            return AsyncTaskResult(
                index=index,
                url=url,
                error_type="InvalidURL",
                error_message="URL nav nosakāms domēns.",
            )

        domain_semaphore = self._domain_semaphore(domain)

        # Take the domain permit first so same-domain waiters never occupy
        # scarce global slots. Domain delay is also paid before acquiring
        # the global execution slot.
        async with domain_semaphore:
            await self._wait_for_domain_slot(domain)

            async with self._global_semaphore:
                self._active += 1
                self._peak_active = max(
                    self._peak_active,
                    self._active,
                )
                self._domain_active[domain] += 1
                self._peak_domain_active[domain] = max(
                    self._peak_domain_active[domain],
                    self._domain_active[domain],
                )

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
                finally:
                    self._domain_active[domain] -= 1
                    self._active -= 1

    async def run(
        self,
        urls: Iterable[str],
        worker: Worker[T],
    ) -> tuple[list[AsyncTaskResult[T]], AsyncRunStats]:
        queue: asyncio.Queue[tuple[int, str] | None] = asyncio.Queue(
            maxsize=self.policy.max_pending
        )
        results: list[AsyncTaskResult[T]] = []
        submitted = 0
        completed = 0
        failed = 0
        peak_pending = 0

        async def consume() -> None:
            nonlocal completed, failed

            while True:
                item = await queue.get()
                try:
                    if item is None:
                        return

                    index, url = item
                    result = await self._execute(
                        index,
                        url,
                        worker,
                    )
                    results.append(result)
                    completed += 1
                    if not result.ok:
                        failed += 1
                finally:
                    queue.task_done()

        consumers = [
            asyncio.create_task(consume())
            for _ in range(self.policy.global_concurrency)
        ]

        try:
            for index, url in enumerate(urls):
                await queue.put((index, url))
                submitted += 1
                peak_pending = max(
                    peak_pending,
                    queue.qsize(),
                )

            await queue.join()
        finally:
            for _ in consumers:
                await queue.put(None)
            await asyncio.gather(*consumers)

        results.sort(key=lambda item: item.index)

        return results, AsyncRunStats(
            submitted=submitted,
            completed=completed,
            failed=failed,
            peak_active=self._peak_active,
            peak_pending=peak_pending,
            peak_domain_active=dict(self._peak_domain_active),
        )
