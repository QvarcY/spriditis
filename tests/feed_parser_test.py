from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.crawler.feed_discovery import parse_feed


def main():
    rss = """
    <rss version="2.0">
      <channel>
        <item>
          <guid>p2</guid>
          <title>Ergonomic chair 2</title>
          <link>https://example.com/product/2</link>
          <pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate>
          <description>mesh chair</description>
        </item>
        <item>
          <guid>p1</guid>
          <title>Ergonomic chair 1</title>
          <link>https://example.com/product/1</link>
        </item>
      </channel>
    </rss>
    """
    kind, entries = parse_feed(rss)
    assert kind == "rss"
    assert [e.entry_id for e in entries] == ["p2", "p1"]
    assert entries[0].url == "https://example.com/product/2"

    atom = """
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>a2</id>
        <title>Chair A2</title>
        <updated>2026-09-24T08:00:00Z</updated>
        <link rel="alternate" href="https://example.com/product/a2"/>
      </entry>
    </feed>
    """
    kind, entries = parse_feed(atom)
    assert kind == "atom"
    assert entries[0].entry_id == "a2"
    assert entries[0].url.endswith("/product/a2")

    json_feed = """
    {
      "version": "https://jsonfeed.org/version/1.1",
      "items": [
        {
          "id": "j2",
          "url": "https://example.com/product/j2",
          "title": "Chair J2",
          "date_published": "2026-09-24T08:00:00Z"
        }
      ]
    }
    """
    kind, entries = parse_feed(
        json_feed,
        content_type="application/feed+json",
    )
    assert kind == "jsonfeed"
    assert entries[0].entry_id == "j2"

    kind, entries = parse_feed("<broken")
    assert kind == "invalid"
    assert entries == []

    print("FEED PARSER TEST OK")


if __name__ == "__main__":
    main()
