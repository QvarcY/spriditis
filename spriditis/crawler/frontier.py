from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field


@dataclass(order=True)
class FrontierItem:
    sort_key: tuple[int, int] = field(init=False, repr=False)
    priority: int
    order: int
    url: str = field(compare=False)
    depth: int = field(compare=False)
    discovery_depth: int = field(compare=False, default=0)
    source_url: str = field(compare=False, default="")
    source_type: str = field(compare=False, default="unknown")

    def __post_init__(self):
        self.sort_key = (-self.priority, self.order)


class URLFrontier:
    def __init__(self):
        self._queue: list[tuple[int, int, FrontierItem]] = []
        self._counter = itertools.count()
        self._queued: set[str] = set()

    def add(
        self,
        url: str,
        *,
        priority: int,
        depth: int,
        discovery_depth: int = 0,
        source_url: str = "",
        source_type: str = "unknown",
    ) -> bool:
        if url in self._queued:
            return False
        order = next(self._counter)
        item = FrontierItem(
            priority=priority,
            order=order,
            url=url,
            depth=depth,
            discovery_depth=discovery_depth,
            source_url=source_url,
            source_type=source_type,
        )
        heapq.heappush(self._queue, (-priority, order, item))
        self._queued.add(url)
        return True

    def pop(self) -> FrontierItem:
        _, _, item = heapq.heappop(self._queue)
        self._queued.discard(item.url)
        return item

    def __bool__(self):
        return bool(self._queue)
