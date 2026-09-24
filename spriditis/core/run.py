from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .domains import DomainDiscovery, DomainRecord
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

    search_queries_issued: int = 0
    search_results_seen: int = 0
    search_results_unique: int = 0
    search_results_duplicates: int = 0
    search_domains_activated: int = 0
    search_provider_errors: int = 0

    domains: dict[str, DomainRecord] = field(default_factory=dict)
    domain_discoveries: list[DomainDiscovery] = field(default_factory=list)

    @property
    def discovered_domains(self) -> set[str]:
        return set(self.domains)

    @property
    def relevant_entities(self) -> list[MarketEntity]:
        return [entity for entity in self.entities if entity.is_relevant]
