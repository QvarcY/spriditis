from __future__ import annotations

from dataclasses import dataclass, field

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject


@dataclass
class ResearchCoverage:
    """Run-local evidence and scheduling state, separate from domain history."""

    specific_target: bool
    source_goal: int
    expedition_mode: bool
    attempted_urls: set[str] = field(default_factory=set)
    attempted_domains: set[str] = field(default_factory=set)
    usable_domains: set[str] = field(default_factory=set)
    productive_domains: set[str] = field(default_factory=set)
    retained_domains: set[str] = field(default_factory=set)
    search_candidate_domains: set[str] = field(default_factory=set)
    overflow_probe_domains: set[str] = field(default_factory=set)
    overflow_probe_attempted_urls: set[str] = field(default_factory=set)
    confirmed_domains: set[str] = field(default_factory=set)
    priced_domains: set[str] = field(default_factory=set)
    exhausted_domains: set[str] = field(default_factory=set)
    released_domains: set[str] = field(default_factory=set)
    confirmed_entities: int = 0

    @classmethod
    def for_project(cls, project: ResearchProject) -> ResearchCoverage:
        return cls(
            specific_target=bool(
                any(term.strip() for term in project.analysis.target_identity_terms)
                and any(
                    term.strip()
                    for term in project.analysis.target_identity_anchor_terms
                )
            ),
            source_goal=project.crawl.max_domains,
            expedition_mode=project.crawl.mode == "expedition",
        )

    @property
    def needs_evidence(self) -> bool:
        # The supported market/price research modes need priced offerings.
        return self.specific_target and len(self.priced_domains) < self.source_goal

    def observe_entities(self, domain: str, entities: list[MarketEntity]) -> int:
        if entities:
            self.productive_domains.add(domain)

            if (
                self.expedition_mode
                and not self.specific_target
                and len(self.retained_domains) < self.source_goal
            ):
                self.retained_domains.add(domain)
        confirmed = [
            entity for entity in entities
            if entity.is_relevant
            and entity.attributes.get("target_identity_status") == "confirmed"
        ]
        if confirmed:
            self.confirmed_domains.add(domain)
        if any(entity.price is not None for entity in confirmed):
            self.priced_domains.add(domain)
        self.confirmed_entities += len(confirmed)
        return len(confirmed)

    def occupied_domains(self, activated: set[str]) -> set[str]:
        # Expedition broad research retains evidence-bearing sources only.
        # Preserve the existing slot rule for other crawl modes.
        if self.specific_target:
            retained = self.priced_domains
        elif self.expedition_mode:
            retained = self.retained_domains
        else:
            retained = self.usable_domains
        return (activated - self.exhausted_domains) | retained

    def snapshot(self) -> dict[str, object]:
        return {
            "attempted_pages": len(self.attempted_urls),
            "attempted_domains": sorted(self.attempted_domains),
            "usable_domains": sorted(self.usable_domains),
            "productive_domains": sorted(self.productive_domains),
            "retained_domains": sorted(self.retained_domains),
            "search_candidate_domains":
                sorted(self.search_candidate_domains),
            "search_candidate_domains_discovered":
                len(self.search_candidate_domains),
            "search_candidate_domains_probed":
                len(
                    self.attempted_domains
                    & self.search_candidate_domains
                ),
            "overflow_probe_domains":
                sorted(self.overflow_probe_domains),
            "overflow_probe_pages":
                len(self.overflow_probe_attempted_urls),
            "confirmed_domains": sorted(self.confirmed_domains),
            "priced_domains": sorted(self.priced_domains),
            "exhausted_domains": sorted(self.exhausted_domains),
            "released_domains": sorted(self.released_domains),
            "confirmed_targets": self.confirmed_entities,
            "source_goal": self.source_goal,
        }
