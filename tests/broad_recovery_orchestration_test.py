from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from spriditis.ai.fallback import FallbackProvider
from spriditis.config import AppSettings
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.crawler.policy import (
    url_safety_reason,
)
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200

    @property
    def headers(self):
        return {
            "Content-Type":
                "text/html; charset=utf-8"
        }


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)

        if url not in self.pages:
            raise AssertionError(
                f"Unexpected crawl URL: {url}"
            )

        return FakeResponse(
            url=url,
            text=self.pages[url],
        )


initial_query = (
    "Acme Chair adjustable height"
)

recovery_query = (
    "adjustable height Acme Chair"
)

initial_url = (
    "https://initial.example/catalog/acme-chair"
)

weak_backfill_url = (
    "https://weak.example/catalog/acme-chair"
)

recovered_url = (
    "https://recovered.example/product/"
    "acme-chair-adjustable-height"
)


project = ResearchProject.model_validate(
    {
        "id": "broad-recovery-orchestration",
        "name": initial_query,
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["en"],
        "countries": [],
        "keywords": [
            "Acme",
            "Chair",
            "adjustable",
            "height",
        ],
        "negative_keywords": [],
        "seed_urls": [],
        "crawl": {
            "mode": "expedition",
            "max_pages_total": 3,
            "max_pages_per_domain": 1,
            "max_domains": 1,
            "max_probe_domains": 0,
            "max_probe_pages_total": 0,
            "max_depth": 1,
            "delay_seconds": 0,
            "respect_robots": False,
            "discover_sitemaps": False,
            "discover_feeds": False,
            "saturation_window": 0,
            "diminishing_returns_window": 0,
        },
        "search": {
            "provider": "none",
            "max_queries": 1,
            "max_recovery_queries": 1,
            "results_per_query": 5,
            "result_threshold": 20,
            "queries": [
                initial_query,
            ],
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
            "min_relevance_score": 0.35,
            "required_evidence_terms": [
                "adjustable",
                "height",
            ],
        },
    }
)


provider = FakeSearchProvider(
    {
        initial_query: [
            SearchHit(
                url=initial_url,
                title=(
                    "Acme Chair adjustable height"
                ),
                snippet="Catalog",
            ),
            SearchHit(
                url=weak_backfill_url,
                title="Acme Chair",
                snippet="Catalog",
            ),
        ],
        recovery_query: [
            SearchHit(
                url=recovered_url,
                title=(
                    "Acme Chair adjustable height"
                ),
                snippet=(
                    "Acme Chair adjustable height "
                    "100 EUR"
                ),
            ),
        ],
    }
)


settings = AppSettings(
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
    user_agent="SpriditisTest/3.3",
    request_timeout_seconds=1,
)


crawler = ResearchCrawler(
    settings,
    project,
    FallbackProvider(),
    search_provider=provider,
)

crawler.session = FakeSession(
    {
        initial_url: """
            <html>
            <body>
                No qualifying products.
            </body>
            </html>
        """,
        recovered_url: """
            <html>
            <head>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "Product",
              "name":
                "Acme Chair adjustable height",
              "description":
                "Acme Chair adjustable height",
              "offers": {
                "@type": "Offer",
                "price": "100",
                "priceCurrency": "EUR"
              }
            }
            </script>
            </head>
            <body>
                Acme Chair adjustable height
            </body>
            </html>
        """,
    }
)


result = crawler.crawl()


assert crawler.session.calls == [
    initial_url,
    recovered_url,
], crawler.session.calls

assert weak_backfill_url not in crawler.session.calls

assert result.search_queries_issued == 2

assert crawler._recovery_queries_issued == 1

assert any(
    item.stage == "discovery_recovery"
    and item.decision == "reformulate_queries"
    and item.signals.get("reason")
    == "broad_evidence_deficit"
    for item in result.adaptive_decisions
)

assert len(result.entities) == 1
assert result.entities[0].is_relevant
assert result.entities[0].price == 100.0

assert (
    "recovered.example"
    in crawler._coverage.productive_domains
)

assert (
    "recovered.example"
    in crawler._coverage.retained_domains
)


for url in (
    "https://wa.me/?text=example",
    "https://api.whatsapp.com/send?text=example",
    "https://web.whatsapp.com/send?text=example",
    "https://blog.whatsapp.com/example",
    "https://www.whatsappbusiness.com/example",
):
    safe, reason = url_safety_reason(url)

    assert not safe, url
    assert reason == "blocked_host", (
        url,
        reason,
    )


print(
    "BROAD RECOVERY ORCHESTRATION TEST OK"
)
print(
    "recovery_before_weak_backfill=True"
)
print(
    "qualified_recovery_source_retained=True"
)
print(
    "whatsapp_action_hosts=blocked"
)
