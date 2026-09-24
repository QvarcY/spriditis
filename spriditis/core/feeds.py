from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FeedEntry:
    entry_id: str
    url: str
    title: str = ""
    published: str = ""
    summary: str = ""


@dataclass
class FeedState:
    feed_url: str
    domain: str
    feed_type: str = "unknown"
    status: str = "unknown"
    etag: str = ""
    last_modified: str = ""
    last_entry_id: str = ""
    last_published: str = ""
    last_checked: str = ""
    last_success: str = ""
    entries_seen: int = 0
    new_entries: int = 0
    last_error: str = ""
    first_seen: str = ""
    last_seen: str = ""
