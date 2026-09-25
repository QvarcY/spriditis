from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Awaitable, Callable
from urllib.parse import urlparse

from .async_http import AsyncHTTPResult


RETRYABLE_STATUS_CODES = frozenset({
    408,
    429,
    500,
    502,
    503,
    504,
})


@dataclass(frozen=True)
class AsyncRetryPolicy:
    max_retries: int = 2
    retry_base_seconds: float = 1.0
    max_retry_delay_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries nevar būt negatīvs.")
        if self.retry_base_seconds < 0:
            raise ValueError(
                "retry_base_seconds nevar būt negatīvs."
            )
        if self.max_retry_delay_seconds < 0:
            raise ValueError(
                "max_retry_delay_seconds nevar būt negatīvs."
            )


@dataclass
class DomainPolitenessState:
    current_delay_seconds: float
    next_allowed_at: float = 0.0
    requests_started: int = 0
    successes: int = 0
    pressure_events: int = 0
    retries: int = 0
    waited_seconds: float = 0.0


@dataclass(frozen=True)
class AsyncFetchOutcome:
    result: AsyncHTTPResult
    attempts: int
    retries: int
    retry_delays: tuple[float, ...] = ()
    waited_seconds: float = 0.0
    final_domain_delay_seconds: float = 0.0
    retry_exhausted: bool = False


SleepFunc = Callable[[float], Awaitable[None]]
MonotonicFunc = Callable[[], float]
UTCNowFunc = Callable[[], datetime]


class AdaptivePolitenessController:
    """
    Explainable per-domain start pacing for async crawling.

    delay_seconds is the stable floor. Transient pressure increases a
    domain's delay, successful responses decay it back toward the floor.
    Retry-After and exponential retry backoff can extend next_allowed_at.
    """

    def __init__(
        self,
        *,
        base_delay_seconds: float,
        max_delay_seconds: float,
        retry_base_seconds: float,
        sleep_func: SleepFunc = asyncio.sleep,
        monotonic_func: MonotonicFunc = time.monotonic,
        utcnow_func: UTCNowFunc = lambda: datetime.now(timezone.utc),
    ):
        if base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds nevar būt negatīvs."
            )
        if max_delay_seconds < base_delay_seconds:
            raise ValueError(
                "max_delay_seconds nevar būt mazāks par bāzes delay."
            )
        if retry_base_seconds < 0:
            raise ValueError(
                "retry_base_seconds nevar būt negatīvs."
            )

        self.base_delay_seconds = float(base_delay_seconds)
        self.max_delay_seconds = float(max_delay_seconds)
        self.retry_base_seconds = float(retry_base_seconds)
        self.sleep_func = sleep_func
        self.monotonic_func = monotonic_func
        self.utcnow_func = utcnow_func

        self._states: dict[str, DomainPolitenessState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def domain_for(url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    def _state(self, domain: str) -> DomainPolitenessState:
        state = self._states.get(domain)
        if state is None:
            state = DomainPolitenessState(
                current_delay_seconds=self.base_delay_seconds
            )
            self._states[domain] = state
        return state

    def _lock(self, domain: str) -> asyncio.Lock:
        lock = self._locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[domain] = lock
        return lock

    async def before_request(self, url: str) -> float:
        domain = self.domain_for(url)
        if not domain:
            return 0.0

        async with self._lock(domain):
            state = self._state(domain)
            now = self.monotonic_func()
            wait_for = max(0.0, state.next_allowed_at - now)

            if wait_for > 0:
                await self.sleep_func(wait_for)
                state.waited_seconds += wait_for

            started = self.monotonic_func()
            state.requests_started += 1
            state.next_allowed_at = max(
                state.next_allowed_at,
                started + state.current_delay_seconds,
            )
            return wait_for

    def observe(
        self,
        url: str,
        result: AsyncHTTPResult,
    ) -> None:
        domain = self.domain_for(url)
        if not domain:
            return

        state = self._state(domain)
        status = result.status_code

        if self.is_pressure(result):
            state.pressure_events += 1
            floor = max(
                self.base_delay_seconds,
                self.retry_base_seconds,
            )
            current = max(
                state.current_delay_seconds,
                floor,
            )
            state.current_delay_seconds = min(
                self.max_delay_seconds,
                max(floor, current * 2.0),
            )
            return

        if (
            result.ok
            and status is not None
            and 200 <= status < 400
        ):
            state.successes += 1
            if state.current_delay_seconds > self.base_delay_seconds:
                state.current_delay_seconds = max(
                    self.base_delay_seconds,
                    state.current_delay_seconds * 0.5,
                )

    @staticmethod
    def is_pressure(result: AsyncHTTPResult) -> bool:
        if result.error_type:
            return True
        return result.status_code in RETRYABLE_STATUS_CODES

    @staticmethod
    def is_retryable(result: AsyncHTTPResult) -> bool:
        return AdaptivePolitenessController.is_pressure(result)

    def retry_delay(
        self,
        result: AsyncHTTPResult,
        attempt_index: int,
        *,
        max_delay_seconds: float,
    ) -> float:
        raw = result.header("Retry-After", "").strip()
        if raw:
            try:
                return max(
                    0.0,
                    min(float(raw), max_delay_seconds),
                )
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(raw)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(
                            tzinfo=timezone.utc
                        )
                    seconds = (
                        retry_at - self.utcnow_func()
                    ).total_seconds()
                    return max(
                        0.0,
                        min(seconds, max_delay_seconds),
                    )
                except (
                    TypeError,
                    ValueError,
                    OverflowError,
                ):
                    pass

        delay = self.retry_base_seconds * (2 ** attempt_index)
        return max(
            0.0,
            min(delay, max_delay_seconds),
        )

    def defer_retry(
        self,
        url: str,
        delay_seconds: float,
    ) -> None:
        domain = self.domain_for(url)
        if not domain:
            return

        state = self._state(domain)
        state.retries += 1
        state.next_allowed_at = max(
            state.next_allowed_at,
            self.monotonic_func() + max(0.0, delay_seconds),
        )

    def current_delay(self, domain: str) -> float:
        return self._state(domain).current_delay_seconds

    def snapshot(self) -> dict[str, DomainPolitenessState]:
        return {
            domain: DomainPolitenessState(
                current_delay_seconds=state.current_delay_seconds,
                next_allowed_at=state.next_allowed_at,
                requests_started=state.requests_started,
                successes=state.successes,
                pressure_events=state.pressure_events,
                retries=state.retries,
                waited_seconds=state.waited_seconds,
            )
            for domain, state in self._states.items()
        }


class AsyncRetryingFetcher:
    def __init__(
        self,
        *,
        transport,
        retry_policy: AsyncRetryPolicy,
        politeness: AdaptivePolitenessController,
    ):
        self.transport = transport
        self.retry_policy = retry_policy
        self.politeness = politeness

    async def fetch(self, url: str) -> AsyncFetchOutcome:
        attempts_total = self.retry_policy.max_retries + 1
        retry_delays: list[float] = []
        waited_seconds = 0.0
        last_result: AsyncHTTPResult | None = None

        for attempt_index in range(attempts_total):
            waited_seconds += await self.politeness.before_request(url)
            result = await self.transport.fetch(url)
            last_result = result
            self.politeness.observe(url, result)

            retryable = self.politeness.is_retryable(result)
            if not retryable:
                return AsyncFetchOutcome(
                    result=result,
                    attempts=attempt_index + 1,
                    retries=attempt_index,
                    retry_delays=tuple(retry_delays),
                    waited_seconds=waited_seconds,
                    final_domain_delay_seconds=
                        self.politeness.current_delay(
                            self.politeness.domain_for(url)
                        ),
                )

            if attempt_index >= self.retry_policy.max_retries:
                return AsyncFetchOutcome(
                    result=result,
                    attempts=attempt_index + 1,
                    retries=attempt_index,
                    retry_delays=tuple(retry_delays),
                    waited_seconds=waited_seconds,
                    final_domain_delay_seconds=
                        self.politeness.current_delay(
                            self.politeness.domain_for(url)
                        ),
                    retry_exhausted=True,
                )

            delay = self.politeness.retry_delay(
                result,
                attempt_index,
                max_delay_seconds=
                    self.retry_policy.max_retry_delay_seconds,
            )
            retry_delays.append(delay)
            self.politeness.defer_retry(url, delay)

        assert last_result is not None
        return AsyncFetchOutcome(
            result=last_result,
            attempts=attempts_total,
            retries=self.retry_policy.max_retries,
            retry_delays=tuple(retry_delays),
            waited_seconds=waited_seconds,
            final_domain_delay_seconds=self.politeness.current_delay(
                self.politeness.domain_for(url)
            ),
            retry_exhausted=True,
        )
