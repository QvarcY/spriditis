from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from dataclasses import dataclass
from pathlib import Path

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200
    content_type: str = "text/html; charset=utf-8"
    extra_headers: dict | None = None

    @property
    def headers(self):
        result = {"Content-Type": self.content_type}
        if self.extra_headers:
            result.update(self.extra_headers)
        return result


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        response = self.responses.get(url)
        if response is None:
            return FakeResponse(
                url=url,
                text="<html><body>not found</body></html>",
                status_code=404,
            )
        return response


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


def project():
    return ResearchProject.model_validate(
        {
            "id": "feed_integration",
            "name": "Feed integration",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["ergonomic", "chair"],
            "negative_keywords": [],
            "seed_urls": ["https://seed.example/catalog"],
            "crawl": {
                "mode": "domain",
                "max_pages_total": 3,
                "max_pages_per_domain": 3,
                "max_domains": 1,
                "max_depth": 3,
                "delay_seconds": 0,
                "respect_robots": False,
                "discover_sitemaps": False,
                "discover_feeds": True,
                "probe_common_feed_paths": False,
                "max_feeds_per_domain": 3,
                "max_feed_entries_per_feed": 20
            },
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
                "min_relevance_score": 0.35,
                "categories": ["chair"],
                "desired_attributes": []
            }
        }
    )


def settings():
    return AppSettings(
        gemini_api_key="",
        gemini_model="none",
        gemini_batch_size=10,
        gemini_requests_per_minute=5,
        gemini_max_retries=0,
        gemini_retry_base_seconds=1.0,
        db_path=Path("data/test.db"),
        legacy_db_path=None,
        report_dir=Path("reports"),
        smtp_host="",
        smtp_port=465,
        smtp_user="",
        smtp_app_password="",
        report_to="",
        send_email=False,
        user_agent="SpriditisTest/1.0",
        request_timeout_seconds=1,
    )


def main():
    responses = {
        "https://seed.example/catalog": FakeResponse(
            url="https://seed.example/catalog",
            text="""
            <html><head>
              <link rel="alternate"
                    type="application/rss+xml"
                    href="/feed.xml">
            </head><body><h1>Catalog</h1></body></html>
            """,
        ),
        "https://seed.example/feed.xml": FakeResponse(
            url="https://seed.example/feed.xml",
            text="""
            <rss version="2.0"><channel>
              <item>
                <guid>chair-2</guid>
                <title>ergonomic chair</title>
                <link>https://seed.example/product/ergonomic-chair</link>
                <pubDate>Thu, 24 Sep 2026 08:00:00 GMT</pubDate>
              </item>
            </channel></rss>
            """,
            content_type="application/rss+xml",
            extra_headers={"ETag": '"feed-v1"'},
        ),
        "https://seed.example/product/ergonomic-chair": FakeResponse(
            url="https://seed.example/product/ergonomic-chair",
            text="<html><body><h1>Ergonomic chair</h1></body></html>",
        ),
    }

    crawler = ResearchCrawler(settings(), project(), NoOpAI())
    fake = FakeSession(responses)
    crawler.session = fake

    result = crawler.crawl()

    assert result.visited_pages == 2
    assert result.feed_candidates_seen == 1
    assert result.feeds_found == 1
    assert result.feed_entries_seen == 1
    assert result.feed_entries_new == 1
    assert result.feed_errors == 0
    assert "https://seed.example/feed.xml" in result.feed_states

    feed_events = [
        item for item in result.domain_discoveries
        if item.discovered_via == "feed"
    ]
    assert len(feed_events) == 1
    assert feed_events[0].target_url == (
        "https://seed.example/product/ergonomic-chair"
    )

    assert fake.calls == [
        "https://seed.example/catalog",
        "https://seed.example/feed.xml",
        "https://seed.example/product/ergonomic-chair",
    ]

    print("FEED CRAWLER INTEGRATION TEST OK")
    print("visited_pages=2")
    print("feeds_found=1")
    print("feed_entries_new=1")


if __name__ == "__main__":
    main()
