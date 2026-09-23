from __future__ import annotations

import json
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PRICE_RE = re.compile(
    r"(?<!\d)(\d{1,9}(?:[.,]\d{1,2})?)\s*(€|EUR|eur)",
    re.IGNORECASE,
)


def clean_text(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = unescape(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_price(value: Any) -> float | None:
    if value is None:
        return None
    text = clean_text(value, 100)
    match = re.search(r"(\d{1,9}(?:[.,]\d{1,2})?)", text)
    if not match:
        return None
    try:
        return round(float(match.group(1).replace(",", ".")), 2)
    except ValueError:
        return None


def meta(
    soup: BeautifulSoup,
    *,
    prop: str | None = None,
    name: str | None = None,
) -> str:
    attrs = {}
    if prop:
        attrs["property"] = prop
    if name:
        attrs["name"] = name
    tag = soup.find("meta", attrs=attrs)
    if not tag:
        return ""
    return clean_text(tag.get("content"), 1500)


def absolute_image(value: Any, base_url: str) -> str:
    if isinstance(value, str):
        return urljoin(base_url, value)
    if isinstance(value, list) and value:
        return absolute_image(value[0], base_url)
    if isinstance(value, dict):
        for key in ("url", "contentUrl"):
            if value.get(key):
                return urljoin(base_url, str(value[key]))
    return ""
