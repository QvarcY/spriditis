from __future__ import annotations

import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.crawler.async_coordinator import (
    AsyncCrawlCoordinator,
    AsyncCrawlPolicy,
)


async def main() -> None:
    policy = AsyncCrawlPolicy(
        global_concurrency=3,
        per_domain_concurrency=1,
        min_domain_delay_seconds=0.03,
        max_pending=2,
    )

    coordinator = AsyncCrawlCoordinator(policy)

    active = 0
    peak_active = 0
    domain_active: dict[str, int] = defaultdict(int)
    peak_domain_active: dict[str, int] = defaultdict(int)
    starts: dict[str, list[float]] = defaultdict(list)

    urls = [
        "https://a.example/1",
        "https://a.example/2",
        "https://b.example/1",
        "https://b.example/2",
        "https://c.example/1",
        "https://a.example/3",
    ]

    async def worker(url: str) -> str:
        nonlocal active, peak_active

        domain = url.split("/", 3)[2]
        starts[domain].append(time.monotonic())

        active += 1
        peak_active = max(peak_active, active)
        domain_active[domain] += 1
        peak_domain_active[domain] = max(
            peak_domain_active[domain],
            domain_active[domain],
        )

        try:
            await asyncio.sleep(0.02)
            return f"ok:{url}"
        finally:
            domain_active[domain] -= 1
            active -= 1

    results, stats = await coordinator.run(urls, worker)

    assert [item.url for item in results] == urls
    assert all(item.ok for item in results)
    assert [item.value for item in results] == [
        f"ok:{url}" for url in urls
    ]

    assert stats.submitted == len(urls)
    assert stats.completed == len(urls)
    assert stats.failed == 0

    assert peak_active <= policy.global_concurrency
    assert stats.peak_active <= policy.global_concurrency
    assert stats.peak_active == peak_active

    assert all(
        value <= policy.per_domain_concurrency
        for value in peak_domain_active.values()
    )
    assert all(
        value <= policy.per_domain_concurrency
        for value in stats.peak_domain_active.values()
    )

    assert stats.peak_pending <= policy.max_pending

    for domain, values in starts.items():
        for previous, current in zip(values, values[1:]):
            assert current - previous >= 0.02, (
                domain,
                previous,
                current,
                current - previous,
            )

    # Worker failures are isolated and returned as structured results.
    failing = AsyncCrawlCoordinator(
        AsyncCrawlPolicy(
            global_concurrency=2,
            per_domain_concurrency=1,
            max_pending=1,
        )
    )

    async def sometimes_fails(url: str) -> str:
        if url.endswith("/bad"):
            raise RuntimeError("synthetic failure")
        await asyncio.sleep(0)
        return "ok"

    failure_results, failure_stats = await failing.run(
        [
            "https://one.example/good",
            "https://two.example/bad",
            "https://three.example/good",
        ],
        sometimes_fails,
    )

    assert [item.ok for item in failure_results] == [
        True,
        False,
        True,
    ]
    assert failure_results[1].error_type == "RuntimeError"
    assert failure_results[1].error_message == "synthetic failure"
    assert failure_stats.submitted == 3
    assert failure_stats.completed == 3
    assert failure_stats.failed == 1


asyncio.run(main())

print("ASYNC COORDINATOR TEST OK")
print("global_concurrency=bounded")
print("per_domain_concurrency=bounded")
print("domain_start_delay=enforced")
print("pending_queue=bounded")
print("result_order=input_order")
print("worker_failure=isolated_structured")
