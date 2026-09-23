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

from .frontier import URLFrontier
from .policy import (
    host_key,
    is_safe_public_url,
    normalize_url,
    text_relevance_score,
    url_allowed,
)
from .robots import RobotsCache


class ResearchCrawler:
    def __init__(
        self,
        settings: AppSettings,
        project: ResearchProject,
        ai: AIProvider,
    ):
        self.settings = settings
        self.project = project
        self.ai = ai

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

    def crawl(self) -> ResearchRunResult:
        result = ResearchRunResult(project_id=self.project.id)

        frontier = URLFrontier()
        visited: set[str] = set()
        entity_keys: set[str] = set()
        pages_by_domain: Counter[str] = Counter()

        seeds: list[str] = []

        for raw in self.project.seed_urls:
            url = normalize_url(raw)

            if url and is_safe_public_url(url):
                seeds.append(url)
                frontier.add(url, priority=100, depth=0)

        if not seeds:
            raise ValueError("Projektam nav neviena derīga seed URL.")

        known_domains = {host_key(url) for url in seeds}
        result.discovered_domains.update(known_domains)

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

            if (
                pages_by_domain[domain]
                >= self.project.crawl.max_pages_per_domain
            ):
                continue

            if not url_allowed(
                self.project,
                url,
                seed_urls=seeds,
                known_domains=known_domains,
            ):
                continue

            if (
                self.project.crawl.respect_robots
                and not self.robots.can_fetch(url)
            ):
                result.skipped_by_robots += 1
                visited.add(url)
                print(f"🤖 robots.txt neļauj: {url}")
                continue

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
                print(f"⚠️ HTTP kļūda: {exc}")
                continue

            final_url = normalize_url(response.url) or url

            if not is_safe_public_url(final_url):
                visited.add(url)
                result.failed_pages += 1
                print(
                    f"⚠️ Nedrošs redirect URL, izlaižam: {final_url}"
                )
                continue

            final_domain = host_key(final_url)
            known_domains.add(final_domain)
            result.discovered_domains.add(final_domain)

            visited.add(url)
            visited.add(final_url)
            pages_by_domain[final_domain] += 1
            result.visited_pages += 1

            if response.status_code != 200:
                result.failed_pages += 1
                self._sleep()
                continue

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if content_type and "html" not in content_type:
                self._sleep()
                continue

            try:
                entities = extract_entities(
                    response.text,
                    final_url,
                    self.project,
                )
            except Exception as exc:
                entities = []
                print(f"⚠️ Extraction kļūda: {exc}")

            # Alpha.3: šajā posmā AI vēl netiek saukts.
            # Vispirms pabeidzam crawl/extraction, pēc tam veicam batch AI analīzi.
            for entity in entities:
                if entity.stable_key in entity_keys:
                    continue

                entity_keys.add(entity.stable_key)
                result.entities.append(entity)

                price_text = (
                    f"{entity.price:.2f} {entity.currency}"
                    if entity.price is not None
                    else "?"
                )

                print(
                    f"   📦 Atrasts: {entity.title[:62]} | "
                    f"{price_text}"
                )

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup.find_all("a", href=True):
                absolute = normalize_url(
                    urljoin(final_url, tag["href"])
                )

                if not absolute or absolute in visited:
                    continue

                if not is_safe_public_url(absolute):
                    continue

                target_domain = host_key(absolute)
                anchor = " ".join(tag.stripped_strings)

                score = text_relevance_score(
                    self.project,
                    absolute,
                    anchor,
                )

                is_external = target_domain != final_domain

                if (
                    self.project.crawl.mode == "domain"
                    and is_external
                ):
                    continue

                if is_external:
                    if target_domain not in known_domains:
                        if (
                            len(known_domains)
                            >= self.project.crawl.max_domains
                        ):
                            continue

                        if (
                            score
                            < self.project.crawl.external_link_threshold
                        ):
                            continue

                        known_domains.add(target_domain)
                        result.discovered_domains.add(target_domain)

                if not url_allowed(
                    self.project,
                    absolute,
                    seed_urls=seeds,
                    known_domains=known_domains,
                ):
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

        result.finished_at = datetime.now(timezone.utc).isoformat()
        return result

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

            status = (
                "✅"
                if enriched.is_relevant
                else "⚪"
            )

            print(
                f"   {status} {enriched.title[:56]} | "
                f"{enriched.category} | "
                f"relevance={enriched.relevance_score:.2f}"
            )

        result.entities = enriched_entities

    def _sleep(self):
        if self.project.crawl.delay_seconds > 0:
            time.sleep(self.project.crawl.delay_seconds)
