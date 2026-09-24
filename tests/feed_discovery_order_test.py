from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.crawler.feed_discovery import discover_feed_urls


def main():
    html = """
    <html><head>
      <link rel="alternate" type="application/rss+xml"
            href="https://github.blog/feed/">
      <link rel="alternate" type="application/rss+xml"
            href="https://github.blog/comments/feed/">
      <link rel="alternate" type="application/rss+xml"
            href="https://github.blog/changelog/feed/">
    </head></html>
    """

    feeds = discover_feed_urls(
        "https://github.blog/changelog/",
        html,
        probe_common_paths=False,
    )

    assert feeds == [
        "https://github.blog/changelog/feed",
        "https://github.blog/feed",
        "https://github.blog/comments/feed",
    ]

    print("FEED DISCOVERY ORDER TEST OK")


if __name__ == "__main__":
    main()
