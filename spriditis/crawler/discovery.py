from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

from spriditis.core.domains import DomainDiscovery, DomainRecord, utc_now
from spriditis.core.projects import ResearchProject

from .policy import host_key, url_safety_reason


def score_to_ratio(score: int) -> float:
    return max(0.0, min(float(score), 100.0)) / 100.0


class DomainRegistry:
    def __init__(self, project: ResearchProject):
        self.project = project
        self.records: dict[str, DomainRecord] = {}
        self.discoveries: list[DomainDiscovery] = []

    def add_seed(self, url: str) -> DomainRecord:
        domain = host_key(url)
        record = self._get_or_create(
            domain,
            status="active",
            discovered_via="seed",
            discovered_from_url="",
            relevance_score=1.0,
        )
        record.status = "active"
        record.reason = "seed"
        record.last_seen = utc_now()
        return record

    def observe_link(
        self,
        *,
        source_url: str,
        target_url: str,
        anchor_text: str,
        raw_score: int,
    ) -> tuple[DomainRecord, DomainDiscovery]:
        source_domain = host_key(source_url)
        target_domain = host_key(target_url)
        ratio = score_to_ratio(raw_score)

        safe, safety_reason = url_safety_reason(target_url)

        if not safe:
            status = "blocked"
            action = "blocked"
            reason = safety_reason
        elif target_domain in self.records and self.records[target_domain].status == "active":
            status = "active"
            action = "known"
            reason = "already_active"
        elif self.project.crawl.mode == "domain":
            status = "candidate"
            action = "recorded"
            reason = "domain_mode"
        elif raw_score < self.project.crawl.external_link_threshold:
            status = "candidate"
            action = "recorded"
            reason = "below_threshold"
        elif self.active_count >= self.project.crawl.max_domains:
            status = "candidate"
            action = "recorded"
            reason = "domain_budget_reached"
        else:
            status = "active"
            action = "activated"
            reason = "relevance_threshold"

        record = self._get_or_create(
            target_domain,
            status=status,
            discovered_via="external_link",
            discovered_from_url=source_url,
            relevance_score=ratio,
        )

        # Do not downgrade a domain that was already active.
        if record.status != "active":
            record.status = status

        record.relevance_score = max(record.relevance_score, ratio)
        record.last_seen = utc_now()

        if not record.reason or status in {"blocked", "active"}:
            record.reason = reason

        discovery = DomainDiscovery(
            source_domain=source_domain,
            target_domain=target_domain,
            source_url=source_url,
            target_url=target_url,
            anchor_text=anchor_text[:500],
            relevance_score=ratio,
            action=action,
            reason=reason,
        )
        self.discoveries.append(discovery)
        return record, discovery

    def mark_page(self, domain: str):
        record = self._get_or_create(domain)
        record.pages_seen += 1
        record.last_seen = utc_now()
        record.last_crawled = utc_now()

    def mark_entities(self, domain: str, count: int):
        record = self._get_or_create(domain)
        record.entities_found += max(0, count)
        record.last_seen = utc_now()

    def mark_robots(self, domain: str, status: str):
        record = self._get_or_create(domain)
        record.robots_status = status
        record.last_seen = utc_now()

    def mark_sitemap(self, domain: str, status: str, urls_found: int = 0):
        record = self._get_or_create(domain)
        record.sitemap_status = status
        record.sitemap_urls_found = max(record.sitemap_urls_found, max(0, urls_found))
        record.last_seen = utc_now()

    def mark_failed(self, domain: str, reason: str):
        record = self._get_or_create(domain)
        if record.status != "blocked":
            record.status = "failed"
        record.reason = reason
        record.last_seen = utc_now()

    @property
    def active_count(self) -> int:
        return sum(1 for record in self.records.values() if record.status == "active")

    def _get_or_create(
        self,
        domain: str,
        *,
        status: str = "candidate",
        discovered_via: str = "link",
        discovered_from_url: str = "",
        relevance_score: float = 0.0,
    ) -> DomainRecord:
        record = self.records.get(domain)

        if record is None:
            record = DomainRecord(
                domain=domain,
                status=status,
                discovered_via=discovered_via,
                discovered_from_url=discovered_from_url,
                relevance_score=relevance_score,
            )
            self.records[domain] = record

        return record


def parse_sitemap_xml(
    xml_text: str,
    *,
    max_urls: int = 100,
) -> tuple[str, list[str]]:
    """
    Returns (kind, locs), where kind is urlset/sitemapindex/invalid.
    """
    if not xml_text.strip():
        return "invalid", []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return "invalid", []

    root_name = root.tag.rsplit("}", 1)[-1].lower()

    if root_name not in {"urlset", "sitemapindex"}:
        return "invalid", []

    locs: list[str] = []

    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1].lower() != "loc":
            continue

        value = (elem.text or "").strip()

        if value:
            locs.append(value)

        if len(locs) >= max_urls:
            break

    return root_name, locs


@dataclass
class SitemapResult:
    status: str
    urls: list[str]


class SitemapDiscovery:
    def __init__(
        self,
        session: requests.Session,
        *,
        user_agent: str,
        timeout: int,
    ):
        self.session = session
        self.user_agent = user_agent
        self.timeout = timeout

    def discover(
        self,
        page_url: str,
        *,
        max_urls: int,
    ) -> SitemapResult:
        if max_urls <= 0:
            return SitemapResult(status="disabled", urls=[])

        parsed = urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        candidates: list[str] = []

        # First read explicit Sitemap: lines from robots.txt.
        robots_url = f"{base}/robots.txt"
        try:
            response = self.session.get(
                robots_url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
            if response.status_code == 200:
                for line in response.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        value = line.split(":", 1)[1].strip()
                        if value:
                            candidates.append(value)
        except requests.RequestException:
            pass

        default_sitemap = f"{base}/sitemap.xml"
        if default_sitemap not in candidates:
            candidates.append(default_sitemap)

        collected: list[str] = []
        seen_candidates: set[str] = set()

        while candidates and len(collected) < max_urls:
            sitemap_url = candidates.pop(0)

            if sitemap_url in seen_candidates:
                continue

            seen_candidates.add(sitemap_url)

            try:
                response = self.session.get(
                    sitemap_url,
                    timeout=self.timeout,
                    headers={"User-Agent": self.user_agent},
                )
            except requests.RequestException:
                continue

            if response.status_code != 200:
                continue

            kind, locs = parse_sitemap_xml(
                response.text,
                max_urls=max_urls,
            )

            if kind == "urlset":
                for loc in locs:
                    if host_key(loc) == host_key(page_url):
                        collected.append(loc)
                    if len(collected) >= max_urls:
                        break

            elif kind == "sitemapindex":
                for loc in locs:
                    if host_key(loc) == host_key(page_url):
                        candidates.append(loc)

        if collected:
            return SitemapResult(status="found", urls=collected)

        return SitemapResult(status="not_found", urls=[])
