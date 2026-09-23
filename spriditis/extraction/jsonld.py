from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spriditis.core.entities import MarketEntity

from .common import absolute_image, clean_text, parse_price


def _iter_nodes(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _iter_nodes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_nodes(item)


def _is_product_type(value: Any) -> bool:
    if isinstance(value, str):
        return value.lower() == "product"
    if isinstance(value, list):
        return any(str(item).lower() == "product" for item in value)
    return False


def _seller_name(node: dict[str, Any]) -> str:
    for key in ("seller", "brand", "manufacturer"):
        value = node.get(key)
        if isinstance(value, str):
            return clean_text(value, 200)
        if isinstance(value, dict):
            return clean_text(value.get("name"), 200)
    return ""


def extract_jsonld_products(
    soup: BeautifulSoup,
    page_url: str,
) -> list[MarketEntity]:
    entities: list[MarketEntity] = []

    scripts = soup.find_all(
        "script",
        attrs={"type": re.compile(r"ld\+json", re.I)},
    )

    for script in scripts:
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        for node in _iter_nodes(data):
            if not _is_product_type(node.get("@type")):
                continue

            title = clean_text(node.get("name"), 300)
            if not title:
                continue

            offers = node.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                offers = {}

            price = parse_price(
                offers.get("price")
                or offers.get("lowPrice")
                or node.get("price")
            )
            currency = clean_text(
                offers.get("priceCurrency")
                or node.get("priceCurrency")
                or "EUR",
                10,
            ).upper()

            source_url = urljoin(
                page_url,
                str(node.get("url") or offers.get("url") or page_url),
            )
            description = clean_text(node.get("description"), 2500)

            entities.append(
                MarketEntity(
                    title=title,
                    entity_type="product",
                    source_url=source_url,
                    source_domain=(urlparse(source_url).hostname or "").lower(),
                    description=description,
                    price=price,
                    currency=currency or "EUR",
                    seller=_seller_name(node),
                    image_url=absolute_image(node.get("image"), page_url),
                    extraction_method="json-ld",
                    evidence=clean_text(f"{title}. {description}", 800),
                )
            )

    return entities
