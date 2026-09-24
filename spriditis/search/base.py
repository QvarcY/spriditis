from __future__ import annotations

from abc import ABC, abstractmethod

from .models import SearchHit


class SearchProviderError(RuntimeError):
    pass


class SearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        language: str,
        limit: int,
        safesearch: int,
    ) -> list[SearchHit]:
        raise NotImplementedError
