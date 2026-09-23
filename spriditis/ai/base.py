from __future__ import annotations

from abc import ABC, abstractmethod

from spriditis.core.entities import EntityEnrichment, MarketEntity
from spriditis.core.projects import ResearchProject


class AIProvider(ABC):
    @abstractmethod
    def enrich(
        self,
        entity: MarketEntity,
        project: ResearchProject,
    ) -> EntityEnrichment:
        raise NotImplementedError

    def enrich_many(
        self,
        entities: list[MarketEntity],
        project: ResearchProject,
    ) -> list[EntityEnrichment]:
        """
        Default provider behavior.

        Vienkāršie provideri var neko īpašu nezināt par batching.
        Gemini šo metodi override un analizē vairākus objektus vienā requestā.
        """
        return [self.enrich(entity, project) for entity in entities]
