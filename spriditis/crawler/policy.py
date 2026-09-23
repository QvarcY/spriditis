from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from spriditis.core.projects import ResearchProject


BLOCKED_HOST_SUFFIXES = (
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "pinterest.com",
    "google.com",
    "google.lv",
    "doubleclick.net",
)

SKIP_PATH_PARTS = (
    "/login",
    "/logout",
    "/register",
    "/registr",
    "/cart",
    "/checkout",
    "/admin",
    "/account",
    "/privacy",
    "/privat",
    "/terms",
    "/noteikumi",
)

BINARY_EXTENSIONS = re.compile(
    r"\.(?:jpg|jpeg|png|gif|webp|svg|pdf|zip|rar|7z|css|js|xml|mp4|mp3|woff2?)$",
    re.I,
)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return ""

    clean_query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        low = key.lower()
        if low.startswith("utm_") or low in {"fbclid", "gclid", "ref"}:
            continue
        clean_query.append((key, value))

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            urlencode(clean_query, doseq=True),
            "",
        )
    )


def host_key(url_or_host: str) -> str:
    if "://" in url_or_host:
        host = urlparse(url_or_host).hostname or ""
    else:
        host = url_or_host
    host = host.lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def same_site(a: str, b: str) -> bool:
    return host_key(a) == host_key(b)


def url_safety_reason(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported_scheme"

    host = (parsed.hostname or "").lower()

    if not host:
        return False, "missing_host"

    if host == "localhost" or host.endswith(".local"):
        return False, "local_host"

    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False, "non_public_ip"
    except ValueError:
        pass

    if any(
        host == blocked or host.endswith("." + blocked)
        for blocked in BLOCKED_HOST_SUFFIXES
    ):
        return False, "blocked_host"

    path = (parsed.path or "").lower()

    if any(part in path for part in SKIP_PATH_PARTS):
        return False, "blocked_path"

    if BINARY_EXTENSIONS.search(path):
        return False, "binary_or_static_file"

    return True, "ok"


def is_safe_public_url(url: str) -> bool:
    safe, _ = url_safety_reason(url)
    return safe


def text_relevance_score(
    project: ResearchProject,
    url: str,
    anchor_text: str = "",
) -> int:
    haystack = f"{url} {anchor_text}".lower()
    score = 0

    for keyword in project.keywords:
        key = keyword.strip().lower()
        if key and key in haystack:
            score += 10

    for keyword in project.negative_keywords:
        key = keyword.strip().lower()
        if key and key in haystack:
            score -= 20

    path = (urlparse(url).path or "").lower()
    if any(part in path for part in ("/product", "/produk", "/katalog", "/shop", "/veikal")):
        score += 20

    depth = len([part for part in path.split("/") if part])
    if depth >= 2:
        score += min(depth * 2, 10)

    return max(-100, min(score, 100))


def url_allowed(
    project: ResearchProject,
    candidate_url: str,
    *,
    seed_urls: list[str],
    known_domains: set[str],
) -> bool:
    if not is_safe_public_url(candidate_url):
        return False

    host = host_key(candidate_url)

    if project.crawl.mode == "domain":
        return any(same_site(candidate_url, seed) for seed in seed_urls)

    if project.crawl.mode == "discovery":
        if host in known_domains:
            return True
        return len(known_domains) < project.crawl.max_domains

    # expedition būs aktīvs meklēšanas režīms nākamajā posmā.
    # 3.1 alpha neizdomā jaunus search seedus, bet var sekot discovery noteikumiem.
    if project.crawl.mode == "expedition":
        if host in known_domains:
            return True
        return len(known_domains) < project.crawl.max_domains

    return False
