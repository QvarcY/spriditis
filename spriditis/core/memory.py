from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PageVisit:
    url: str
    final_url: str
    domain: str
    source_url: str = ""
    source_type: str = "unknown"
    depth: int = 0
    priority: int = 0
    outcome: str = "unknown"
    http_status: int | None = None
    content_type: str = ""
    visited_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
