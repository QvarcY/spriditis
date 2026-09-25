from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from .frontier import FrontierItem, URLFrontier
from .policy import host_key


EligibilityCheck = Callable[[FrontierItem], bool]


@dataclass(frozen=True)
class FetchWave:
    items: tuple[FrontierItem, ...]
    reserved_by_domain: dict[str, int] = field(default_factory=dict)

    @property
    def urls(self) -> tuple[str, ...]:
        return tuple(item.url for item in self.items)


class AsyncWavePlanner:
    """
    Deterministically reserve a bounded fetch wave from the frontier.

    Planning mutates only the frontier (via pop). It does not touch visited,
    Domain Registry, page counters, extraction state, or persistence. Per-
    domain page capacity is reserved while choosing the wave so concurrent
    fetches cannot overshoot the existing crawl budget.
    """

    def __init__(
        self,
        *,
        wave_size: int,
        max_pages_per_domain: int,
    ):
        if wave_size < 1:
            raise ValueError("wave_size jābūt vismaz 1.")
        if max_pages_per_domain < 1:
            raise ValueError(
                "max_pages_per_domain jābūt vismaz 1."
            )

        self.wave_size = wave_size
        self.max_pages_per_domain = max_pages_per_domain

    def plan(
        self,
        frontier: URLFrontier,
        *,
        remaining_total: int,
        pages_by_domain: Counter[str],
        eligible: EligibilityCheck,
    ) -> FetchWave:
        if remaining_total <= 0:
            return FetchWave(items=())

        target = min(self.wave_size, remaining_total)
        selected: list[FrontierItem] = []
        reserved: Counter[str] = Counter()
        deferred: list[FrontierItem] = []

        while frontier and len(selected) < target:
            item = frontier.pop()

            if not eligible(item):
                deferred.append(item)
                continue

            domain = host_key(item.url)
            if not domain:
                deferred.append(item)
                continue

            if (
                pages_by_domain[domain] + reserved[domain]
                >= self.max_pages_per_domain
            ):
                deferred.append(item)
                continue

            selected.append(item)
            reserved[domain] += 1

        # Put temporarily ineligible items back with exactly their original
        # priority/order metadata. URLFrontier.add() would allocate a new
        # order, so use restore() to preserve deterministic tie ordering.
        for item in deferred:
            frontier.restore(item)

        return FetchWave(
            items=tuple(selected),
            reserved_by_domain=dict(reserved),
        )
