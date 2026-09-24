from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

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

    @property
    def headers(self):
        return {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return FakeResponse(
            url=url,
            text=self.pages.get(url, "<html></html>"),
            status_code=200 if url in self.pages else 404,
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


def make_project(
    project_id: str,
    *,
    soft_cap: int,
    penalty: int = 30,
) -> ResearchProject:
    return ResearchProject.model_validate({
        "id": project_id,
        "name": project_id,
        "keywords": ["research"],
        "seed_urls": ["https://seed.example/start"],
        "crawl": {
            "mode": "discovery",
            "max_pages_total": 2,
            "max_pages_per_domain": 5,
            "max_domains": 2,
            "max_depth": 3,
            "delay_seconds": 0,
            "respect_robots": False,
            "external_link_threshold": 35,
            "discover_sitemaps": False,
            "discover_feeds": False,
            "entity_diversity_soft_cap": soft_cap,
            "entity_diversity_priority_penalty": penalty,
        },
        "search": {
            "provider": "none",
            "max_queries": 0,
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
        },
    })


internal_url = "https://seed.example/product/research/internal"
external_url = "https://other.example/product/research/external"

seed_html = f"""
<html>
<head>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Research Product",
  "url": "https://seed.example/product/research-product",
  "description": "Research product for diversity test",
  "offers": {{
    "@type": "Offer",
    "price": "19.99",
    "priceCurrency": "EUR"
  }}
}}
</script>
</head>
<body>
<a href="{internal_url}">research internal product</a>
<a href="{external_url}">research external product</a>
</body>
</html>
"""

pages = {
    "https://seed.example/start": seed_html,
    internal_url: "<html><body>internal</body></html>",
    external_url: "<html><body>external</body></html>",
}


def run(project: ResearchProject):
    crawler = ResearchCrawler(
        settings,
        project,
        NoOpAI(),
    )
    crawler.session = FakeSession(pages)
    result = crawler.crawl()
    return crawler, result


# Baseline: diversity disabled, same-domain URL keeps its normal priority bonus.
baseline_crawler, baseline = run(
    make_project(
        "diversity_baseline",
        soft_cap=0,
    )
)

assert baseline_crawler.session.calls == [
    "https://seed.example/start",
    internal_url,
]
assert len(baseline.entities) == 1
assert baseline.diversity_penalties_applied == 0
assert baseline.diversity_domains_penalized == set()

# Adaptive diversity: after the first seed-domain entity, the next same-domain
# URL receives a soft priority penalty. The external active source is explored
# first, while the entity itself remains retained.
adaptive_crawler, adaptive = run(
    make_project(
        "diversity_adaptive",
        soft_cap=1,
        penalty=30,
    )
)

assert adaptive_crawler.session.calls == [
    "https://seed.example/start",
    external_url,
]
assert len(adaptive.entities) == 1
assert adaptive.entities[0].source_domain == "seed.example"
assert adaptive.diversity_penalties_applied == 1
assert adaptive.diversity_domains_penalized == {"seed.example"}
assert adaptive.domains["other.example"].status == "active"

print("ADAPTIVE SOURCE DIVERSITY TEST OK")
print("baseline_second=seed.example")
print("adaptive_second=other.example")
print("entities_retained=1")
print("soft_cap=1 priority_penalty=30")
