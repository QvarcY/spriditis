from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from spriditis.ai.base import AIProvider
from spriditis.config import AppSettings
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.extraction.engine import extract_entities
from spriditis.search.base import SearchProvider, SearchProviderError
from spriditis.search.query import build_search_queries

from .discovery import DomainRegistry, SitemapDiscovery
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
    ):
        self.settings = settings
        self.project = project
        self.ai = ai
        self.search_provider = search_provider

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
        sitemap_checked: set[str] = set()

        registry = DomainRegistry(self.project)

        seeds: list[str] = []

        for raw in self.project.seed_urls:
            url = normalize_url(raw)

            if url and is_safe_public_url(url):
                seeds.append(url)
                registry.add_seed(url)
                frontier.add(url, priority=100, depth=0)

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
                print(f"⚠️ HTTP kļūda: {exc}")
                continue

            final_url = normalize_url(response.url) or url

            if not is_safe_public_url(final_url):
                visited.add(url)
                result.failed_pages += 1
                registry.mark_failed(domain, "unsafe_redirect")
                print(
                    f"⚠️ Nedrošs redirect URL, izlaižam: {final_url}"
                )
                continue

            final_domain = host_key(final_url)

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
                self._sleep()
                continue

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if content_type and "html" not in content_type:
                self._sleep()
                continue

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
                            source_url=final_url,
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
                    record, discovery = registry.observe_link(
                        source_url=final_url,
                        target_url=absolute,
                        anchor_text=anchor,
                        raw_score=score,
                    )

                    if (
                        discovery.action == "activated"
                        and record.status == "active"
                    ):
                        print(
                            f"   🧭 Jauns domēns aktivizēts: "
                            f"{record.domain} "
                            f"(score={record.relevance_score:.2f})"
                        )

                    if record.status != "active":
                        continue

                else:
                    if not is_safe_public_url(absolute):
                        continue

                priority = 20 + score

                if not is_external:
                    priority += 15

                frontier.add(
                    absolute,
                    priority=priority,
                    depth=item.depth + 1,
                    source_url=final_url,
                )

            self._sleep()

        self._enrich_entities(result)

        result.domains = registry.records
        result.domain_discoveries = registry.discoveries
        result.finished_at = datetime.now(timezone.utc).isoformat()
        return result

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

        queries = build_search_queries(self.project)
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
            print(f"   🔍 {query.query}")

            try:
                hits = self.search_provider.search(
                    query.query,
                    language=language,
                    limit=self.project.search.results_per_query,
                    safesearch=self.project.search.safesearch,
                )
            except SearchProviderError as exc:
                result.search_provider_errors += 1
                detail = f"kind={exc.kind}, attempts={exc.attempts}"
                if exc.status_code is not None:
                    detail += f", http={exc.status_code}"
                print(f"   ⚠️ SearchProvider kļūda: {exc} [{detail}]")
                continue

            for hit in hits:
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
                    print(
                        f"      🧭 Search domēns aktivizēts: "
                        f"{record.domain} (score={record.relevance_score:.2f})"
                    )

                if record.status == "active":
                    frontier.add(
                        normalized,
                        priority=80 + score,
                        depth=0,
                        source_url="",
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
