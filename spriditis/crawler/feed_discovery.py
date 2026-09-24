from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from spriditis.core.feeds import FeedEntry, FeedState

from .policy import host_key, normalize_url, url_safety_reason


FEED_MIME_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/feed+json",
}

COMMON_FEED_PATHS = (
    "/feed",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/feed.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(parent: ET.Element, *names: str) -> str:
    wanted = {name.lower() for name in names}
    for child in parent:
        if _local_name(child.tag) in wanted:
            return (child.text or "").strip()
    return ""


def _parse_time(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def parse_feed(
    text: str,
    *,
    content_type: str = "",
    max_entries: int = 50,
) -> tuple[str, list[FeedEntry]]:
    if max_entries <= 0 or not text.strip():
        return "invalid", []

    stripped = text.lstrip()
    mime = (content_type or "").split(";", 1)[0].strip().lower()

    if mime in {"application/feed+json", "application/json"} or stripped.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return "invalid", []

        items = payload.get("items")
        if not isinstance(items, list):
            return "invalid", []

        entries: list[FeedEntry] = []
        for item in items[:max_entries]:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("external_url") or "").strip()
            if not url:
                continue
            entries.append(
                FeedEntry(
                    entry_id=str(item.get("id") or url).strip(),
                    url=url,
                    title=str(item.get("title") or "").strip(),
                    published=str(
                        item.get("date_published") or item.get("date_modified") or ""
                    ).strip(),
                    summary=str(
                        item.get("summary")
                        or item.get("content_text")
                        or item.get("content_html")
                        or ""
                    ).strip(),
                )
            )
        return "jsonfeed", entries

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return "invalid", []

    root_name = _local_name(root.tag)

    if root_name == "feed":
        entries: list[FeedEntry] = []
        for elem in root:
            if _local_name(elem.tag) != "entry":
                continue
            url = ""
            for child in elem:
                if _local_name(child.tag) != "link":
                    continue
                href = (child.attrib.get("href") or "").strip()
                rel = (child.attrib.get("rel") or "alternate").strip().lower()
                if href and rel in {"", "alternate"}:
                    url = href
                    break
            if not url:
                continue
            entries.append(
                FeedEntry(
                    entry_id=_child_text(elem, "id") or url,
                    url=url,
                    title=_child_text(elem, "title"),
                    published=_child_text(elem, "published", "updated"),
                    summary=_child_text(elem, "summary", "content"),
                )
            )
            if len(entries) >= max_entries:
                break
        return "atom", entries

    if root_name in {"rss", "rdf"}:
        entries: list[FeedEntry] = []
        for elem in root.iter():
            if _local_name(elem.tag) != "item":
                continue
            link = _child_text(elem, "link")
            guid = _child_text(elem, "guid")
            url = link or (guid if guid.startswith(("http://", "https://")) else "")
            if not url:
                continue
            entries.append(
                FeedEntry(
                    entry_id=guid or url,
                    url=url,
                    title=_child_text(elem, "title"),
                    published=_child_text(elem, "pubdate", "date"),
                    summary=_child_text(elem, "description", "summary"),
                )
            )
            if len(entries) >= max_entries:
                break
        return "rss", entries

    return "invalid", []


def discover_feed_urls(
    page_url: str,
    html: str,
    *,
    probe_common_paths: bool,
) -> list[str]:
    page_domain = host_key(page_url)
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for tag in soup.find_all("link", href=True):
        rel = tag.get("rel") or []
        if isinstance(rel, str):
            rel = rel.split()
        if "alternate" not in {str(value).lower() for value in rel}:
            continue
        mime = str(tag.get("type") or "").split(";", 1)[0].strip().lower()
        href = str(tag.get("href") or "").strip()
        if not href:
            continue
        looks_like_json_feed = (
            mime == "application/json"
            and href.lower().endswith((".json", "/feed", "/feed.json"))
        )
        if mime not in FEED_MIME_TYPES and not looks_like_json_feed:
            continue
        candidates.append(urljoin(page_url, href))

    if probe_common_paths:
        parsed = urlparse(page_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        candidates.extend(urljoin(base, path) for path in COMMON_FEED_PATHS)

    result: list[str] = []
    seen: set[str] = set()
    page_path = (urlparse(page_url).path or "/").rstrip("/") or "/"

    def candidate_score(url: str) -> int:
        path = (urlparse(url).path or "/").lower()
        score = 0

        # Prefer a feed scoped to the page/section being researched.
        if page_path != "/" and path.startswith(page_path.lower() + "/"):
            score += 50

        # Generic feed-like paths are useful, but less specific.
        if "feed" in path or path.endswith((".rss", ".atom", ".xml")):
            score += 10

        # Comment feeds are usually discussion noise, not source content.
        if "/comments/" in path or "comments/feed" in path:
            score -= 100

        return score

    for raw in candidates:
        normalized = normalize_url(raw)
        if not normalized or normalized in seen:
            continue
        if host_key(normalized) != page_domain:
            continue
        safe, _ = url_safety_reason(normalized, allow_feed_resource=True)
        if not safe:
            continue
        seen.add(normalized)
        result.append(normalized)

    result.sort(key=candidate_score, reverse=True)
    return result


def _new_entries(
    entries: list[FeedEntry],
    previous: FeedState | None,
) -> list[FeedEntry]:
    if previous is None:
        return list(entries)

    if previous.last_entry_id:
        newer: list[FeedEntry] = []
        for entry in entries:
            if entry.entry_id == previous.last_entry_id:
                return newer
            newer.append(entry)
        if not previous.last_published:
            return newer

    previous_time = _parse_time(previous.last_published)
    if previous_time is None:
        return list(entries)

    newer = []
    for entry in entries:
        entry_time = _parse_time(entry.published)
        if entry_time is None or entry_time > previous_time:
            newer.append(entry)
    return newer


@dataclass
class FeedFetchResult:
    state: FeedState
    entries: list[FeedEntry]
    new_entries: list[FeedEntry]
    not_modified: bool = False


@dataclass
class FeedScanResult:
    candidate_count: int
    fetches: list[FeedFetchResult]
    errors: int = 0


class FeedDiscovery:
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

    def scan(
        self,
        page_url: str,
        html: str,
        *,
        previous_states: dict[str, FeedState],
        max_entries: int,
        max_feeds: int,
        probe_common_paths: bool,
    ) -> FeedScanResult:
        if max_entries <= 0 or max_feeds <= 0:
            return FeedScanResult(candidate_count=0, fetches=[])

        candidates = discover_feed_urls(
            page_url,
            html,
            probe_common_paths=probe_common_paths,
        )
        fetches: list[FeedFetchResult] = []
        errors = 0
        confirmed = 0

        for feed_url in candidates:
            if confirmed >= max_feeds:
                break
            previous = previous_states.get(feed_url)
            headers = {
                "User-Agent": self.user_agent,
                "Accept": (
                    "application/rss+xml, application/atom+xml, "
                    "application/feed+json, application/json, "
                    "application/xml, text/xml;q=0.9, */*;q=0.5"
                ),
            }
            if previous and previous.etag:
                headers["If-None-Match"] = previous.etag
            if previous and previous.last_modified:
                headers["If-Modified-Since"] = previous.last_modified

            try:
                response = self.session.get(
                    feed_url,
                    timeout=self.timeout,
                    headers=headers,
                    allow_redirects=True,
                )
            except requests.RequestException as exc:
                errors += 1
                if previous:
                    state = replace(previous)
                    state.status = "error"
                    state.last_checked = _now()
                    state.last_seen = state.last_checked
                    state.last_error = f"http_error:{type(exc).__name__}"
                    fetches.append(FeedFetchResult(state, [], []))
                continue

            final_url = normalize_url(response.url) or feed_url
            safe, reason = url_safety_reason(
                final_url,
                allow_feed_resource=True,
            )
            if not safe or host_key(final_url) != host_key(page_url):
                errors += 1
                if previous:
                    state = replace(previous)
                    state.status = "error"
                    state.last_checked = _now()
                    state.last_seen = state.last_checked
                    state.last_error = f"unsafe_redirect:{reason}"
                    fetches.append(FeedFetchResult(state, [], []))
                continue

            now = _now()

            if response.status_code == 304 and previous:
                state = replace(previous)
                # 304 is a fetch outcome, not a feed lifecycle state.
                # Keep the feed active and expose "not modified" via run metrics.
                state.status = "active"
                state.last_checked = now
                state.last_seen = now
                state.last_error = ""
                confirmed += 1
                fetches.append(FeedFetchResult(state, [], [], True))
                continue

            if response.status_code != 200:
                errors += 1
                if previous:
                    state = replace(previous)
                    state.status = "error"
                    state.last_checked = now
                    state.last_seen = now
                    state.last_error = f"http_status:{response.status_code}"
                    fetches.append(FeedFetchResult(state, [], []))
                continue

            feed_type, entries = parse_feed(
                response.text,
                content_type=response.headers.get("Content-Type", ""),
                max_entries=max_entries,
            )
            if feed_type == "invalid":
                errors += 1
                if previous:
                    state = replace(previous)
                    state.status = "error"
                    state.last_checked = now
                    state.last_seen = now
                    state.last_error = "invalid_feed"
                    fetches.append(FeedFetchResult(state, [], []))
                continue

            state = replace(previous) if previous else FeedState(
                feed_url=feed_url,
                domain=host_key(feed_url),
                first_seen=now,
            )
            # Keep the discovered/request URL as the persistent resource key.
            # A same-host redirect may canonicalize the response URL, but if
            # we persisted only the redirect target, the next HTML discovery
            # would miss the saved ETag/Last-Modified state.
            state.feed_url = feed_url
            state.domain = host_key(feed_url)
            state.feed_type = feed_type
            state.status = "active"
            state.etag = response.headers.get("ETag", "") or state.etag
            state.last_modified = (
                response.headers.get("Last-Modified", "") or state.last_modified
            )
            state.last_checked = now
            state.last_success = now
            state.last_seen = now
            state.last_error = ""

            fresh = _new_entries(entries, previous)
            state.entries_seen += len(entries)
            state.new_entries += len(fresh)
            if entries:
                state.last_entry_id = entries[0].entry_id
                state.last_published = entries[0].published

            confirmed += 1
            fetches.append(FeedFetchResult(state, entries, fresh))

        return FeedScanResult(
            candidate_count=len(candidates),
            fetches=fetches,
            errors=errors,
        )
