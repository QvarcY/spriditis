from __future__ import annotations

from .base import SearchProvider
from .models import SearchHit


class FakeSearchProvider(SearchProvider):
    """Deterministic provider used by offline integration tests."""

    def __init__(self, responses: dict[str, list[SearchHit]], *, provider_name: str = "fake"):
        self.responses = responses
        self._name = provider_name
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def search(self, query: str, *, language: str, limit: int, safesearch: int) -> list[SearchHit]:
        self.calls.append(query)
        return list(self.responses.get(query, []))[:limit]
