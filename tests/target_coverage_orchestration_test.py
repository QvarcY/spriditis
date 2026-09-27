from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spriditis.ai.fallback import FallbackProvider
from spriditis.config import load_settings
from spriditis.core.projects import ResearchProject
from spriditis.core.domains import DomainRecord
from spriditis.crawler.async_http import AsyncHTTPResult
from spriditis.crawler.engine import ResearchCrawler
from spriditis.reports.html import _analytics
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.models import SearchHit


QUERY = "Find Bambu Lab P1S Combo offers"
A = "https://a.example/p1s-combo"
B = "https://b.example/p1s-combo"
C = "https://c.example/p1s-combo"


def page(*titles, price=599, description="", links=()):
    products = [
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": title,
            "description": description,
            **({"offers": {"@type": "Offer", "price": price, "priceCurrency": "EUR"}}
               if price is not None else {}),
        }
        for title in titles
    ]
    return '<html><script type="application/ld+json">' + json.dumps(products) + '</script>' + ''.join(
        f'<a href="{url}">Bambu Lab P1S Combo</a>' for url in links
    ) + '</html>'


WRONG = page("Bambu Lab P2S Combo", "Bambu Lab X2D Combo", "BAMBU LAB")
RIGHT = page("Bambu Lab P1S Combo")


def hits(*urls):
    return [SearchHit(url=url, title="Bambu Lab P1S Combo", snippet="") for url in urls]


class CountingAI(FallbackProvider):
    def __init__(self):
        self.keys = []

    def enrich(self, entity, project):
        self.keys.append(entity.stable_key)
        return super().enrich(entity, project)


class Transport:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        status, html = value if isinstance(value, tuple) else (200, value)
        return SimpleNamespace(
            url=url, text=html, status_code=status, headers={"Content-Type": "text/html"},
        )

    async def fetch(self, url):
        try:
            response = self.get(url)
        except requests.RequestException as exc:
            return AsyncHTTPResult(
                requested_url=url, final_url=url, status_code=None,
                error_type=type(exc).__name__, error_message=str(exc),
            )
        return AsyncHTTPResult(
            requested_url=url, final_url=url, status_code=response.status_code,
            text=response.text, headers=response.headers,
        )


def run(search_results, pages, *, async_enabled=False, page_cap=8,
        domain_cap=1, per_domain=1, recovery=0, robots_block=(), required=(),
        domain_states=None, sitemap_urls=None, specific_target=True):
    project = ResearchProject.model_validate({
        "id": "target_coverage_test", "name": QUERY,
        "keywords": ["Bambu", "Lab", "P1S", "Combo"],
        "languages": ["en"], "countries": ["LV"],
        "crawl": {
            "mode": "expedition", "max_domains": domain_cap,
            "max_pages_total": page_cap, "max_pages_per_domain": per_domain,
            "max_depth": 2, "delay_seconds": 0, "respect_robots": bool(robots_block),
            "discover_sitemaps": sitemap_urls is not None, "discover_feeds": False,
            "max_sitemap_urls_per_domain": 30,
            "saturation_window": 1, "diminishing_returns_window": 1,
            "async_enabled": async_enabled, "async_max_retries": 0,
        },
        "search": {"queries": [QUERY], "max_queries": 1, "max_recovery_queries": recovery},
        "analysis": {
            "ai_enabled": False, "ai_provider": "none",
            "target_identity_terms": ["P1S", "Combo"] if specific_target else [],
            "target_identity_anchor_terms": ["P1S"] if specific_target else [],
            "required_evidence_terms": list(required),
        },
    })
    transport = Transport(pages)
    ai = CountingAI()
    provider = FakeSearchProvider(search_results)
    crawler = ResearchCrawler(
        load_settings(), project, ai, search_provider=provider,
        async_transport=transport if async_enabled else None,
        domain_states=domain_states,
    )
    crawler.session = transport
    crawler.robots.can_fetch = lambda url: url not in robots_block
    if sitemap_urls is not None:
        crawler.sitemaps.discover = lambda url, **kwargs: SimpleNamespace(
            status="found", urls=sitemap_urls.get(url, [])[:kwargs["max_urls"]],
        )
    result = crawler.crawl()
    assert len(ai.keys) == len(set(ai.keys)), "An entity was enriched twice"
    assert len(crawler._coverage.attempted_urls) <= page_cap
    assert result.search_queries_issued <= 1 + recovery
    assert [d for d in result.adaptive_decisions if d.stage == "stop"][-1].decision == result.stop_reason
    return crawler, result, transport


for async_enabled in (False, True):
    # Reproduce the three extracted entities / zero confirmed failure.
    crawler, result, transport = run(
        {QUERY: hits(A, B)}, {A: WRONG, B: RIGHT}, async_enabled=async_enabled,
    )
    assert transport.calls == [A, B]
    assert result.domains["a.example"].status == "active"
    assert result.domains["a.example"].entities_found == 3
    assert result.search_domains_activated == 2
    stop = next(d for d in result.adaptive_decisions if d.stage == "stop")
    assert stop.signals["active_domains"] == 2, "Audit must retain both activations"
    first = next(d for d in result.adaptive_decisions if d.stage == "target_coverage")
    assert first.signals["extracted_entities"] == 3
    assert first.signals["new_confirmed_targets"] == 0
    assert crawler._coverage.productive_domains == {"a.example", "b.example"}
    assert crawler._coverage.confirmed_domains == {"b.example"}
    assert _analytics(result.entities)["priced"] == 1
    assert _analytics(result.entities)["min_price"] == 599

    crawler, result, transport = run(
        {QUERY: hits(A, B, "https://b.example/cart")},
        {A: (403, "Forbidden"), B: RIGHT}, async_enabled=async_enabled,
    )
    assert transport.calls == [A, B], "Backfill must preserve URL safety"

    # A saved active source still needs a run-local useful-source slot.
    crawler, result, transport = run(
        {QUERY: hits(A, B)}, {A: WRONG, B: RIGHT}, async_enabled=async_enabled,
        domain_states={"b.example": DomainRecord(domain="b.example", status="active")},
    )
    assert transport.calls == [A, B]
    first_b = next(d for d in result.domain_discoveries if d.target_domain == "b.example")
    assert first_b.reason == "domain_budget_reached"

    # Probe the current domain up to its cap before replacing it.
    detail = "https://a.example/detail"
    crawler, result, transport = run({QUERY: hits(A, B)}, {
        A: page("Bambu Lab P2S Combo", links=[detail]), detail: WRONG, B: RIGHT,
    }, per_domain=2, async_enabled=async_enabled)
    assert transport.calls == [A, detail, B]

    crawler, result, transport = run({QUERY: hits(A, B)}, {
        A: page("Bambu Lab P1S Combo", price=None), B: RIGHT,
    }, async_enabled=async_enabled)
    assert transport.calls == [A, B]
    assert crawler._coverage.priced_domains == {"b.example"}

    # Recovery runs only after the initial candidate pool has been explored.
    crawler, result, transport = run({
        QUERY: hits(A),
        "Bambu Lab P1S Combo Latvia": hits(B),
        "Bambu Lab P1S Combo price": hits(C),
    }, {A: WRONG, B: RIGHT, C: RIGHT}, domain_cap=2, recovery=2,
        async_enabled=async_enabled)
    assert set(transport.calls) == {A, B, C}
    assert result.search_queries_issued == 3
    assert crawler._coverage.priced_domains == {"b.example", "c.example"}
    assert result.stop_reason != "insufficient_target_coverage"

    # Failed and robots-denied attempts are bounded and retain audit semantics.
    for failure in ((403, "Forbidden"), requests.ConnectionError("offline"), "robots"):
        crawler, result, transport = run(
            {QUERY: hits(A, B)}, {A: failure if failure != "robots" else WRONG, B: RIGHT},
            async_enabled=async_enabled, robots_block=[A] if failure == "robots" else [],
        )
        assert B in transport.calls
        assert "a.example" in crawler._coverage.attempted_domains
        if failure == "robots":
            assert result.domains["a.example"].robots_status == "blocked"
            assert result.domains["a.example"].status == "active"
        else:
            assert result.domains["a.example"].status == "failed"

    crawler, result, transport = run(
        {QUERY: hits(A, B, C)},
        {A: requests.ConnectionError("offline"), B: requests.ConnectionError("offline")},
        page_cap=2, recovery=2, async_enabled=async_enabled,
    )
    assert transport.calls == [A, B]
    assert result.visited_pages == 0
    assert result.stop_reason == "insufficient_target_coverage"
    assessment = next(d for d in result.adaptive_decisions if d.stage == "coverage_assessment")
    assert assessment.signals["previous_stop_reason"] == "max_page_attempts"

    # Matching identity without the required evidence cannot fill a source slot.
    crawler, result, transport = run(
        {QUERY: hits(A, B)}, {A: RIGHT, B: page("Bambu Lab P1S Combo", description="warranty")},
        required=["warranty"], async_enabled=async_enabled,
    )
    assert transport.calls == [A, B]
    assert crawler._coverage.confirmed_domains == {"b.example"}

    # Exhausted discovery is an honest insufficient result, never a soft success.
    crawler, result, transport = run({QUERY: hits(A)}, {A: WRONG}, recovery=2,
        async_enabled=async_enabled)
    assert result.stop_reason == "insufficient_target_coverage"
    assert result.search_queries_issued == 3
    assert not crawler._coverage.confirmed_domains

    # A hard page ceiling prevents further queries even with zero confirmations.
    crawler, result, transport = run({QUERY: hits(A, B)}, {A: WRONG}, page_cap=1,
        recovery=2, async_enabled=async_enabled)
    assert result.stop_reason == "insufficient_target_coverage"
    assert result.search_queries_issued == 1

    # Deferred HTML discovery remains usable when the original slot is exhausted.
    crawler, result, transport = run({QUERY: hits(A)}, {
        A: page("Bambu Lab P2S Combo", links=[B]), B: RIGHT,
    }, async_enabled=async_enabled)
    assert transport.calls == [A, B]
    assert any(d.stage == "discovery_backfill" for d in result.adaptive_decisions)

    # Live failure: priced and unpriced target sources expose navigation noise.
    # Neither HTML nor thirty sitemap candidates may starve recovery search.
    for continuation in ("html", "sitemap", "both"):
        maps = {} if continuation != "html" else None
        pages = {C: RIGHT}
        noise_urls = set()
        for url, price in ((A, 606), (B, None)):
            origin = url.rsplit("/", 1)[0]
            noise = [origin + path for path in (
                "/sign-in", "/orders/status", "/televisions", "/products/tv",
                "/sign-in?return=%2Fp1s-combo", "/products/p1smax-combo",
            )]
            html = page("Bambu Lab P1S Combo", price=price)
            if continuation != "sitemap":
                html += ''.join(f'<a href="{link}">Store navigation</a>' for link in noise)
                noise_urls.update(noise)
            if maps is not None:
                maps[url] = [f"{origin}/catalog/page-{i}" for i in range(30)]
                noise_urls.update(maps[url])
            pages[url] = html
        pages.update({url: "<html>Unrelated navigation</html>" for url in noise_urls})
        search = {QUERY: hits(A, B), "Bambu Lab P1S Combo Latvia": hits(C)}
        crawler, result, transport = run(
            search, pages, domain_cap=2, per_domain=4, page_cap=6, recovery=1,
            sitemap_urls=maps, async_enabled=async_enabled,
        )
        assert transport.calls == [A, B, C], "Navigation noise starved recovery"
        recovery_event = next(d for d in result.adaptive_decisions if d.stage == "discovery_recovery")
        assert recovery_event.signals["attempted_pages"] == 2
        assert recovery_event.signals["priced_domains"] == ["a.example"]
        assert result.search_queries_issued == 2
        assert crawler._coverage.priced_domains == {"a.example", "c.example"}
        discarded = [d for d in result.adaptive_decisions if d.stage == "target_continuation"]
        assert {d.target for d in discarded} == noise_urls
        assert all(d.decision == "discarded" for d in discarded)
        if maps is not None:
            assert result.domains["a.example"].sitemap_urls_found == 30
            assert result.domains["b.example"].sitemap_urls_found == 30

        # The same navigation remains crawlable for broad research.
        _, broad, broad_transport = run(
            search, pages, domain_cap=2, per_domain=4, page_cap=6, recovery=1,
            sitemap_urls=maps, specific_target=False, async_enabled=async_enabled,
        )
        assert any(url in noise_urls for url in broad_transport.calls)
        assert broad.search_queries_issued == 1
        assert not any(d.stage == "target_continuation" for d in broad.adaptive_decisions)

    # A target-bearing sitemap path still deserves continuation before recovery.
    priced_detail = "https://b.example/products/%50%31%53-combo"
    crawler, result, transport = run({QUERY: hits(B)}, {
        B: page("Bambu Lab P1S Combo", price=None), priced_detail: RIGHT,
    }, per_domain=4, page_cap=3, recovery=1, async_enabled=async_enabled,
        sitemap_urls={B: ["https://b.example/televisions", priced_detail]})
    assert transport.calls == [B, priced_detail]
    assert result.search_queries_issued == 1
    assert crawler._coverage.priced_domains == {"b.example"}

print("TARGET COVERAGE ORCHESTRATION TEST OK (sequential and async)")
