from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.entities import EntityEnrichment
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.crawler.policy import text_relevance_score
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200

    @property
    def headers(self):
        return {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers = {}
        self.calls: list[str] = []

    def get(self, url: str, **kwargs):
        self.calls.append(url)
        return FakeResponse(
            url=url,
            text=self.pages[url],
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


def make_project() -> ResearchProject:
    return ResearchProject.model_validate({
        "id": "promising-probe-continuation",
        "name": "engraved keychain",
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["en"],
        "countries": [],
        "keywords": [
            "engraved",
            "keychain",
        ],
        "negative_keywords": [
            "jobs",
        ],
        "seed_urls": [],
        "crawl": {
            "mode": "expedition",
            "max_pages_total": 3,
            "max_pages_per_domain": 4,
            "max_domains": 1,
            "max_depth": 3,
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
            "results_per_query": 1,
            "result_threshold": 20,
            "queries": [
                "engraved keychain",
            ],
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    })


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


# --------------------------------------------------
# CASE 1
#
# The search result lands on a shop landing page.
# Useful product evidence is two internal hops deeper.
#
# Without C1, Phase B retires the source after page 2.
# With C1, strong internal-link evidence grants exactly
# one extra provisional page.
# --------------------------------------------------

query = "engraved keychain"

landing = "https://shop.example/"
category = (
    "https://shop.example/shop/collection"
)
product = (
    "https://shop.example/product/"
    "personalized-engraved-keychain"
)
competing_item = "https://shop.example/item/12345"

crawler = ResearchCrawler(
    settings,
    make_project(),
    NoOpAI(),
    search_provider=FakeSearchProvider({
        query: [
            SearchHit(
                url=landing,
                title="Engraved keychain shop",
                snippet=(
                    "Custom engraved keychain collection"
                ),
            )
        ]
    }),
)

crawler.session = FakeSession({
    landing: f"""
        <html>
        <body>
            <a href="{competing_item}">
                View item
            </a>
            <a href="{category}">
                Engraved collection
            </a>
        </body>
        </html>
    """,
    competing_item: """
        <html>
        <body>
            Generic unrelated item.
        </body>
        </html>
    """,
    category: f"""
        <html>
        <body>
            <a href="{product}">
                Personalized engraved keychain
            </a>
        </body>
        </html>
    """,
    product: """
        <html>
        <head>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "Product",
              "name": "Personalized engraved keychain",
              "offers": {
                "@type": "Offer",
                "price": "12.50",
                "priceCurrency": "EUR"
              }
            }
            </script>
        </head>
        <body>
            Personalized engraved keychain
        </body>
        </html>
    """,
})

result = crawler.crawl()

assert crawler.session.calls == [
    landing,
    category,
    product,
]

assert result.visited_pages == 3

assert len(result.entities) == 1
assert (
    result.entities[0].title
    == "Personalized engraved keychain"
)
assert result.entities[0].price == 12.5

assert (
    result.domains["shop.example"].status
    == "active"
)
assert (
    result.domains["shop.example"].entities_found
    == 1
)

probe_decisions = [
    item
    for item in result.adaptive_decisions
    if (
        item.stage == "source_probe"
        and item.decision == "continuation_granted"
    )
]

assert len(probe_decisions) == 1

decision = probe_decisions[0]

assert decision.target == "shop.example"
assert (
    decision.signals["reason"]
    == "strong_internal_link_evidence"
)
assert decision.signals["trial_page_limit"] == 3
assert decision.signals["link_score"] >= 20


# Structural URL shape alone must not grant the extra page.
# /item/ receives a strong generic URL-shape score, but there is
# no actual subject evidence for engraved keychains.
generic_item = competing_item
generic_context = "View item"

generic_score = text_relevance_score(
    crawler.project,
    generic_item,
    generic_context,
)

assert generic_score >= crawler.project.search.result_threshold

assert not crawler._promising_probe_link(
    generic_item,
    generic_context,
    generic_score,
)


# --------------------------------------------------
# CASE 2
#
# Ordinary navigation does not count as useful
# page-level evidence. The existing Phase B two-page
# trial therefore remains unchanged.
# --------------------------------------------------

empty_landing = "https://empty.example/"
about = "https://empty.example/about"
contact = "https://empty.example/contact"

empty_crawler = ResearchCrawler(
    settings,
    make_project(),
    NoOpAI(),
    search_provider=FakeSearchProvider({
        query: [
            SearchHit(
                url=empty_landing,
                title="Engraved keychain shop",
                snippet=(
                    "Custom engraved keychain collection"
                ),
            )
        ]
    }),
)

empty_crawler.session = FakeSession({
    empty_landing: f"""
        <html>
        <body>
            <a href="{about}">
                About us
            </a>
        </body>
        </html>
    """,
    about: f"""
        <html>
        <body>
            <a href="{contact}">
                Contact
            </a>
        </body>
        </html>
    """,
    contact: """
        <html>
        <body>
            Nothing relevant.
        </body>
        </html>
    """,
})

empty_result = empty_crawler.crawl()

assert empty_crawler.session.calls == [
    empty_landing,
    about,
]

assert empty_result.visited_pages == 2

assert (
    empty_result.domains["empty.example"].status
    == "candidate"
)

assert (
    empty_result.domains["empty.example"].reason
    == "nonproductive_source"
)

assert not any(
    item.stage == "source_probe"
    and item.decision == "continuation_granted"
    for item in empty_result.adaptive_decisions
)

print(
    "SEARCH PROMISING PROBE CONTINUATION TEST OK"
)
