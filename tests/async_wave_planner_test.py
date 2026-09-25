from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import CrawlConfig
from spriditis.crawler.async_wave import AsyncWavePlanner
from spriditis.crawler.frontier import URLFrontier


# Async mode remains opt-in and validates impossible concurrency settings.
default_config = CrawlConfig()
assert default_config.async_enabled is False
assert default_config.async_global_concurrency == 4
assert default_config.async_per_domain_concurrency == 1
assert default_config.async_max_pending == 8

try:
    CrawlConfig(
        async_global_concurrency=1,
        async_per_domain_concurrency=2,
    )
except ValueError as exc:
    assert "async_per_domain_concurrency" in str(exc)
else:
    raise AssertionError("invalid async concurrency config was accepted")


frontier = URLFrontier()
frontier.add(
    "https://a.example/high-1",
    priority=100,
    depth=0,
    source_type="seed",
)
frontier.add(
    "https://a.example/high-2",
    priority=95,
    depth=0,
    source_type="seed",
)
frontier.add(
    "https://b.example/mid",
    priority=90,
    depth=0,
    source_type="seed",
)
frontier.add(
    "https://c.example/blocked",
    priority=85,
    depth=0,
    source_type="seed",
)
frontier.add(
    "https://d.example/later",
    priority=80,
    depth=0,
    source_type="seed",
)

planner = AsyncWavePlanner(
    wave_size=3,
    max_pages_per_domain=2,
)

pages = Counter({"a.example": 1})

wave = planner.plan(
    frontier,
    remaining_total=10,
    pages_by_domain=pages,
    classify=lambda item: (
        "defer" if "blocked" in item.url else "eligible"
    ),
)

# a.example has one page already, so only one additional URL may be
# reserved from that domain. The planner skips high-2 temporarily and
# continues looking for other eligible domains.
assert wave.urls == (
    "https://a.example/high-1",
    "https://b.example/mid",
    "https://d.example/later",
)
assert wave.reserved_by_domain == {
    "a.example": 1,
    "b.example": 1,
    "d.example": 1,
}

# Deferred items keep their original deterministic priority/tie order.
first_deferred = frontier.pop()
second_deferred = frontier.pop()
assert first_deferred.url == "https://a.example/high-2"
assert second_deferred.url == "https://c.example/blocked"

# Permanently invalid work can be dropped instead of requeued.
drop_frontier = URLFrontier()
drop_frontier.add(
    "https://drop.example/invalid",
    priority=100,
    depth=0,
)
drop_frontier.add(
    "https://keep.example/valid",
    priority=90,
    depth=0,
)
drop_wave = planner.plan(
    drop_frontier,
    remaining_total=2,
    pages_by_domain=Counter(),
    classify=lambda item: (
        "drop" if "invalid" in item.url else "eligible"
    ),
)
assert drop_wave.urls == ("https://keep.example/valid",)
assert not drop_frontier

# remaining_total caps the wave independently from configured wave_size.
small_frontier = URLFrontier()
for index in range(5):
    small_frontier.add(
        f"https://x{index}.example/item",
        priority=100 - index,
        depth=0,
    )

small_wave = planner.plan(
    small_frontier,
    remaining_total=2,
    pages_by_domain=Counter(),
    eligible=lambda item: True,
)
assert len(small_wave.items) == 2
assert small_wave.urls == (
    "https://x0.example/item",
    "https://x1.example/item",
)

# If the total budget is exhausted, planning must not mutate the frontier.
before = small_frontier.pop()
small_frontier.restore(before)

empty_wave = planner.plan(
    small_frontier,
    remaining_total=0,
    pages_by_domain=Counter(),
    eligible=lambda item: True,
)
assert empty_wave.items == ()
after = small_frontier.pop()
assert after.url == before.url


print("ASYNC WAVE PLANNER TEST OK")
print("async_mode=opt_in")
print("invalid_concurrency=config_rejected")
print("wave_size=bounded")
print("remaining_total=reserved")
print("per_domain_page_budget=reserved")
print("temporarily_ineligible=deferred")
print("permanently_ineligible=dropped")
print("frontier_tie_order=preserved")
