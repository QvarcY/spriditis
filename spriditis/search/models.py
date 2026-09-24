from __future__ import annotations

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    query: str
    reason: str = "generated"
    memory_state: str = "untested"
    memory_productive_domain_rate: float | None = None
    memory_productive_domains: int = 0
    memory_unique_domains: int = 0
    memory_runs: int = 0


class SearchHit(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    engine: str = ""
    provider_score: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
