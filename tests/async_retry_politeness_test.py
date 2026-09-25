from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import CrawlConfig
from spriditis.crawler.async_http import AsyncHTTPResult
from spriditis.crawler.async_politeness import (
    AdaptivePolitenessController,
    AsyncRetryPolicy,
    AsyncRetryingFetcher,
)


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def utcnow(self):
        return datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc)


class SequenceTransport:
    def __init__(self, sequences):
        self.sequences = {
            url: list(items)
            for url, items in sequences.items()
        }
        self.calls: list[str] = []
        self.call_count = defaultdict(int)

    async def fetch(self, url: str) -> AsyncHTTPResult:
        self.calls.append(url)
        self.call_count[url] += 1
        items = self.sequences[url]
        if not items:
            raise AssertionError(f"No fake response left for {url}")
        return items.pop(0)


def result(
    url: str,
    *,
    status: int | None,
    headers=None,
    error_type: str = "",
    error_message: str = "",
):
    return AsyncHTTPResult(
        requested_url=url,
        final_url=url,
        status_code=status,
        headers=headers or {},
        text="ok" if status == 200 else "",
        error_type=error_type,
        error_message=error_message,
    )


async def main() -> None:
    default = CrawlConfig()
    assert default.async_max_retries == 2
    assert default.async_retry_base_seconds == 1.0
    assert default.async_max_domain_delay_seconds == 120.0

    try:
        CrawlConfig(
            async_enabled=True,
            delay_seconds=5.0,
            async_max_domain_delay_seconds=2.0,
        )
    except ValueError as exc:
        assert "async_max_domain_delay_seconds" in str(exc)
    else:
        raise AssertionError(
            "async max delay smaller than base delay was accepted"
        )

    clock = FakeClock()
    throttle_url = "https://throttle.example/item"
    transport = SequenceTransport(
        {
            throttle_url: [
                result(
                    throttle_url,
                    status=429,
                    headers={"Retry-After": "3"},
                ),
                result(throttle_url, status=200),
            ],
        }
    )

    politeness = AdaptivePolitenessController(
        base_delay_seconds=1.0,
        max_delay_seconds=8.0,
        retry_base_seconds=0.5,
        sleep_func=clock.sleep,
        monotonic_func=clock.monotonic,
        utcnow_func=clock.utcnow,
    )
    fetcher = AsyncRetryingFetcher(
        transport=transport,
        retry_policy=AsyncRetryPolicy(
            max_retries=2,
            retry_base_seconds=0.5,
            max_retry_delay_seconds=10.0,
        ),
        politeness=politeness,
    )

    outcome = await fetcher.fetch(throttle_url)

    assert outcome.result.status_code == 200
    assert outcome.attempts == 2
    assert outcome.retries == 1
    assert outcome.retry_delays == (3.0,)
    assert transport.call_count[throttle_url] == 2
    assert sum(clock.sleeps) == 3.0

    # 429 pressure doubles 1s -> 2s; the successful retry recovers 2s -> 1s.
    assert outcome.final_domain_delay_seconds == 1.0

    throttle_state = politeness.snapshot()["throttle.example"]
    assert throttle_state.requests_started == 2
    assert throttle_state.pressure_events == 1
    assert throttle_state.successes == 1
    assert throttle_state.retries == 1
    assert throttle_state.waited_seconds == 3.0

    # Network errors use bounded exponential backoff and stop at the budget.
    clock2 = FakeClock()
    fail_url = "https://fail.example/item"
    fail_transport = SequenceTransport(
        {
            fail_url: [
                result(
                    fail_url,
                    status=None,
                    error_type="ConnectionError",
                    error_message="synthetic",
                ),
                result(
                    fail_url,
                    status=None,
                    error_type="ConnectionError",
                    error_message="synthetic",
                ),
                result(
                    fail_url,
                    status=None,
                    error_type="ConnectionError",
                    error_message="synthetic",
                ),
            ],
        }
    )
    fail_politeness = AdaptivePolitenessController(
        base_delay_seconds=0.0,
        max_delay_seconds=10.0,
        retry_base_seconds=1.0,
        sleep_func=clock2.sleep,
        monotonic_func=clock2.monotonic,
        utcnow_func=clock2.utcnow,
    )
    fail_fetcher = AsyncRetryingFetcher(
        transport=fail_transport,
        retry_policy=AsyncRetryPolicy(
            max_retries=2,
            retry_base_seconds=1.0,
            max_retry_delay_seconds=10.0,
        ),
        politeness=fail_politeness,
    )

    failed = await fail_fetcher.fetch(fail_url)

    assert failed.result.error_type == "ConnectionError"
    assert failed.attempts == 3
    assert failed.retries == 2
    assert failed.retry_delays == (1.0, 2.0)
    assert failed.retry_exhausted is True
    assert fail_transport.call_count[fail_url] == 3
    assert sum(clock2.sleeps) == 3.0

    # Non-transient HTTP errors are returned immediately.
    clock3 = FakeClock()
    missing_url = "https://missing.example/item"
    missing_transport = SequenceTransport(
        {
            missing_url: [
                result(missing_url, status=404),
            ],
        }
    )
    missing_politeness = AdaptivePolitenessController(
        base_delay_seconds=0.0,
        max_delay_seconds=10.0,
        retry_base_seconds=1.0,
        sleep_func=clock3.sleep,
        monotonic_func=clock3.monotonic,
        utcnow_func=clock3.utcnow,
    )
    missing_fetcher = AsyncRetryingFetcher(
        transport=missing_transport,
        retry_policy=AsyncRetryPolicy(
            max_retries=4,
            retry_base_seconds=1.0,
            max_retry_delay_seconds=10.0,
        ),
        politeness=missing_politeness,
    )

    missing = await missing_fetcher.fetch(missing_url)
    assert missing.result.status_code == 404
    assert missing.attempts == 1
    assert missing.retries == 0
    assert missing.retry_exhausted is False
    assert clock3.sleeps == []

    # Domain state is independent: pressure on A does not raise B's delay.
    domain_a = "https://a.example/item"
    domain_b = "https://b.example/item"
    independent = AdaptivePolitenessController(
        base_delay_seconds=1.0,
        max_delay_seconds=16.0,
        retry_base_seconds=1.0,
        sleep_func=clock3.sleep,
        monotonic_func=clock3.monotonic,
        utcnow_func=clock3.utcnow,
    )
    independent.observe(
        domain_a,
        result(domain_a, status=503),
    )
    assert independent.current_delay("a.example") == 2.0
    assert independent.current_delay("b.example") == 1.0

    # Retry-After is capped to the configured retry ceiling.
    capped = independent.retry_delay(
        result(
            domain_a,
            status=429,
            headers={"Retry-After": "999"},
        ),
        0,
        max_delay_seconds=12.0,
    )
    assert capped == 12.0


asyncio.run(main())

print("ASYNC RETRY / POLITENESS TEST OK")
print("retryable_statuses=bounded_retry")
print("network_error=bounded_exponential_backoff")
print("retry_after=respected_and_capped")
print("retry_budget=hard_limit")
print("non_retryable_http=no_retry")
print("adaptive_delay=pressure_up_success_down")
print("domain_politeness=independent")
print("config=validated")
