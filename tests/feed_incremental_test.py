from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from dataclasses import dataclass

from spriditis.crawler.feed_discovery import FeedDiscovery


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int
    headers: dict


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        headers = kwargs.get("headers", {})
        self.calls.append((url, dict(headers)))

        if headers.get("If-None-Match") == '"feed-v1"':
            return FakeResponse(
                url="https://example.com/canonical/feed.xml",
                text="",
                status_code=304,
                headers={"ETag": '"feed-v1"'},
            )

        return FakeResponse(
            url="https://example.com/canonical/feed.xml",
            text="""
            <rss version="2.0"><channel>
              <item>
                <guid>new-2</guid>
                <title>Ergonomic chair 2</title>
                <link>https://example.com/product/2</link>
                <pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate>
              </item>
              <item>
                <guid>old-1</guid>
                <title>Ergonomic chair 1</title>
                <link>https://example.com/product/1</link>
                <pubDate>Wed, 23 Sep 2026 08:00:00 GMT</pubDate>
              </item>
            </channel></rss>
            """,
            status_code=200,
            headers={
                "Content-Type": "application/rss+xml",
                "ETag": '"feed-v1"',
                "Last-Modified": "Thu, 24 Sep 2026 08:00:00 GMT",
            },
        )


def main():
    page = """
    <html><head>
      <link rel="alternate"
            type="application/rss+xml"
            href="/feed.xml">
    </head><body></body></html>
    """

    session = FakeSession()
    discovery = FeedDiscovery(
        session,
        user_agent="SpriditisTest/1.0",
        timeout=1,
    )

    first = discovery.scan(
        "https://example.com/catalog",
        page,
        previous_states={},
        max_entries=20,
        max_feeds=3,
        probe_common_paths=False,
    )

    assert first.candidate_count == 1
    assert first.errors == 0
    assert len(first.fetches) == 1
    fetched = first.fetches[0]
    assert fetched.state.feed_type == "rss"
    assert fetched.state.etag == '"feed-v1"'
    assert fetched.state.feed_url == "https://example.com/feed.xml"
    assert [e.entry_id for e in fetched.new_entries] == ["new-2", "old-1"]

    previous = {fetched.state.feed_url: fetched.state}

    second = discovery.scan(
        "https://example.com/catalog",
        page,
        previous_states=previous,
        max_entries=20,
        max_feeds=3,
        probe_common_paths=False,
    )

    assert len(second.fetches) == 1
    assert second.fetches[0].not_modified is True
    assert second.fetches[0].state.status == "active"
    assert second.fetches[0].state.feed_url == "https://example.com/feed.xml"
    assert second.fetches[0].new_entries == []
    assert session.calls[-1][1]["If-None-Match"] == '"feed-v1"'
    assert "If-Modified-Since" in session.calls[-1][1]

    print("FEED INCREMENTAL TEST OK")


if __name__ == "__main__":
    main()
