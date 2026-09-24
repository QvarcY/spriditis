from __future__ import annotations

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    query: str
    reason: str = "generated"


class SearchHit(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    engine: str = ""
    provider_score: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
