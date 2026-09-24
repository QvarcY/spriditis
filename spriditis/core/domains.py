from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


DomainStatus = Literal[
    "candidate",
    "active",
    "blocked",
    "rejected",
    "failed",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DomainRecord(BaseModel):
    domain: str
    status: DomainStatus = "candidate"
    discovered_via: str = "link"
    discovered_from_url: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)

    robots_status: str = "unknown"
    sitemap_status: str = "unknown"
    sitemap_urls_found: int = 0

    pages_seen: int = 0
    entities_found: int = 0

    first_seen: str = Field(default_factory=utc_now)
    last_seen: str = Field(default_factory=utc_now)
    last_crawled: str | None = None

    reason: str = ""


class DomainDiscovery(BaseModel):
    source_domain: str = ""
    target_domain: str
    source_url: str = ""
    target_url: str
    anchor_text: str = ""
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    action: str = "recorded"
    reason: str = ""
    discovered_via: str = "external_link"
    provider: str = ""
    query_text: str = ""
    discovered_at: str = Field(default_factory=utc_now)
