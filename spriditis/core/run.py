from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .entities import MarketEntity


@dataclass
class ResearchRunResult:
    project_id: str
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str | None = None
    entities: list[MarketEntity] = field(default_factory=list)
    visited_pages: int = 0
    failed_pages: int = 0
    skipped_by_robots: int = 0
    discovered_domains: set[str] = field(default_factory=set)

    @property
    def relevant_entities(self) -> list[MarketEntity]:
        return [entity for entity in self.entities if entity.is_relevant]
