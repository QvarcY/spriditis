from __future__ import annotations

from abc import ABC, abstractmethod

from .models import SearchHit


class SearchProviderError(RuntimeError):
    """Structured SearchProvider failure safe for CLI/reporting."""

    def __init__(
        self,
        message: str,
        *,
        kind: str = "provider_error",
        status_code: int | None = None,
        retryable: bool = False,
        attempts: int = 1,
    ):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.retryable = retryable
        self.attempts = max(1, int(attempts))


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
