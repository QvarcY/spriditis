from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.domains import DomainRecord
from spriditis.core.feeds import FeedState
from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.extraction.engine import extract_entities
from spriditis.search.base import SearchProvider, SearchProviderError
from spriditis.search.query import build_search_queries
from spriditis.search.relevance import LocalRelevance, local_relevance_signals

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

        self.session = requests.Session()
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

    def crawl(self) -> ResearchRunResult:
        result = ResearchRunResult(project_id=self.project.id)

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
                frontier.add(
                    url,
                    priority=100,
                    depth=0,
                    source_type="seed",
                )

        if self.project.crawl.mode == "expedition":
            self._seed_from_search(frontier, registry, result)

        if not frontier:
            if self.project.crawl.mode == "expedition":
                raise ValueError(
                    "Expedition neieguva nevienu derīgu sākuma URL no seed vai SearchProvider."
                )
            raise ValueError("Projektam nav neviena derīga seed URL.")

        while (
            frontier
            and result.visited_pages < self.project.crawl.max_pages_total
        ):
            item = frontier.pop()
            url = item.url

            if url in visited:
                continue

            if item.depth > self.project.crawl.max_depth:
                continue

            domain = host_key(url)
            record = registry.records.get(domain)

            if record is None or record.status != "active":
                continue

            if (
                pages_by_domain[domain]
                >= self.project.crawl.max_pages_per_domain
            ):
                continue

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

            try:
                response = self.session.get(
                    url,
                    timeout=self.settings.request_timeout_seconds,
                    allow_redirects=True,
                )
            except requests.RequestException as exc:
                visited.add(url)
                result.failed_pages += 1
                registry.mark_failed(domain, f"http_error:{type(exc).__name__}")
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

                        if (
                            feed_event.action == "activated"
                            and record.status == "active"
                        ):
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

            for entity in entities:
                if entity.stable_key in entity_keys:
                    continue

                entity_keys.add(entity.stable_key)
                result.entities.append(entity)
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

                score = text_relevance_score(
                    self.project,
                    absolute,
                    anchor,
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

                    if (
                        discovery.action == "activated"
                        and record.status == "active"
                    ):
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
                        continue

                    if (
                        next_discovery_depth
                        > self.project.crawl.max_discovery_depth
                    ):
                        continue
                else:
                    if not is_safe_public_url(absolute):
                        continue
                    next_discovery_depth = item.discovery_depth

                priority = 20 + score

                if not is_external:
                    priority += 15
                    penalty = self._source_diversity_penalty(
                        final_domain,
                        registry,
                    )
                    if penalty:
                        priority -= penalty
                        result.diversity_penalties_applied += 1
                        result.diversity_domains_penalized.add(final_domain)

                frontier.add(
                    absolute,
                    priority=priority,
                    depth=item.depth + 1,
                    discovery_depth=next_discovery_depth,
                    source_url=final_url,
                    source_type="html_link",
                )

            new_active_domains = len(
                set(registry.run_active_domains) - active_domains_before
            )
            if self._update_adaptive_stop(
                result,
                new_entities=new_entities,
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
                registry.active_count >= self.project.crawl.max_domains
                and any(
                    item.reason == "domain_budget_reached"
                    for item in registry.discoveries
                )
            ):
                result.stop_reason = "max_domains"
            else:
                result.stop_reason = "budget_exhausted"

        self._enrich_entities(result)

        result.domains = registry.current_run_records()
        result.domain_discoveries = registry.discoveries
        result.finished_at = datetime.now(timezone.utc).isoformat()
        return result

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
        )
        if not queries:
            raise ValueError(
                "Expedition režīmam nav neviena search query. "
                "Pievieno keywords vai search.queries."
            )

        language = self.project.languages[0] if self.project.languages else "all"

        print("")
        print(
            f"🔎 Expedition: {self.search_provider.name} · "
            f"{len(queries)} vaicājumi"
        )

        seen_search_urls: set[str] = set()

        for query in queries:
            result.search_queries_issued += 1
            memory_note = ""
            if query.memory_state != "untested":
                rate = query.memory_productive_domain_rate or 0.0
                memory_note = (
                    f" · memory={query.memory_state}"
                    f" yield={rate:.1%}"
                    f" productive={query.memory_productive_domains}"
                    f"/{query.memory_unique_domains}"
                    f" runs={query.memory_runs}"
                )
            print(f"   🔍 {query.query}{memory_note}")

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
            except SearchProviderError as exc:
                result.search_provider_errors += 1
                detail = f"kind={exc.kind}, attempts={exc.attempts}"
                if exc.status_code is not None:
                    detail += f", http={exc.status_code}"
                print(f"   ⚠️ SearchProvider kļūda: {exc} [{detail}]")
                continue

            for ranked_hit in ranked_hits:
                hit = ranked_hit.hit
                result.search_results_seen += 1
                normalized = normalize_url(hit.url)
                if not normalized:
                    continue
                if normalized in seen_search_urls:
                    result.search_results_duplicates += 1
                    continue
                seen_search_urls.add(normalized)
                result.search_results_unique += 1

                evidence = " ".join(
                    part for part in [hit.title, hit.snippet] if part
                )
                score = text_relevance_score(
                    self.project,
                    normalized,
                    evidence,
                )

                record, discovery = registry.observe_search_result(
                    provider=self.search_provider.name,
                    query_text=query.query,
                    target_url=normalized,
                    title=hit.title,
                    snippet=hit.snippet,
                    raw_score=score,
                )

                if discovery.action == "activated":
                    result.search_domains_activated += 1
                    profile = self.source_profiles.get(record.domain)
                    state = self._source_memory_state(record.domain)
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
                        f"{record.domain} (score={record.relevance_score:.2f})"
                        f"{source_note}"
                        f" local={ranked_hit.audit_label}"
                    )

                if record.status == "active":
                    frontier.add(
                        normalized,
                        priority=80 + score,
                        depth=0,
                        discovery_depth=0,
                        source_url="",
                        source_type="search_provider",
                    )

    def _enrich_entities(self, result: ResearchRunResult):
        if not result.entities:
            return

        print("")
        print(
            f"🧠 Analīzes posms: "
            f"{len(result.entities)} atrasti tirgus objekti."
        )

        enrichments = self.ai.enrich_many(
            result.entities,
            self.project,
        )

        if len(enrichments) != len(result.entities):
            raise RuntimeError(
                "AI provider atgrieza neatbilstošu rezultātu skaitu."
            )

        enriched_entities = []

        for entity, enrichment in zip(
            result.entities,
            enrichments,
        ):
            enriched = entity.apply_enrichment(enrichment)
            enriched_entities.append(enriched)

            status = "✅" if enriched.is_relevant else "⚪"

            print(
                f"   {status} {enriched.title[:56]} | "
                f"{enriched.category} | "
                f"relevance={enriched.relevance_score:.2f}"
            )

        result.entities = enriched_entities

    def _sleep(self):
        if self.project.crawl.delay_seconds > 0:
            time.sleep(self.project.crawl.delay_seconds)
