from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spriditis.core.entities import ExtractionEvidence, MarketEntity

from .common import absolute_image, clean_text, parse_price


def _fact(
    value: Any,
    *,
    page_url: str,
    confidence: float,
    evidence: str,
) -> ExtractionEvidence:
    return ExtractionEvidence(
        value=value,
        source_url=page_url,
        extraction_method="json-ld",
        confidence=confidence,
        evidence=evidence,
    )


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


def _identity_value(value: Any) -> str:
    if isinstance(value, (str, int, float)):
        return clean_text(str(value), 200)
    if isinstance(value, dict):
        return clean_text(
            value.get("name")
            or value.get("model")
            or value.get("value"),
            200,
        )
    if isinstance(value, list):
        for item in value:
            resolved = _identity_value(item)
            if resolved:
                return resolved
    return ""


def _identity_attributes(node: dict[str, Any]) -> dict[str, str]:
    attributes: dict[str, str] = {}

    mappings = {
        "brand": ("brand",),
        "manufacturer": ("manufacturer",),
        "model": ("model",),
        "mpn": ("mpn",),
        "sku": ("sku",),
        "gtin": (
            "gtin14",
            "gtin13",
            "gtin12",
            "gtin8",
            "gtin",
        ),
    }

    for target, source_keys in mappings.items():
        for key in source_keys:
            value = _identity_value(node.get(key))
            if value:
                attributes[target] = value
                break

    return attributes


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
            raw_currency = (
                offers.get("priceCurrency")
                or node.get("priceCurrency")
            )
            currency = clean_text(
                raw_currency or "EUR",
                10,
            ).upper()

            source_url = urljoin(
                page_url,
                str(node.get("url") or offers.get("url") or page_url),
            )
            description = clean_text(node.get("description"), 2500)

            seller = _seller_name(node)
            image_url = absolute_image(node.get("image"), page_url)
            attributes = _identity_attributes(node)

            field_evidence: dict[str, ExtractionEvidence] = {
                "title": _fact(
                    title,
                    page_url=page_url,
                    confidence=0.98,
                    evidence="jsonld:name",
                ),
                "source_url": _fact(
                    source_url,
                    page_url=page_url,
                    confidence=0.98,
                    evidence="jsonld:url|offers.url|page_url",
                ),
            }

            if description:
                field_evidence["description"] = _fact(
                    description,
                    page_url=page_url,
                    confidence=0.98,
                    evidence="jsonld:description",
                )
            if price is not None:
                field_evidence["price"] = _fact(
                    price,
                    page_url=page_url,
                    confidence=0.98,
                    evidence="jsonld:offers.price|offers.lowPrice|price",
                )
            if currency:
                field_evidence["currency"] = _fact(
                    currency or "EUR",
                    page_url=page_url,
                    confidence=0.98 if raw_currency else 0.55,
                    evidence=(
                        "jsonld:offers.priceCurrency|priceCurrency"
                        if raw_currency
                        else "default:EUR"
                    ),
                )
            if seller:
                field_evidence["seller"] = _fact(
                    seller,
                    page_url=page_url,
                    confidence=0.94,
                    evidence="jsonld:seller|brand|manufacturer",
                )
            if image_url:
                field_evidence["image_url"] = _fact(
                    image_url,
                    page_url=page_url,
                    confidence=0.98,
                    evidence="jsonld:image",
                )

            for key, value in attributes.items():
                field_evidence[f"attributes.{key}"] = _fact(
                    value,
                    page_url=page_url,
                    confidence=0.98,
                    evidence=f"jsonld:{key}",
                )

            entities.append(
                MarketEntity(
                    title=title,
                    entity_type="product",
                    source_url=source_url,
                    source_domain=(urlparse(source_url).hostname or "").lower(),
                    description=description,
                    price=price,
                    currency=currency or "EUR",
                    seller=seller,
                    image_url=image_url,
                    attributes=attributes,
                    extraction_method="json-ld",
                    evidence=clean_text(f"{title}. {description}", 800),
                    field_evidence=field_evidence,
                )
            )

    return entities
