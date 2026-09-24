from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .domains import DomainDiscovery, DomainRecord
from .entities import MarketEntity
from .feeds import FeedState
from .memory import PageVisit


@dataclass(frozen=True)
class AdaptiveDecision:
    stage: str
    decision: str
    target: str
    signals: dict[str, Any] = field(default_factory=dict)
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class ResearchRunResult:
    project_id: str
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str | None = None

    entities: list[MarketEntity] = field(default_factory=list)
    page_visits: list[PageVisit] = field(default_factory=list)
    adaptive_decisions: list[AdaptiveDecision] = field(default_factory=list)

    visited_pages: int = 0
    failed_pages: int = 0
    skipped_by_robots: int = 0

    stop_reason: str = ""
    diminishing_returns_streak: int = 0
    saturation_streak: int = 0
    diversity_penalties_applied: int = 0
    diversity_domains_penalized: set[str] = field(default_factory=set)

    search_queries_issued: int = 0
    search_results_seen: int = 0
    search_results_unique: int = 0
    search_results_duplicates: int = 0
    search_domains_activated: int = 0
    search_provider_errors: int = 0

    feed_candidates_seen: int = 0
    feeds_found: int = 0
    feed_entries_seen: int = 0
    feed_entries_new: int = 0
    feed_not_modified: int = 0
    feed_errors: int = 0
    feed_states: dict[str, FeedState] = field(default_factory=dict)

    domains: dict[str, DomainRecord] = field(default_factory=dict)
    domain_discoveries: list[DomainDiscovery] = field(default_factory=list)

    @property
    def discovered_domains(self) -> set[str]:
        return set(self.domains)

    @property
    def relevant_entities(self) -> list[MarketEntity]:
        return [entity for entity in self.entities if entity.is_relevant]
