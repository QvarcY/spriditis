from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.feeds import FeedState
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


def main():
    project = ResearchProject.model_validate(
        {
            "id": "feed_storage",
            "name": "Feed storage",
            "research_type": "product_market",
            "entity_type": "product",
            "seed_urls": ["https://example.com"],
        }
    )

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "spriditis.db")
        try:
            db.save_project(project)
            result = ResearchRunResult(project_id=project.id)
            result.feed_states["https://example.com/feed.xml"] = FeedState(
                feed_url="https://example.com/feed.xml",
                domain="example.com",
                feed_type="rss",
                status="active",
                etag='"abc"',
                last_modified="Thu, 24 Sep 2026 08:00:00 GMT",
                last_entry_id="entry-2",
                last_published="2026-09-24T08:00:00Z",
                last_checked="2026-09-24T08:05:00+00:00",
                last_success="2026-09-24T08:05:00+00:00",
                entries_seen=2,
                new_entries=2,
                first_seen="2026-09-24T08:05:00+00:00",
                last_seen="2026-09-24T08:05:00+00:00",
            )
            db.save_feed_states(project, result)

            states = db.load_feed_states(project.id)
            state = states["https://example.com/feed.xml"]
            assert state.feed_type == "rss"
            assert state.etag == '"abc"'
            assert state.last_entry_id == "entry-2"
            assert state.entries_seen == 2

            rows = db.list_feeds(project.id)
            assert len(rows) == 1
            assert rows[0]["domain"] == "example.com"
        finally:
            db.close()

    print("FEED STORAGE TEST OK")


if __name__ == "__main__":
    main()
