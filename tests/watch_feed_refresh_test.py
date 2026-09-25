from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.storage.database import Database


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200
    headers: dict | None = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        self.calls.append((url, headers))

        if url == "https://watch.example/catalog":
            return FakeResponse(
                url=url,
                text="""
                <html><head>
                  <link rel="alternate"
                        type="application/rss+xml"
                        href="/feed.xml">
                </head><body><h1>Catalog</h1></body></html>
                """,
                headers={"Content-Type": "text/html; charset=utf-8"},
            )

        if url == "https://watch.example/feed.xml":
            if headers.get("If-None-Match") == '"feed-v1"':
                return FakeResponse(
                    url=url,
                    text="",
                    status_code=304,
                    headers={"ETag": '"feed-v1"'},
                )

            return FakeResponse(
                url=url,
                text="""
                <rss version="2.0"><channel>
                  <item>
                    <guid>item-1</guid>
                    <title>Personalized gift</title>
                    <link>https://watch.example/product/1</link>
                    <pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate>
                  </item>
                </channel></rss>
                """,
                headers={
                    "Content-Type": "application/rss+xml",
                    "ETag": '"feed-v1"',
                    "Last-Modified":
                        "Thu, 24 Sep 2026 08:00:00 GMT",
                },
            )

        return FakeResponse(
            url=url,
            text="<html><body>not found</body></html>",
            status_code=404,
            headers={"Content-Type": "text/html"},
        )


class NoOpAI(AIProvider):
    def enrich(self, entity, project):
        return EntityEnrichment(
            is_relevant=True,
            confidence=1.0,
            relevance_score=1.0,
            category="test",
            tags=[],
            attributes={},
            opportunity_notes="",
        )


project = ResearchProject.model_validate(
    {
        "id": "watch_feed_refresh",
        "name": "Watch feed refresh",
        "research_type": "product_market",
        "entity_type": "product",
        "keywords": ["gift"],
        "seed_urls": ["https://watch.example/catalog"],
        "crawl": {
            "mode": "domain",
            "max_pages_total": 1,
            "max_pages_per_domain": 1,
            "max_domains": 1,
            "max_depth": 2,
            "delay_seconds": 0,
            "respect_robots": False,
            "discover_sitemaps": False,
            "discover_feeds": True,
            "probe_common_feed_paths": False,
            "max_feeds_per_domain": 3,
            "max_feed_entries_per_feed": 20,
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
            "min_relevance_score": 0.35,
            "categories": ["gift"],
            "desired_attributes": [],
        },
    }
)


def settings(db_path):
    return AppSettings(
        gemini_api_key="",
        gemini_model="none",
        gemini_batch_size=10,
        gemini_requests_per_minute=5,
        gemini_max_retries=0,
        gemini_retry_base_seconds=1.0,
        db_path=db_path,
        legacy_db_path=None,
        report_dir=db_path.parent / "reports",
        smtp_host="",
        smtp_port=465,
        smtp_user="",
        smtp_app_password="",
        report_to="",
        send_email=False,
        user_agent="SpriditisWatchFeedTest/1.0",
        request_timeout_seconds=1,
    )


with TemporaryDirectory() as tmp:
    db_path = _BootstrapPath(tmp) / "spriditis.db"
    app_settings = settings(db_path)
    session = FakeSession()
    db = Database(db_path)

    try:
        db.save_project(project)

        # First completed Watch-like cycle: normal 200 feed response.
        run_a = db.start_run(project)
        crawler_a = ResearchCrawler(
            app_settings,
            project,
            NoOpAI(),
            feed_states=db.load_feed_states(project.id),
            domain_states=db.load_domain_states(project.id),
        )
        crawler_a.session = session
        result_a = crawler_a.crawl()

        assert result_a.feed_not_modified == 0
        assert result_a.feeds_found == 1
        assert result_a.feed_entries_new == 1
        assert (
            result_a.feed_states[
                "https://watch.example/feed.xml"
            ].etag
            == '"feed-v1"'
        )

        db.save_domain_registry(project, run_a, result_a)
        db.save_feed_states(project, run_a, result_a)
        db.save_page_visits(project, run_a, result_a)
        db.finish_run(run_a, result_a)

        persisted = db.load_feed_states(project.id)
        first_state = persisted["https://watch.example/feed.xml"]
        assert first_state.etag == '"feed-v1"'
        assert (
            first_state.last_modified
            == "Thu, 24 Sep 2026 08:00:00 GMT"
        )
        first_last_success = first_state.last_success
        first_entries_seen = first_state.entries_seen
        first_new_entries = first_state.new_entries

        assert db.compare_with_previous_run(project.id, run_a) is None

        # Second completed Watch-like cycle: persisted validators must
        # produce a conditional request and a 304 Not Modified outcome.
        run_b = db.start_run(project)
        crawler_b = ResearchCrawler(
            app_settings,
            project,
            NoOpAI(),
            feed_states=db.load_feed_states(project.id),
            domain_states=db.load_domain_states(project.id),
        )
        crawler_b.session = session
        result_b = crawler_b.crawl()

        assert result_b.feed_not_modified == 1
        assert result_b.feed_errors == 0
        assert result_b.feed_entries_new == 0

        feed_calls = [
            headers
            for url, headers in session.calls
            if url == "https://watch.example/feed.xml"
        ]
        assert len(feed_calls) == 2
        assert "If-None-Match" not in feed_calls[0]
        assert "If-Modified-Since" not in feed_calls[0]
        assert feed_calls[1]["If-None-Match"] == '"feed-v1"'
        assert (
            feed_calls[1]["If-Modified-Since"]
            == "Thu, 24 Sep 2026 08:00:00 GMT"
        )

        db.save_domain_registry(project, run_b, result_b)
        db.save_feed_states(project, run_b, result_b)
        db.save_page_visits(project, run_b, result_b)
        db.finish_run(run_b, result_b)

        second_state = db.load_feed_states(project.id)[
            "https://watch.example/feed.xml"
        ]
        assert second_state.status == "active"
        assert second_state.etag == '"feed-v1"'
        assert second_state.last_success == first_last_success
        assert second_state.entries_seen == first_entries_seen
        assert second_state.new_entries == first_new_entries

        snapshots_a = db.feed_snapshots(project.id, run_a)
        snapshots_b = db.feed_snapshots(project.id, run_b)
        assert len(snapshots_a) == 1
        assert len(snapshots_b) == 1
        assert snapshots_a[0]["status"] == "active"
        assert snapshots_b[0]["status"] == "active"
        assert snapshots_b[0]["etag"] == '"feed-v1"'

        trace_b = db.trace_run(project.id, run_b)
        assert trace_b is not None
        assert trace_b["run"]["feed_not_modified"] == 1

        diff = db.compare_with_previous_run(project.id, run_b)
        assert diff is not None
        assert diff["events"] == []
        assert diff["counts"]["FEED_APPEARED"] == 0
        assert diff["counts"]["FEED_DISAPPEARED"] == 0
        assert diff["counts"]["FEED_NEW_ENTRIES"] == 0
        assert diff["counts"]["FEED_FAILED"] == 0
        assert diff["counts"]["FEED_RECOVERED"] == 0
    finally:
        db.close()


print("WATCH FEED REFRESH TEST OK")
print("first_cycle=200_etag_persisted")
print("second_cycle=conditional_request")
print("if_none_match=reused_from_db")
print("if_modified_since=reused_from_db")
print("http_304=active_not_failure")
print("feed_not_modified=traceable")
print("unchanged_feed=no_change_event")
