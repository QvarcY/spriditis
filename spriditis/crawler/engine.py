from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.domains import DomainDiscovery, DomainRecord
from spriditis.core.entities import MarketEntity
from spriditis.core.feeds import FeedState
from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import AdaptiveDecision, ResearchRunResult
from spriditis.extraction.engine import extract_entities
from spriditis.search.base import SearchProvider, SearchProviderError
from spriditis.search.query import build_search_queries
from spriditis.search.relevance import LocalRelevance, local_relevance_signals
from spriditis.resolution.target import apply_target_identity_gate

from .async_coordinator import AsyncCrawlCoordinator, AsyncCrawlPolicy
from .async_http import AsyncHTTPResult, AsyncHTTPTransport
from .async_politeness import (
    AdaptivePolitenessController,
    AsyncRetryPolicy,
    AsyncRetryingFetcher,
)
from .async_wave import AsyncWavePlanner
from .coverage import ResearchCoverage
from .discovery import DomainRegistry, SitemapDiscovery
from .feed_discovery import FeedDiscovery
from .frontier import URLFrontier
from .policy import (
    host_key,
    is_safe_public_url,
    normalize_url,
    text_relevance_score,
)
from .robots import RobotsCache
from .safe_http import SafeSession


def _link_relevance_context(tag) -> str:
    """
    Use the surrounding table row when a link lives in tabular result data.

    Marketplaces and directories often keep year, price, location and other
    important evidence in sibling cells rather than inside the <a> itself.
    Navigation links outside tables keep their ordinary anchor text.
    """
    anchor = " ".join(tag.stripped_strings)

    row = tag.find_parent("tr")
    if row is None:
        return anchor

    row_text = " ".join(row.stripped_strings)

    if not row_text:
        return anchor

    return row_text[:2000]


class _AsyncResponseAdapter:
    def __init__(self, result: AsyncHTTPResult):
        self.url = result.final_url
        self.text = result.text
        self.status_code = int(result.status_code or 0)
        self.headers = result.headers


class ResearchCrawler:
    def __init__(
        self,
        settings: AppSettings,
        project: ResearchProject,
        ai: AIProvider,
        search_provider: SearchProvider | None = None,
        feed_states: dict[str, FeedState] | None = None,
        domain_states: dict[str, DomainRecord] | None = None,
        query_memory: list[dict] | None = None,
        source_profiles: list[dict] | None = None,
        async_transport=None,
        progress_callback: Callable[
            [str, dict[str, object]],
            None,
        ] | None = None,
    ):
        self.settings = settings
        self.project = project
        self.ai = ai
        self.search_provider = search_provider
        self.feed_states = dict(feed_states or {})
        self.domain_states = dict(domain_states or {})
        self.query_memory = list(query_memory or [])
        self.source_profiles = {
            str(row.get("domain", "")): dict(row)
            for row in (source_profiles or [])
            if row.get("domain")
        }
        self.async_transport = async_transport
        self._owns_async_transport = async_transport is None
        self.progress_callback = progress_callback
        self._search_candidate_pool: list[dict[str, object]] = []
        self._coverage = ResearchCoverage.for_project(project)
        self._issued_queries: set[str] = set()
        self._recovery_queries_issued = 0
        self._deferred_sources: list[tuple[DomainDiscovery, int, int]] = []
        self._promising_probe_domains: set[str] = set()

        self.session = SafeSession()
        self.session.headers.update(
            {
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": ",".join(project.languages) + ",en;q=0.7",
            }
        )

        self.robots = RobotsCache(
            self.session,
            settings.user_agent,
            settings.request_timeout_seconds,
        )

        self.sitemaps = SitemapDiscovery(
            self.session,
            user_agent=settings.user_agent,
            timeout=settings.request_timeout_seconds,
        )

    def _emit_progress(
        self,
        kind: str,
        **data: object,
    ) -> None:
        callback = self.progress_callback
        if callback is None:
            return

        try:
            callback(kind, dict(data))
        except Exception:
            # Progress reporting is observational. A consumer-side failure
            # must never break the research run itself.
            return

    def crawl(self) -> ResearchRunResult:
        try:
            return self._crawl_impl()
        finally:
            if (
                self._owns_async_transport
                and self.async_transport is not None
            ):
                self.async_transport.close()
                self.async_transport = None

    def _crawl_impl(self) -> ResearchRunResult:
        result = ResearchRunResult(project_id=self.project.id)
        self._coverage = ResearchCoverage.for_project(self.project)
        self._search_candidate_pool = []
        self._issued_queries = set()
        self._recovery_queries_issued = 0
        self._deferred_sources = []
        self._promising_probe_domains = set()

        frontier = URLFrontier()
        visited: set[str] = set()
        entity_keys: set[str] = set()
        pages_by_domain: Counter[str] = Counter()
        discovery_depth_activations: Counter[int] = Counter()
        sitemap_checked: set[str] = set()
        feed_checked: set[str] = set()

        registry = DomainRegistry(
            self.project,
            initial_records=self.domain_states,
        )

        seeds: list[str] = []

        for raw in self.project.seed_urls:
            url = normalize_url(raw)

            if url and is_safe_public_url(url):
                seeds.append(url)
                registry.add_seed(url)
                self._emit_progress(
                    "source_activated",
                    domain=host_key(url),
                    origin="seed",
                )
                frontier.add(
                    url,
                    priority=100,
                    depth=0,
                    source_type="seed",
                )

        if self.project.crawl.mode == "expedition":
            self._seed_from_search(frontier, registry, result)

        if not frontier and not self._coverage.specific_target:
            if self.project.crawl.mode == "expedition":
                raise ValueError(
                    "Expedition neieguva nevienu derīgu sākuma URL no seed vai SearchProvider."
                )
            raise ValueError("Projektam nav neviena derīga seed URL.")

        async_cache: dict[str, AsyncHTTPResult] = {}
        async_planner = None
        async_fetcher = None
        async_politeness = None
        if self.project.crawl.async_enabled:
            async_planner = AsyncWavePlanner(
                wave_size=min(
                    self.project.crawl.async_global_concurrency,
                    self.project.crawl.async_max_pending,
                ),
                max_pages_per_domain=
                    self.project.crawl.max_pages_per_domain,
            )
            async_politeness = AdaptivePolitenessController(
                base_delay_seconds=
                    self.project.crawl.delay_seconds,
                max_delay_seconds=
                    self.project.crawl
                    .async_max_domain_delay_seconds,
                retry_base_seconds=
                    self.project.crawl.async_retry_base_seconds,
            )
            async_fetcher = AsyncRetryingFetcher(
                transport=self._ensure_async_transport(),
                retry_policy=AsyncRetryPolicy(
                    max_retries=
                        self.project.crawl.async_max_retries,
                    retry_base_seconds=
                        self.project.crawl.async_retry_base_seconds,
                    max_retry_delay_seconds=
                        self.project.crawl
                        .async_max_domain_delay_seconds,
                ),
                politeness=async_politeness,
            )

        while True:
            if not self._replenish_sources(
                frontier, registry, result, visited, pages_by_domain,
                discovery_depth_activations,
            ):
                break
            if (
                len(self._coverage.attempted_urls)
                >= self.project.crawl.max_pages_total
                and not async_cache
            ):
                break
            if async_planner is not None:
                if not async_cache:
                    self._prefetch_async_wave(
                        frontier=frontier,
                        planner=async_planner,
                        cache=async_cache,
                        visited=visited,
                        pages_by_domain=pages_by_domain,
                        registry=registry,
                        result=result,
                        fetcher=async_fetcher,
                    )
                if not frontier:
                    continue

            item = frontier.pop()
            url = item.url

            if url in visited:
                async_cache.pop(url, None)
                continue

            if item.depth > self.project.crawl.max_depth:
                continue

            domain = host_key(url)
            record = registry.records.get(domain)

            if record is None or record.status != "active":
                async_cache.pop(url, None)
                continue

            if (
                pages_by_domain[domain]
                >= self._source_page_limit(domain)
            ):
                async_cache.pop(url, None)
                continue

            if (
                url not in self._coverage.attempted_urls
                and len(self._coverage.attempted_urls)
                >= self.project.crawl.max_pages_total
            ):
                continue
            self._coverage.attempted_urls.add(url)
            self._coverage.attempted_domains.add(domain)

            if (
                self.project.crawl.respect_robots
                and not self.robots.can_fetch(url)
            ):
                result.skipped_by_robots += 1
                visited.add(url)
                registry.mark_robots(domain, "blocked")
                result.page_visits.append(
                    PageVisit(
                        url=url,
                        final_url=url,
                        domain=domain,
                        source_url=item.source_url,
                        source_type=item.source_type,
                        depth=item.depth,
                        priority=item.priority,
                        outcome="robots_blocked",
                    )
                )
                print(f"🤖 robots.txt neļauj: {url}")
                continue

            registry.mark_robots(domain, "allowed")

            print(
                f"📖 [{result.visited_pages + 1}/"
                f"{self.project.crawl.max_pages_total}] {url}"
            )

            prefetched = async_cache.pop(url, None)

            if prefetched is not None and not prefetched.ok:
                visited.add(url)
                result.failed_pages += 1
                error_type = prefetched.error_type or "AsyncFetchError"
                registry.mark_failed(
                    domain,
                    f"http_error:{error_type}",
                )
                result.page_visits.append(
                    PageVisit(
                        url=url,
                        final_url=url,
                        domain=domain,
                        source_url=item.source_url,
                        source_type=item.source_type,
                        depth=item.depth,
                        priority=item.priority,
                        outcome=f"http_error:{error_type}",
                    )
                )
                print(
                    f"⚠️ HTTP kļūda: "
                    f"{prefetched.error_message or error_type}"
                )
                continue

            if prefetched is not None:
                response = _AsyncResponseAdapter(prefetched)
            else:
                try:
                    response = self.session.get(
                        url,
                        timeout=self.settings.request_timeout_seconds,
                        allow_redirects=True,
                    )
                except requests.RequestException as exc:
                    visited.add(url)
                    result.failed_pages += 1
                    registry.mark_failed(
                        domain,
                        f"http_error:{type(exc).__name__}",
                    )
                    result.page_visits.append(
                        PageVisit(
                            url=url,
                            final_url=url,
                            domain=domain,
                            source_url=item.source_url,
                            source_type=item.source_type,
                            depth=item.depth,
                            priority=item.priority,
                            outcome=f"http_error:{type(exc).__name__}",
                        )
                    )
                    print(f"⚠️ HTTP kļūda: {exc}")
                    continue

            final_url = normalize_url(response.url) or url

            if not is_safe_public_url(final_url):
                visited.add(url)
                result.failed_pages += 1
                registry.mark_failed(domain, "unsafe_redirect")
                result.page_visits.append(
                    PageVisit(
                        url=url,
                        final_url=final_url,
                        domain=domain,
                        source_url=item.source_url,
                        source_type=item.source_type,
                        depth=item.depth,
                        priority=item.priority,
                        outcome="unsafe_redirect",
                        http_status=response.status_code,
                        content_type=response.headers.get("Content-Type", ""),
                    )
                )
                print(
                    f"⚠️ Nedrošs redirect URL, izlaižam: {final_url}"
                )
                continue

            final_domain = host_key(final_url)
            active_domains_before = set(registry.run_active_domains)

            if final_domain not in registry.records:
                registry.add_seed(final_url)

            visited.add(url)
            visited.add(final_url)
            pages_by_domain[final_domain] += 1
            result.visited_pages += 1
            registry.mark_page(final_domain)
            self._emit_progress(
                "page_checked",
                domain=final_domain,
                visited_pages=result.visited_pages,
                max_pages=self.project.crawl.max_pages_total,
            )

            if response.status_code != 200:
                result.failed_pages += 1
                registry.mark_failed(
                    final_domain,
                    f"http_status:{response.status_code}",
                )
                result.page_visits.append(
                    PageVisit(
                        url=url,
                        final_url=final_url,
                        domain=final_domain,
                        source_url=item.source_url,
                        source_type=item.source_type,
                        depth=item.depth,
                        priority=item.priority,
                        outcome="http_status",
                        http_status=response.status_code,
                        content_type=response.headers.get("Content-Type", ""),
                    )
                )
                self._sleep()
                continue

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if content_type and "html" not in content_type:
                result.page_visits.append(
                    PageVisit(
                        url=url,
                        final_url=final_url,
                        domain=final_domain,
                        source_url=item.source_url,
                        source_type=item.source_type,
                        depth=item.depth,
                        priority=item.priority,
                        outcome="non_html",
                        http_status=response.status_code,
                        content_type=content_type,
                    )
                )
                self._sleep()
                continue

            self._coverage.usable_domains.add(final_domain)
            result.page_visits.append(
                PageVisit(
                    url=url,
                    final_url=final_url,
                    domain=final_domain,
                    source_url=item.source_url,
                    source_type=item.source_type,
                    depth=item.depth,
                    priority=item.priority,
                    outcome="html_ok",
                    http_status=response.status_code,
                    content_type=content_type,
                )
            )

            continuation_summaries: dict[str, AdaptiveDecision] = {}

            # Sitemap discovery only once per active domain.
            if (
                self.project.crawl.discover_sitemaps
                and final_domain not in sitemap_checked
            ):
                sitemap_checked.add(final_domain)

                sitemap = self.sitemaps.discover(
                    final_url,
                    max_urls=self.project.crawl.max_sitemap_urls_per_domain,
                )
                registry.mark_sitemap(
                    final_domain,
                    sitemap.status,
                    len(sitemap.urls),
                )

                if sitemap.urls:
                    print(
                        f"   🗺️ Sitemap: {len(sitemap.urls)} URL kandidāti"
                    )

                    for sitemap_url in sitemap.urls:
                        normalized = normalize_url(sitemap_url)

                        if not normalized or normalized in visited:
                            continue

                        if not self._allow_target_continuation(
                            continuation_summaries, normalized, source_url=final_url,
                            source_type="sitemap",
                        ):
                            continue

                        score = text_relevance_score(
                            self.project,
                            normalized,
                            "",
                        )

                        frontier.add(
                            normalized,
                            priority=30 + score,
                            depth=min(item.depth + 1, self.project.crawl.max_depth),
                            discovery_depth=item.discovery_depth,
                            source_url=final_url,
                            source_type="sitemap",
                        )


            if (
                self.project.crawl.discover_feeds
                and final_domain not in feed_checked
            ):
                feed_checked.add(final_domain)

                feed_discovery = FeedDiscovery(
                    self.session,
                    user_agent=self.settings.user_agent,
                    timeout=self.settings.request_timeout_seconds,
                )

                scan = feed_discovery.scan(
                    final_url,
                    response.text,
                    previous_states=self.feed_states,
                    max_entries=self.project.crawl.max_feed_entries_per_feed,
                    max_feeds=self.project.crawl.max_feeds_per_domain,
                    probe_common_paths=self.project.crawl.probe_common_feed_paths,
                )

                result.feed_candidates_seen += scan.candidate_count
                result.feed_errors += scan.errors

                for fetched in scan.fetches:
                    state = fetched.state
                    self.feed_states[state.feed_url] = state
                    result.feed_states[state.feed_url] = state

                    if fetched.not_modified:
                        result.feed_not_modified += 1
                        print(f"   📰 Feed nav mainījies: {state.feed_url}")
                        continue

                    if state.status != "active":
                        continue

                    result.feeds_found += 1
                    result.feed_entries_seen += len(fetched.entries)
                    result.feed_entries_new += len(fetched.new_entries)

                    print(
                        f"   📰 {state.feed_type}: "
                        f"{len(fetched.entries)} ieraksti / "
                        f"{len(fetched.new_entries)} jauni"
                    )

                    for entry in fetched.new_entries:
                        normalized = normalize_url(
                            urljoin(state.feed_url, entry.url)
                        )

                        if not normalized or normalized in visited:
                            continue

                        evidence = " ".join(
                            part for part in [entry.title, entry.summary] if part
                        )

                        score = text_relevance_score(
                            self.project,
                            normalized,
                            evidence,
                        )

                        feed_target_domain = host_key(normalized)
                        feed_is_external = feed_target_domain != final_domain
                        feed_discovery_depth = (
                            item.discovery_depth + 1
                            if feed_is_external
                            else item.discovery_depth
                        )
                        feed_block_reason = (
                            self._discovery_activation_block_reason(
                                feed_discovery_depth,
                                discovery_depth_activations,
                            )
                            if feed_is_external
                            else ""
                        )

                        record, feed_event = registry.observe_feed_entry(
                            feed_url=state.feed_url,
                            target_url=normalized,
                            title=entry.title,
                            summary=entry.summary,
                            raw_score=score,
                            activation_block_reason=feed_block_reason,
                        )
                        if feed_block_reason:
                            result.adaptive_decisions.append(
                                AdaptiveDecision(
                                    stage="discovery_depth",
                                    decision="deferred",
                                    target=normalized,
                                    signals={
                                        "reason": feed_block_reason,
                                        "source_domain": final_domain,
                                        "target_domain": feed_target_domain,
                                        "discovery_depth":
                                            feed_discovery_depth,
                                        "max_discovery_depth":
                                            self.project.crawl
                                            .max_discovery_depth,
                                        "depth_budget":
                                            self.project.crawl
                                            .discovery_depth_budgets.get(
                                                feed_discovery_depth
                                            ),
                                        "via": "feed",
                                    },
                                )
                            )

                        if (
                            feed_event.action == "activated"
                            and record.status == "active"
                        ):
                            self._emit_progress(
                                "source_activated",
                                domain=record.domain,
                                origin="feed",
                            )
                            if feed_is_external:
                                discovery_depth_activations[
                                    feed_discovery_depth
                                ] += 1
                            print(
                                f"      🧭 Feed aktivizēja domēnu: "
                                f"{record.domain} "
                                f"(score={record.relevance_score:.2f}, "
                                f"discovery_depth={feed_discovery_depth})"
                            )

                        if record.status != "active":
                            if feed_event.reason == "domain_budget_reached":
                                self._deferred_sources.append((
                                    feed_event, item.depth + 1, feed_discovery_depth,
                                ))
                            continue

                        if (
                            feed_is_external
                            and feed_discovery_depth
                            > self.project.crawl.max_discovery_depth
                        ):
                            continue

                        frontier.add(
                            normalized,
                            priority=55 + score,
                            depth=item.depth + 1,
                            discovery_depth=feed_discovery_depth,
                            source_url=state.feed_url,
                            source_type="feed",
                        )

            try:
                entities = extract_entities(
                    response.text,
                    final_url,
                    self.project,
                )
            except Exception as exc:
                entities = []
                print(f"⚠️ Extraction kļūda: {exc}")

            new_entities = 0
            page_entities: list[MarketEntity] = []

            for entity in entities:
                if entity.stable_key in entity_keys:
                    continue

                entity_keys.add(entity.stable_key)
                page_entities.append(entity)
                new_entities += 1

                price_text = (
                    f"{entity.price:.2f} {entity.currency}"
                    if entity.price is not None
                    else "?"
                )

                print(
                    f"   📦 Atrasts: {entity.title[:62]} | "
                    f"{price_text}"
                )

            if new_entities:
                registry.mark_entities(final_domain, new_entities)

            if self._coverage.specific_target and page_entities:
                # Use the final enrichment/gate here so stop decisions cannot
                # be invalidated by a later identity or relevance rejection.
                self._emit_progress(
                    "analysis_started",
                    entity_count=len(result.entities) + len(page_entities),
                )
                page_entities = self._enrich_batch(page_entities)
            result.entities.extend(page_entities)
            new_confirmed = self._coverage.observe_entities(
                final_domain, page_entities,
            )
            if self._coverage.specific_target:
                result.adaptive_decisions.append(AdaptiveDecision(
                    stage="target_coverage",
                    decision=(
                        "confirmed_progress" if new_confirmed
                        else "no_confirmed_progress"
                    ),
                    target=final_url,
                    signals={
                        "extracted_entities": new_entities,
                        "new_confirmed_targets": new_confirmed,
                        **self._coverage.snapshot(),
                    },
                ))

            if new_entities:
                self._emit_progress(
                    "entities_found",
                    domain=final_domain,
                    count=new_entities,
                    total=len(result.entities),
                )

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup.find_all("a", href=True):
                raw_href = tag.get("href")
                absolute = normalize_url(
                    urljoin(final_url, raw_href)
                )

                if not absolute or absolute in visited:
                    continue

                target_domain = host_key(absolute)
                anchor = " ".join(tag.stripped_strings)
                relevance_context = _link_relevance_context(tag)

                score = text_relevance_score(
                    self.project,
                    absolute,
                    relevance_context,
                )

                is_external = target_domain != final_domain

                if is_external:
                    next_discovery_depth = item.discovery_depth + 1
                    activation_block_reason = (
                        self._discovery_activation_block_reason(
                            next_discovery_depth,
                            discovery_depth_activations,
                        )
                    )
                    record, discovery = registry.observe_link(
                        source_url=final_url,
                        target_url=absolute,
                        anchor_text=anchor,
                        raw_score=score,
                        activation_block_reason=activation_block_reason,
                    )
                    if activation_block_reason:
                        result.adaptive_decisions.append(
                            AdaptiveDecision(
                                stage="discovery_depth",
                                decision="deferred",
                                target=absolute,
                                signals={
                                    "reason": activation_block_reason,
                                    "source_domain": final_domain,
                                    "target_domain": target_domain,
                                    "discovery_depth":
                                        next_discovery_depth,
                                    "max_discovery_depth":
                                        self.project.crawl.max_discovery_depth,
                                    "depth_budget":
                                        self.project.crawl
                                        .discovery_depth_budgets.get(
                                            next_discovery_depth
                                        ),
                                },
                            )
                        )

                    if (
                        discovery.action == "activated"
                        and record.status == "active"
                    ):
                        self._emit_progress(
                            "source_activated",
                            domain=record.domain,
                            origin="link",
                        )
                        discovery_depth_activations[
                            next_discovery_depth
                        ] += 1
                        print(
                            f"   🧭 Jauns domēns aktivizēts: "
                            f"{record.domain} "
                            f"(score={record.relevance_score:.2f}, "
                            f"discovery_depth={next_discovery_depth})"
                        )

                    if record.status != "active":
                        if discovery.reason == "domain_budget_reached":
                            self._deferred_sources.append((
                                discovery, item.depth + 1, next_discovery_depth,
                            ))
                        continue

                    if (
                        next_discovery_depth
                        > self.project.crawl.max_discovery_depth
                    ):
                        continue
                else:
                    if not is_safe_public_url(absolute):
                        continue
                    if not self._allow_target_continuation(
                        continuation_summaries, absolute, source_url=final_url,
                        source_type="html_link",
                        relevance_context=relevance_context,
                    ):
                        continue

                    if (
                        final_domain
                        not in self._coverage.productive_domains
                        and final_domain
                        not in self._promising_probe_domains
                        and self.project.crawl.max_pages_per_domain >= 3
                        and item.depth + 1
                        <= self.project.crawl.max_depth
                        and self._promising_probe_link(
                            absolute,
                            relevance_context,
                            score,
                        )
                    ):
                        self._promising_probe_domains.add(final_domain)
                        result.adaptive_decisions.append(
                            AdaptiveDecision(
                                stage="source_probe",
                                decision="continuation_granted",
                                target=final_domain,
                                signals={
                                    "reason":
                                        "strong_internal_link_evidence",
                                    "source_url": final_url,
                                    "candidate_url": absolute,
                                    "link_score": score,
                                    "threshold": max(
                                        1,
                                        self.project.search
                                        .result_threshold,
                                    ),
                                    "pages_seen":
                                        pages_by_domain[final_domain],
                                    "trial_page_limit": min(
                                        3,
                                        self.project.crawl
                                        .max_pages_per_domain,
                                    ),
                                },
                            )
                        )

                    next_discovery_depth = item.discovery_depth

                priority = 20 + score

                if not is_external:
                    priority += 15

                    # A C1 provisional continuation must spend its scarce
                    # extra page on evidence-backed work rather than on a
                    # structurally attractive but unrelated internal URL.
                    #
                    # text_relevance_score() is capped at 100, so +101 keeps
                    # a subject-evidence link ahead of every same-domain
                    # non-evidence link during the provisional trial.
                    if (
                        final_domain
                        not in self._coverage.productive_domains
                        and self._promising_probe_link(
                            absolute,
                            relevance_context,
                            score,
                        )
                    ):
                        priority += 101

                    penalty = self._source_diversity_penalty(
                        final_domain,
                        registry,
                    )
                    if penalty:
                        priority_before_penalty = priority
                        priority -= penalty
                        result.diversity_penalties_applied += 1
                        result.diversity_domains_penalized.add(final_domain)
                        result.adaptive_decisions.append(
                            AdaptiveDecision(
                                stage="source_diversity",
                                decision="priority_penalty",
                                target=absolute,
                                signals={
                                    "domain": final_domain,
                                    "soft_cap":
                                        self.project.crawl
                                        .entity_diversity_soft_cap,
                                    "entities_found":
                                        registry.records[
                                            final_domain
                                        ].entities_found,
                                    "penalty": penalty,
                                    "priority_before":
                                        priority_before_penalty,
                                    "priority_after": priority,
                                },
                            )
                        )

                frontier.add(
                    absolute,
                    priority=priority,
                    depth=item.depth + 1,
                    discovery_depth=next_discovery_depth,
                    source_url=final_url,
                    source_type="html_link",
                )

            result.adaptive_decisions.extend(
                summary for summary in continuation_summaries.values()
                if summary.signals["discarded"] > 0
            )

            # Give a source with no extracted evidence only a short chance to
            # produce it, then offer its slot to another search candidate.
            # Replenish before adaptive stopping so a replacement is not
            # discarded by an entity-free page streak.
            if (
                self.project.crawl.mode == "expedition"
                and not self._coverage.specific_target
                and len(self._coverage.attempted_urls)
                < self.project.crawl.max_pages_total
            ):
                self._replenish_sources(
                    frontier, registry, result, visited, pages_by_domain,
                    discovery_depth_activations,
                )

            new_active_domains = len(
                set(registry.run_active_domains) - active_domains_before
            )
            trial_pending = any(
                domain in self._coverage.usable_domains
                and domain not in self._coverage.productive_domains
                and registry.records[domain].status == "active"
                for domain in (
                    registry.run_active_domains
                    - self._coverage.exhausted_domains
                )
            )
            untried_source_pending = any(
                domain not in self._coverage.attempted_domains
                and registry.records[domain].status == "active"
                for domain in (
                    registry.run_active_domains
                    - self._coverage.exhausted_domains
                )
            )
            if (
                self.project.crawl.mode == "expedition"
                and not self._coverage.specific_target
                and (
                    new_active_domains > 0
                    or trial_pending
                    or untried_source_pending
                )
            ):
                result.diminishing_returns_streak = 0
                result.saturation_streak = 0
            elif self._update_adaptive_stop(
                result,
                new_entities=(
                    new_confirmed
                    if self._coverage.specific_target else new_entities
                ),
                new_active_domains=new_active_domains,
            ):
                print(
                    f"⏹️ STOP_REASON={result.stop_reason} "
                    f"diminishing_streak={result.diminishing_returns_streak} "
                    f"saturation_streak={result.saturation_streak}"
                )
                break

            self._sleep()

        if not result.stop_reason:
            if result.visited_pages >= self.project.crawl.max_pages_total:
                result.stop_reason = "max_pages"
            elif (
                len(self._coverage.attempted_urls)
                >= self.project.crawl.max_pages_total
            ):
                result.stop_reason = "max_page_attempts"
            elif self._coverage.specific_target:
                result.stop_reason = "discovery_exhausted"
            elif (
                len(self._coverage.occupied_domains(
                    registry.run_active_domains,
                )) >= self.project.crawl.max_domains
                and any(
                    item.reason == "domain_budget_reached"
                    for item in registry.discoveries
                )
            ):
                result.stop_reason = "max_domains"
            else:
                result.stop_reason = "budget_exhausted"

        self._assess_target_coverage(result)
        result.adaptive_decisions.append(
            AdaptiveDecision(
                stage="stop",
                decision=result.stop_reason,
                target=self.project.id,
                signals={
                    "visited_pages": result.visited_pages,
                    "max_pages_total":
                        self.project.crawl.max_pages_total,
                    "diminishing_returns_streak":
                        result.diminishing_returns_streak,
                    "diminishing_returns_window":
                        self.project.crawl.diminishing_returns_window,
                    "saturation_streak":
                        result.saturation_streak,
                    "saturation_window":
                        self.project.crawl.saturation_window,
                    "active_domains": registry.active_count,
                    "occupied_source_slots": len(
                        self._coverage.occupied_domains(
                            registry.run_active_domains,
                        )
                    ),
                    "max_domains": self.project.crawl.max_domains,
                    **self._coverage.snapshot(),
                },
            )
        )

        if not self._coverage.specific_target:
            self._emit_progress(
                "analysis_started",
                entity_count=len(result.entities),
            )
            self._enrich_entities(result)

        if async_politeness is not None:
            politeness_snapshot = async_politeness.snapshot()
            result.async_pressure_events = sum(
                state.pressure_events
                for state in politeness_snapshot.values()
            )
            result.async_final_domain_delay_seconds = {
                domain: state.current_delay_seconds
                for domain, state in politeness_snapshot.items()
            }

        result.domains = registry.current_run_records()
        result.domain_discoveries = registry.discoveries
        result.finished_at = datetime.now(timezone.utc).isoformat()
        self._emit_progress(
            "crawl_finished",
            visited_pages=result.visited_pages,
            entity_count=len(result.entities),
            domain_count=len(result.domains),
            stop_reason=result.stop_reason,
        )
        return result

    def _ensure_async_transport(self):
        if self.async_transport is None:
            self.async_transport = AsyncHTTPTransport(
                user_agent=self.settings.user_agent,
                timeout_seconds=self.settings.request_timeout_seconds,
                accept_language=",".join(self.project.languages)
                + ",en;q=0.7",
            )
        return self.async_transport

    def _prefetch_async_wave(
        self,
        *,
        frontier: URLFrontier,
        planner: AsyncWavePlanner,
        cache: dict[str, AsyncHTTPResult],
        visited: set[str],
        pages_by_domain: Counter[str],
        registry: DomainRegistry,
        result: ResearchRunResult,
        fetcher,
    ) -> None:
        remaining_total = (
            self.project.crawl.max_pages_total
            - len(self._coverage.attempted_urls)
        )
        if remaining_total <= 0:
            return

        def classify(item):
            if item.url in cache:
                return "defer"
            if item.url in visited:
                return "drop"
            if item.depth > self.project.crawl.max_depth:
                return "drop"

            domain = host_key(item.url)
            record = registry.records.get(domain)
            if record is None or record.status != "active":
                return "drop"

            if (
                pages_by_domain[domain]
                >= self.project.crawl.max_pages_per_domain
            ):
                return "drop"

            return "eligible"

        wave = planner.plan(
            frontier,
            remaining_total=remaining_total,
            pages_by_domain=pages_by_domain,
            classify=classify,
            max_pages_for_domain=self._source_page_limit,
        )
        if not wave.items:
            return

        fetch_items = []
        for item in wave.items:
            url = item.url
            domain = host_key(url)
            self._coverage.attempted_urls.add(url)
            self._coverage.attempted_domains.add(domain)

            if (
                self.project.crawl.respect_robots
                and not self.robots.can_fetch(url)
            ):
                result.skipped_by_robots += 1
                visited.add(url)
                registry.mark_robots(domain, "blocked")
                result.page_visits.append(
                    PageVisit(
                        url=url,
                        final_url=url,
                        domain=domain,
                        source_url=item.source_url,
                        source_type=item.source_type,
                        depth=item.depth,
                        priority=item.priority,
                        outcome="robots_blocked",
                    )
                )
                print(f"🤖 robots.txt neļauj: {url}")
                continue

            registry.mark_robots(domain, "allowed")
            fetch_items.append(item)

        if not fetch_items:
            return

        coordinator = AsyncCrawlCoordinator(
            AsyncCrawlPolicy(
                global_concurrency=
                    self.project.crawl.async_global_concurrency,
                per_domain_concurrency=
                    self.project.crawl.async_per_domain_concurrency,
                min_domain_delay_seconds=0.0,
                max_pending=self.project.crawl.async_max_pending,
            )
        )
        if fetcher is None:
            raise RuntimeError(
                "Async fetcher nav inicializēts async crawl režīmam."
            )

        async def fetch_all():
            return await coordinator.run(
                [item.url for item in fetch_items],
                fetcher.fetch,
            )

        task_results, stats = asyncio.run(fetch_all())

        result.async_fetch_waves += 1
        result.async_fetch_submitted += stats.submitted
        result.async_peak_active = max(
            result.async_peak_active,
            stats.peak_active,
        )
        result.async_peak_pending = max(
            result.async_peak_pending,
            stats.peak_pending,
        )
        for domain, peak in stats.peak_domain_active.items():
            result.async_peak_domain_active[domain] = max(
                result.async_peak_domain_active.get(domain, 0),
                peak,
            )

        by_url = {
            item.url: item
            for item in fetch_items
        }

        for task_result in task_results:
            outcome = task_result.value
            if outcome is None:
                fetch_result = AsyncHTTPResult(
                    requested_url=task_result.url,
                    final_url=task_result.url,
                    status_code=None,
                    error_type=(
                        task_result.error_type
                        or "AsyncWorkerError"
                    ),
                    error_message=task_result.error_message,
                )
                result.async_http_attempts += 1
            else:
                fetch_result = outcome.result
                result.async_http_attempts += outcome.attempts
                result.async_retries += outcome.retries
                result.async_politeness_wait_seconds += (
                    outcome.waited_seconds
                )
                if outcome.retry_exhausted:
                    result.async_retry_exhausted += 1

            if not fetch_result.ok:
                result.async_fetch_failures += 1

            cache[task_result.url] = fetch_result
            frontier.restore(by_url[task_result.url])

    def _source_diversity_penalty(
        self,
        domain: str,
        registry: DomainRegistry,
    ) -> int:
        cap = self.project.crawl.entity_diversity_soft_cap
        if cap <= 0:
            return 0

        record = registry.records.get(domain)
        if record is None or record.entities_found < cap:
            return 0

        return self.project.crawl.entity_diversity_priority_penalty

    def _discovery_activation_block_reason(
        self,
        discovery_depth: int,
        activations: Counter[int],
    ) -> str:
        if discovery_depth > self.project.crawl.max_discovery_depth:
            return "discovery_depth_limit"

        budget = self.project.crawl.discovery_depth_budgets.get(
            discovery_depth
        )
        if budget is not None and activations[discovery_depth] >= budget:
            return "discovery_depth_budget_reached"

        return ""

    def _update_adaptive_stop(
        self,
        result: ResearchRunResult,
        *,
        new_entities: int,
        new_active_domains: int,
    ) -> bool:
        if new_entities > 0:
            result.diminishing_returns_streak = 0
            result.saturation_streak = 0
        else:
            result.diminishing_returns_streak += 1
            if new_active_domains > 0:
                result.saturation_streak = 0
            else:
                result.saturation_streak += 1

        if self._coverage.needs_evidence:
            return False

        saturation_window = self.project.crawl.saturation_window
        if (
            saturation_window > 0
            and result.saturation_streak >= saturation_window
        ):
            result.stop_reason = "saturation_reached"
            return True

        diminishing_window = self.project.crawl.diminishing_returns_window
        if (
            diminishing_window > 0
            and result.diminishing_returns_streak >= diminishing_window
        ):
            result.stop_reason = "diminishing_returns"
            return True

        return False

    def _source_memory_state(self, domain: str) -> str:
        profile = self.source_profiles.get(domain)
        if profile is None:
            return "untested"

        status = str(profile.get("status", ""))
        if status in {"blocked", "rejected"}:
            return status

        crawl_runs = int(profile.get("crawl_runs", 0) or 0)
        productive_runs = int(profile.get("productive_runs", 0) or 0)
        is_stale = bool(profile.get("is_stale", False))

        if productive_runs > 0:
            return "productive_stale" if is_stale else "productive_fresh"
        if crawl_runs > 0:
            return "nonproductive"
        return "untested"

    def _rank_search_hits_by_source_memory(self, hits):
        ranked = []

        band_order = {
            "productive_fresh": 0,
            "untested": 1,
            "productive_stale": 2,
            "nonproductive": 3,
            "blocked": 4,
            "rejected": 4,
        }

        for index, hit in enumerate(hits):
            normalized = normalize_url(hit.url)
            domain = host_key(normalized) if normalized else ""
            profile = self.source_profiles.get(domain)
            state = self._source_memory_state(domain)

            if profile is None:
                productive_rate = 0.0
                entity_yield = 0.0
                success_rate = 0.0
            else:
                productive_rate = float(
                    profile.get("productive_run_rate", 0.0) or 0.0
                )
                entity_yield = float(
                    profile.get("entity_yield", 0.0) or 0.0
                )
                success_rate = float(
                    profile.get("success_rate", 0.0) or 0.0
                )

            band = band_order[state]
            has_productive_history = state in {
                "productive_fresh",
                "productive_stale",
            }
            ranked.append(
                (
                    (
                        band,
                        -productive_rate if has_productive_history else 0.0,
                        -entity_yield if has_productive_history else 0.0,
                        -success_rate if has_productive_history else 0.0,
                        index,
                    ),
                    hit,
                )
            )

        return [hit for _, hit in sorted(ranked, key=lambda item: item[0])]

    def _rank_search_hits(
        self,
        hits,
        query_text: str,
    ) -> list[LocalRelevance]:
        local_signals = local_relevance_signals(
            self.project,
            query_text,
            list(hits),
        )

        band_order = {
            "productive_fresh": 0,
            "untested": 1,
            "productive_stale": 2,
            "nonproductive": 3,
            "blocked": 4,
            "rejected": 4,
        }

        ranked = []
        for signal in local_signals:
            normalized = normalize_url(signal.hit.url)
            domain = host_key(normalized) if normalized else ""
            profile = self.source_profiles.get(domain)
            state = self._source_memory_state(domain)

            if profile is None:
                productive_rate = 0.0
                entity_yield = 0.0
                success_rate = 0.0
            else:
                productive_rate = float(
                    profile.get("productive_run_rate", 0.0) or 0.0
                )
                entity_yield = float(
                    profile.get("entity_yield", 0.0) or 0.0
                )
                success_rate = float(
                    profile.get("success_rate", 0.0) or 0.0
                )

            has_productive_history = state in {
                "productive_fresh",
                "productive_stale",
            }
            ranked.append(
                (
                    (
                        -signal.target_identity_anchor_matches,
                        -signal.target_identity_matches,
                        band_order[state],
                        -productive_rate if has_productive_history else 0.0,
                        -entity_yield if has_productive_history else 0.0,
                        -success_rate if has_productive_history else 0.0,
                        1 if signal.negative_matches else 0,
                        -signal.bm25,
                        -signal.title_matches,
                        -signal.path_matches,
                        -signal.domain_matches,
                        signal.provider_index,
                    ),
                    signal,
                )
            )

        return [
            signal
            for _, signal in sorted(
                ranked,
                key=lambda item: item[0],
            )
        ]

    def _seed_from_search(
        self,
        frontier: URLFrontier,
        registry: DomainRegistry,
        result: ResearchRunResult,
        *,
        recovery: bool = False,
        pages_by_domain: Counter[str] | None = None,
    ):
        if self.search_provider is None:
            raise ValueError(
                "Expedition režīmam vajadzīgs SearchProvider. "
                "Norādi project.search.provider vai izmanto provider injekciju testos."
            )

        queries = build_search_queries(
            self.project,
            query_memory=self.query_memory,
            provider=self.search_provider.name,
            recovery=recovery,
            exclude_queries=self._issued_queries,
        )
        if recovery:
            remaining = (
                self.project.search.max_recovery_queries
                - self._recovery_queries_issued
            )
            queries = queries[:max(0, remaining)]
        if not queries:
            if recovery:
                return
            raise ValueError(
                "Expedition režīmam nav neviena search query. "
                "Pievieno keywords vai search.queries."
            )

        query_offset = result.search_queries_issued
        for position, query in enumerate(queries, start=query_offset + 1):
            result.adaptive_decisions.append(
                AdaptiveDecision(
                    stage="query_priority",
                    decision="scheduled",
                    target=query.query,
                    signals={
                        "position": position,
                        "reason": query.reason,
                        "memory_state": query.memory_state,
                        "productive_domain_rate":
                            query.memory_productive_domain_rate,
                        "productive_domains":
                            query.memory_productive_domains,
                        "unique_domains": query.memory_unique_domains,
                        "runs": query.memory_runs,
                    },
                )
            )

        language = (
            self.project.languages[0]
            if self.project.languages
            else "all"
        )

        print("")
        print(
            f"🔎 Expedition: {self.search_provider.name} · "
            f"{len(queries)} vaicājumi"
        )

        seen_search_urls = {
            str(item["normalized"]) for item in self._search_candidate_pool
        }

        # Search results are collected across every query first.
        #
        # Previously each query activated domains immediately. With a small
        # max_domains budget an early broad query could consume every slot
        # before a later hard-constraint query was even evaluated.
        #
        # pending_by_url keeps the best observation for each normalized URL;
        # domain activation happens only after the complete search candidate
        # pool is globally ranked.
        pending_by_url = {
            str(item["normalized"]): item for item in self._search_candidate_pool
        }

        def candidate_rank(candidate: dict[str, object]):
            query = candidate["query"]
            signal = candidate["ranked_hit"]

            return (
                signal.target_identity_anchor_matches,
                signal.target_identity_matches,
                int(candidate["score"]),
                1
                if getattr(
                    query,
                    "reason",
                    "",
                ) == "required_evidence_bundle"
                else 0,
                -int(candidate["query_position"]),
                -int(candidate["result_position"]),
            )

        for query_position, query in enumerate(
            queries,
            start=query_offset + 1,
        ):
            result.search_queries_issued += 1
            self._issued_queries.add(query.query)
            if recovery:
                self._recovery_queries_issued += 1
            self._emit_progress(
                "search_query_started",
                position=query_position,
                total=query_offset + len(queries),
            )

            memory_note = ""

            if query.memory_state != "untested":
                rate = (
                    query.memory_productive_domain_rate
                    or 0.0
                )
                memory_note = (
                    f" · memory={query.memory_state}"
                    f" yield={rate:.1%}"
                    f" productive="
                    f"{query.memory_productive_domains}"
                    f"/{query.memory_unique_domains}"
                    f" runs={query.memory_runs}"
                )

            print(
                f"   🔍 {query.query}{memory_note}"
            )

            try:
                hits = self.search_provider.search(
                    query.query,
                    language=language,
                    limit=self.project.search.results_per_query,
                    safesearch=self.project.search.safesearch,
                )

                ranked_hits = self._rank_search_hits(
                    hits,
                    query.query,
                )

                for result_position, ranked_hit in enumerate(
                    ranked_hits,
                    start=1,
                ):
                    ranked_url = normalize_url(
                        ranked_hit.hit.url
                    )
                    ranked_domain = (
                        host_key(ranked_url)
                        if ranked_url
                        else ""
                    )

                    profile = self.source_profiles.get(
                        ranked_domain
                    )

                    result.adaptive_decisions.append(
                        AdaptiveDecision(
                            stage="search_result_priority",
                            decision="scheduled",
                            target=ranked_hit.hit.url,
                            signals={
                                "position":
                                    result_position,
                                "query":
                                    query.query,
                                "source_memory_state":
                                    self._source_memory_state(
                                        ranked_domain
                                    ),
                                "productive_run_rate":
                                    float(
                                        profile.get(
                                            "productive_run_rate",
                                            0.0,
                                        )
                                        or 0.0
                                    )
                                    if profile
                                    else 0.0,
                                "entity_yield":
                                    float(
                                        profile.get(
                                            "entity_yield",
                                            0.0,
                                        )
                                        or 0.0
                                    )
                                    if profile
                                    else 0.0,
                                "bm25":
                                    ranked_hit.bm25,
                                "title_matches":
                                    ranked_hit.title_matches,
                                "path_matches":
                                    ranked_hit.path_matches,
                                "domain_matches":
                                    ranked_hit.domain_matches,
                                "target_identity_matches":
                                    ranked_hit.target_identity_matches,
                                "target_identity_anchor_matches":
                                    ranked_hit
                                    .target_identity_anchor_matches,
                                "negative_matches":
                                    ranked_hit.negative_matches,
                                "provider_index":
                                    ranked_hit.provider_index,
                            },
                        )
                    )

            except SearchProviderError as exc:
                result.search_provider_errors += 1

                detail = (
                    f"kind={exc.kind}, "
                    f"attempts={exc.attempts}"
                )

                if exc.status_code is not None:
                    detail += (
                        f", http={exc.status_code}"
                    )

                print(
                    f"   ⚠️ SearchProvider kļūda: "
                    f"{exc} [{detail}]"
                )
                continue

            for result_position, ranked_hit in enumerate(
                ranked_hits,
                start=1,
            ):
                hit = ranked_hit.hit

                result.search_results_seen += 1

                normalized = normalize_url(hit.url)

                if not normalized:
                    continue

                evidence = " ".join(
                    part
                    for part in [
                        hit.title,
                        hit.snippet,
                    ]
                    if part
                )

                score = text_relevance_score(
                    self.project,
                    normalized,
                    evidence,
                )

                candidate = {
                    "normalized": normalized,
                    "query": query,
                    "query_position":
                        query_position,
                    "result_position":
                        result_position,
                    "ranked_hit":
                        ranked_hit,
                    "hit":
                        hit,
                    "score":
                        score,
                }

                if normalized in seen_search_urls:
                    result.search_results_duplicates += 1

                    previous = pending_by_url[
                        normalized
                    ]

                    if (
                        candidate_rank(candidate)
                        > candidate_rank(previous)
                    ):
                        pending_by_url[
                            normalized
                        ] = candidate

                    continue

                seen_search_urls.add(normalized)
                result.search_results_unique += 1

                pending_by_url[
                    normalized
                ] = candidate

        ordered_candidates = sorted(
            pending_by_url.values(),
            key=candidate_rank,
            reverse=True,
        )
        self._search_candidate_pool = ordered_candidates

        result.adaptive_decisions.append(
            AdaptiveDecision(
                stage="search_domain_budget",
                decision="globally_ranked",
                target=self.project.id,
                signals={
                    "candidate_urls":
                        len(ordered_candidates),
                    "max_domains":
                        self.project.crawl.max_domains,
                    "strategy":
                        "all_queries_before_activation",
                },
            )
        )

        for candidate in ordered_candidates:
            normalized = str(
                candidate["normalized"]
            )
            query = candidate["query"]
            ranked_hit = candidate["ranked_hit"]
            hit = candidate["hit"]
            score = int(candidate["score"])
            domain = host_key(normalized)
            if recovery and (
                normalized in self._coverage.attempted_urls
                or (
                    pages_by_domain is not None
                    and pages_by_domain[domain]
                    >= self.project.crawl.max_pages_per_domain
                )
            ):
                continue
            if (
                domain in registry.run_active_domains
                and registry.records[domain].status == "failed"
            ):
                continue

            record, discovery = (
                registry.observe_search_result(
                    provider=
                        self.search_provider.name,
                    query_text=query.query,
                    target_url=normalized,
                    title=hit.title,
                    snippet=hit.snippet,
                    raw_score=score,
                    activation_budget_available=self._source_slot_available(
                        registry, domain,
                    ),
                )
            )

            if discovery.action == "activated":
                result.search_domains_activated += 1
                self._emit_progress(
                    "source_activated",
                    domain=record.domain,
                    origin="search",
                )

                profile = self.source_profiles.get(
                    record.domain
                )
                state = self._source_memory_state(
                    record.domain
                )
                source_note = ""

                if profile is not None:
                    source_note = (
                        f" source_memory={state}"
                        f" productive_run_rate="
                        f"{float(profile.get('productive_run_rate', 0.0) or 0.0):.1%}"
                        f" entity_yield="
                        f"{float(profile.get('entity_yield', 0.0) or 0.0):.2f}"
                    )

                print(
                    f"      🧭 Search domēns aktivizēts: "
                    f"{record.domain} "
                    f"(score={record.relevance_score:.2f})"
                    f"{source_note}"
                    f" local="
                    f"{ranked_hit.audit_label}"
                )

            if (
                record.status == "active"
                and discovery.action in {"activated", "known"}
                and normalized not in self._coverage.attempted_urls
            ):
                self._coverage.exhausted_domains.discard(domain)
                frontier.add(
                    normalized,
                    priority=80 + score,
                    depth=0,
                    discovery_depth=0,
                    source_url="",
                    source_type="search_provider",
                )

        # A search engine can return useful candidates while the older
        # exact-keyword score keeps every result below result_threshold.
        # Do not fail the entire expedition in that case: if normal search
        # activation left the frontier empty, bootstrap from the best
        # independently ranked safe candidates.
        if not frontier and ordered_candidates:
            for candidate in ordered_candidates:
                normalized = str(candidate["normalized"])
                query = candidate["query"]
                ranked_hit = candidate["ranked_hit"]
                hit = candidate["hit"]
                score = int(candidate["score"])
                domain = host_key(normalized)

                if recovery and (
                    normalized in self._coverage.attempted_urls
                    or (
                        pages_by_domain is not None
                        and pages_by_domain[domain]
                        >= self.project.crawl.max_pages_per_domain
                    )
                ):
                    continue

                if not self._ranked_bootstrap_candidate_eligible(
                    ranked_hit,
                    score,
                ):
                    continue

                record, discovery = registry.observe_search_result(
                    provider=self.search_provider.name,
                    query_text=query.query,
                    target_url=normalized,
                    title=hit.title,
                    snippet=hit.snippet,
                    raw_score=score,
                    activation_budget_available=self._source_slot_available(
                        registry,
                        domain,
                    ),
                    activation_reason="search_ranked_bootstrap_fallback",
                )

                # Persisted blocked/rejected state and source budgets still
                # win over the fallback.
                if discovery.action != "activated":
                    continue

                result.search_domains_activated += 1

                self._emit_progress(
                    "source_activated",
                    domain=record.domain,
                    origin="search_ranked_bootstrap",
                )

                result.adaptive_decisions.append(
                    AdaptiveDecision(
                        stage="search_bootstrap_fallback",
                        decision="activated",
                        target=normalized,
                        signals={
                            "domain": record.domain,
                            "query": query.query,
                            "legacy_score": score,
                            "threshold":
                                self.project.search.result_threshold,
                            "bm25": ranked_hit.bm25,
                            "title_matches":
                                ranked_hit.title_matches,
                            "path_matches":
                                ranked_hit.path_matches,
                            "domain_matches":
                                ranked_hit.domain_matches,
                            "target_identity_matches":
                                ranked_hit.target_identity_matches,
                            "target_identity_anchor_matches":
                                ranked_hit.target_identity_anchor_matches,
                            "provider_score":
                                ranked_hit.hit.provider_score,
                        },
                    )
                )

                print(
                    f"      🧭 Search bootstrap fallback: "
                    f"{record.domain} "
                    f"(legacy_score={score}, "
                    f"threshold={self.project.search.result_threshold}) "
                    f"local={ranked_hit.audit_label}"
                )

                frontier.add(
                    normalized,
                    priority=70 + max(score, 0),
                    depth=0,
                    discovery_depth=0,
                    source_url="",
                    source_type="search_ranked_bootstrap",
                )

                if (
                    registry.active_count
                    >= self.project.crawl.max_domains
                ):
                    break

    def _ranked_bootstrap_candidate_eligible(
        self,
        ranked_hit: LocalRelevance,
        score: int,
    ) -> bool:
        if ranked_hit.negative_matches > 0:
            return False

        # A specific model/target keeps the W6.9 identity boundary:
        # provider rank alone must never bootstrap the wrong model.
        if self._coverage.specific_target:
            return (
                ranked_hit.target_identity_anchor_matches > 0
            )

        provider_score = ranked_hit.hit.provider_score

        return (
            score > 0
            or ranked_hit.bm25 > 0.0
            or ranked_hit.title_matches > 0
            or ranked_hit.path_matches > 0
            or ranked_hit.domain_matches > 0
            or ranked_hit.target_identity_matches > 0
            or ranked_hit.target_identity_anchor_matches > 0
            or (
                provider_score is not None
                and provider_score > 0
            )
        )

    def _allow_target_continuation(
        self,
        summaries: dict[str, AdaptiveDecision],
        url: str,
        *,
        source_url: str,
        source_type: str,
        relevance_context: str = "",
    ) -> bool:
        """Count only candidates reaching this filter, grouped by page/type."""
        if not self._coverage.specific_target:
            return True

        anchors = set(re.findall(
            r"[^\W_]+",
            " ".join(self.project.analysis.target_identity_anchor_terms).casefold(),
        ))
        # Match destination path/link-local evidence, not the source page,
        # hostname or return-URL query parameters inherited by navigation.
        evidence = f"{unquote(urlparse(url).path)} {relevance_context}"
        tokens = set(re.findall(r"[^\W_]+", evidence.casefold()))

        summary = summaries.get(source_type)
        if summary is None:
            summary = AdaptiveDecision(
                stage="target_continuation",
                decision="filtered_summary",
                target=source_url,
                signals={
                    "source_url": source_url,
                    "source_type": source_type,
                    "examined": 0,
                    "allowed": 0,
                    "discarded": 0,
                    "required_anchor_tokens": sorted(anchors),
                    "reason_counts": {},
                    "sample_discarded_urls": [],
                },
            )
            summaries[source_type] = summary
        signals = summary.signals
        signals["examined"] += 1
        if anchors and anchors <= tokens:
            signals["allowed"] += 1
            return True

        signals["discarded"] += 1
        reasons = signals["reason_counts"]
        reasons["target_anchor_missing"] = reasons.get("target_anchor_missing", 0) + 1
        samples = signals["sample_discarded_urls"]
        if len(samples) < 5:
            samples.append(url)
        return False

    def _source_slot_available(
        self, registry: DomainRegistry, domain: str = "",
    ) -> bool:
        occupied = self._coverage.occupied_domains(registry.run_active_domains)
        return domain in occupied or len(occupied) < self.project.crawl.max_domains

    def _promising_probe_link(
        self,
        url: str,
        relevance_context: str,
        score: int,
    ) -> bool:
        """Return True when actual page evidence merits one extra probe."""
        if (
            self.project.crawl.mode != "expedition"
            or self._coverage.specific_target
            or score <= 0
        ):
            return False

        threshold = max(
            1,
            self.project.search.result_threshold,
        )

        if score < threshold:
            return False

        haystack = f"{url} {relevance_context}".casefold()

        has_subject_evidence = False

        for term in (
            *self.project.keywords,
            *self.project.analysis.required_evidence_terms,
        ):
            key = term.strip().casefold()

            if key and key in haystack:
                has_subject_evidence = True
                break

        if not has_subject_evidence:
            return False

        for keyword in self.project.negative_keywords:
            key = keyword.strip().casefold()

            if key and key in haystack:
                return False

        return True

    def _source_page_limit(self, domain: str) -> int:
        limit = self.project.crawl.max_pages_per_domain

        if (
            self.project.crawl.mode == "expedition"
            and not self._coverage.specific_target
            and domain not in self._coverage.productive_domains
        ):
            if domain in self._promising_probe_domains:
                return min(3, limit)

            return min(2, limit)

        return limit

    def _replenish_sources(
        self,
        frontier: URLFrontier,
        registry: DomainRegistry,
        result: ResearchRunResult,
        visited: set[str],
        pages_by_domain: Counter[str],
        discovery_depth_activations: Counter[int],
    ) -> bool:
        # HTML/sitemap continuations are filtered before enqueueing, so
        # navigation noise cannot keep these domains pending and delay recovery.
        pending_domains = {
            host_key(item.url) for item in frontier.pending_items()
            if item.url not in visited
            and item.depth <= self.project.crawl.max_depth
            and pages_by_domain[host_key(item.url)]
            < self.project.crawl.max_pages_per_domain
            and host_key(item.url) in registry.records
            and registry.records[host_key(item.url)].status == "active"
            and (
                pages_by_domain[host_key(item.url)]
                < self._source_page_limit(host_key(item.url))
            )
        }
        self._coverage.exhausted_domains = (
            registry.run_active_domains - pending_domains
        )
        if (
            self.project.crawl.mode == "expedition"
            and not self._coverage.specific_target
        ):
            for domain in sorted(self._coverage.exhausted_domains):
                record = registry.records.get(domain)
                if (
                    record is None
                    or record.status != "active"
                    or domain not in self._coverage.usable_domains
                    or domain in self._coverage.productive_domains
                ):
                    continue
                registry.mark_nonproductive(domain)
                self._coverage.released_domains.add(domain)
                result.adaptive_decisions.append(AdaptiveDecision(
                    stage="source_slot",
                    decision="released",
                    target=domain,
                    signals={
                        "reason": "nonproductive_source",
                        "pages_seen": pages_by_domain[domain],
                        "trial_page_limit": self._source_page_limit(domain),
                    },
                ))
        if len(self._coverage.attempted_urls) >= self.project.crawl.max_pages_total:
            return bool(pending_domains)

        added = self._backfill_search_domain_slots(
            frontier, registry, result, reason="source_exhausted",
        )
        added += self._backfill_discovered_sources(
            frontier, registry, result, discovery_depth_activations,
        )
        if pending_domains or added:
            return True

        if (
            self.project.crawl.mode == "expedition"
            and self._coverage.needs_evidence
            and self._recovery_queries_issued < self.project.search.max_recovery_queries
        ):
            result.adaptive_decisions.append(AdaptiveDecision(
                stage="discovery_recovery",
                decision="reformulate_queries",
                target=self.project.id,
                signals=self._coverage.snapshot(),
            ))
            self._seed_from_search(
                frontier, registry, result, recovery=True,
                pages_by_domain=pages_by_domain,
            )
            return any(
                item.url not in visited
                and item.depth <= self.project.crawl.max_depth
                and pages_by_domain[host_key(item.url)]
                < self.project.crawl.max_pages_per_domain
                and registry.records[host_key(item.url)].status == "active"
                for item in frontier.pending_items()
            )
        return False

    def _backfill_discovered_sources(
        self,
        frontier: URLFrontier,
        registry: DomainRegistry,
        result: ResearchRunResult,
        depth_activations: Counter[int],
    ) -> int:
        added = 0
        activated: set[str] = set()
        for event, depth, discovery_depth in sorted(
            self._deferred_sources, key=lambda item: -item[0].relevance_score,
        ):
            if depth > self.project.crawl.max_depth:
                continue
            domain = event.target_domain
            if domain not in activated:
                if domain in registry.run_active_domains:
                    continue
                if not self._source_slot_available(registry):
                    continue
                block = self._discovery_activation_block_reason(
                    discovery_depth, depth_activations,
                )
                common = dict(
                    target_url=event.target_url,
                    raw_score=round(event.relevance_score * 100),
                    activation_block_reason=block,
                    activation_budget_available=True,
                )
                if event.discovered_via == "feed":
                    record, discovery = registry.observe_feed_entry(
                        feed_url=event.source_url,
                        title=event.anchor_text, summary="", **common,
                    )
                else:
                    record, discovery = registry.observe_link(
                        source_url=event.source_url,
                        anchor_text=event.anchor_text, **common,
                    )
                if discovery.action not in {"activated", "known"}:
                    continue
                activated.add(domain)
                depth_activations[discovery_depth] += 1
                self._emit_progress(
                    "source_activated", domain=domain,
                    origin="discovery_backfill",
                )
                result.adaptive_decisions.append(AdaptiveDecision(
                    stage="discovery_backfill", decision="activated",
                    target=event.target_url,
                    signals={"via": event.discovered_via, **self._coverage.snapshot()},
                ))
            if event.target_url not in self._coverage.attempted_urls:
                added += frontier.add(
                    event.target_url, priority=55 + round(event.relevance_score * 100),
                    depth=depth, discovery_depth=discovery_depth,
                    source_url=event.source_url, source_type=event.discovered_via,
                )
        return added

    def _backfill_search_domain_slots(
        self,
        frontier: URLFrontier,
        registry: DomainRegistry,
        result: ResearchRunResult,
        *,
        reason: str,
    ) -> int:
        if (
            self.project.crawl.mode != "expedition"
            or not self._search_candidate_pool
            or self.search_provider is None
        ):
            return 0

        activated = 0
        backfilled_domains: set[str] = set()
        if not self._source_slot_available(registry):
            return 0

        for candidate in self._search_candidate_pool:
            normalized = str(candidate["normalized"])
            domain = host_key(normalized)
            if (
                domain in registry.run_active_domains
                and domain not in backfilled_domains
            ):
                continue
            if normalized in self._coverage.attempted_urls:
                continue
            if (
                domain not in backfilled_domains
                and not self._source_slot_available(registry)
            ):
                continue

            query = candidate["query"]
            ranked_hit = candidate["ranked_hit"]
            hit = candidate["hit"]
            score = int(candidate["score"])

            trial_reason = ""
            if score < self.project.search.result_threshold:
                if (
                    not self._coverage.released_domains
                    or not self._ranked_bootstrap_candidate_eligible(
                        ranked_hit, score,
                    )
                ):
                    continue
                trial_reason = "search_candidate_trial"

            record, discovery = registry.observe_search_result(
                provider=self.search_provider.name,
                query_text=query.query,
                target_url=normalized,
                title=hit.title,
                snippet=hit.snippet,
                raw_score=score,
                activation_budget_available=self._source_slot_available(
                    registry, domain,
                ),
                activation_reason=trial_reason,
            )

            if discovery.action not in {"activated", "known"}:
                continue
            if domain in backfilled_domains:
                frontier.add(
                    normalized, priority=75 + score, depth=0,
                    source_type="search_backfill",
                )
                continue
            activated += 1
            backfilled_domains.add(domain)
            if discovery.action == "activated":
                result.search_domains_activated += 1
            self._emit_progress(
                "source_activated",
                domain=record.domain,
                origin="search_backfill",
            )
            result.adaptive_decisions.append(
                AdaptiveDecision(
                    stage="search_domain_backfill",
                    decision="activated",
                    target=normalized,
                    signals={
                        "domain": record.domain,
                        "reason": reason,
                        "score": score,
                        "activated_domains": registry.active_count,
                        "occupied_source_slots": len(
                            self._coverage.occupied_domains(
                                registry.run_active_domains,
                            )
                        ),
                        **self._coverage.snapshot(),
                        "max_domains": self.project.crawl.max_domains,
                        "query": query.query,
                    },
                )
            )
            print(
                f"      🧭 Search backfill aktivizēts: "
                f"{record.domain} "
                f"(score={record.relevance_score:.2f}, "
                f"reason={reason})"
                f" local={ranked_hit.audit_label}"
            )
            frontier.add(
                normalized,
                priority=75 + score,
                depth=0,
                discovery_depth=0,
                source_url="",
                source_type="search_backfill",
            )

        return activated

    def _enrich_entities(self, result: ResearchRunResult):
        result.entities = self._enrich_batch(result.entities)

    def _enrich_batch(self, entities: list[MarketEntity]) -> list[MarketEntity]:
        if not entities:
            return []

        print("")
        print(
            f"🧠 Analīzes posms: "
            f"{len(entities)} atrasti tirgus objekti."
        )

        enrichments = self.ai.enrich_many(
            entities,
            self.project,
        )

        if len(enrichments) != len(entities):
            raise RuntimeError(
                "AI provider atgrieza neatbilstošu rezultātu skaitu."
            )

        enriched_entities = []

        for entity, enrichment in zip(
            entities,
            enrichments,
        ):
            enriched = entity.apply_enrichment(enrichment)
            enriched = apply_target_identity_gate(
                enriched,
                self.project,
            )
            enriched_entities.append(enriched)

            status = "✅" if enriched.is_relevant else "⚪"
            target_status = enriched.attributes.get(
                "target_identity_status"
            )
            target_note = (
                f" · target={target_status}"
                if target_status
                else ""
            )

            print(
                f"   {status} {enriched.title[:56]} | "
                f"{enriched.category} | "
                f"relevance={enriched.relevance_score:.2f}"
                f"{target_note}"
            )

        return enriched_entities

    def _assess_target_coverage(
        self,
        result: ResearchRunResult,
    ) -> None:
        if not self._coverage.specific_target:
            return

        outcomes = Counter(
            str(
                entity.attributes.get(
                    "target_identity_status",
                    "not_evaluated",
                )
            )
            for entity in result.entities
        )
        previous_stop_reason = result.stop_reason
        decision = "target_coverage_sufficient"
        if self._coverage.needs_evidence:
            decision = "insufficient_target_coverage"
            result.stop_reason = decision
        result.adaptive_decisions.append(
            AdaptiveDecision(
                stage="coverage_assessment",
                decision=decision,
                target=self.project.id,
                signals={
                    **self._coverage.snapshot(),
                    "target_identity_outcomes": dict(outcomes),
                    "previous_stop_reason": previous_stop_reason,
                    "visited_pages": result.visited_pages,
                    "failed_pages": result.failed_pages,
                    "search_results_unique":
                        result.search_results_unique,
                    "search_domains_activated":
                        result.search_domains_activated,
                },
            )
        )

    def _sleep(self):
        if self.project.crawl.async_enabled:
            return
        if self.project.crawl.delay_seconds > 0:
            time.sleep(self.project.crawl.delay_seconds)
