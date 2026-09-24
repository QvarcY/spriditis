from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from spriditis.core.entities import ExtractionEvidence, MarketEntity

from .common import clean_text, parse_price


PRODUCT_TYPE_RE = re.compile(r"(?:^|/)Product/?$", re.I)


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
        extraction_method="microdata",
        confidence=confidence,
        evidence=evidence,
    )


def _belongs_to_scope(tag: Tag, scope: Tag) -> bool:
    parent = tag.parent
    while isinstance(parent, Tag):
        if parent is scope:
            return True
        if parent.has_attr("itemscope"):
            return False
        parent = parent.parent
    return False


def _find_prop(scope: Tag, name: str) -> Tag | None:
    pattern = re.compile(
        rf"(?:^|\s){re.escape(name)}(?:\s|$)",
        re.I,
    )
    for tag in scope.find_all(attrs={"itemprop": pattern}):
        if isinstance(tag, Tag) and _belongs_to_scope(tag, scope):
            return tag
    return None


def _prop_value(tag: Tag | None) -> str:
    if tag is None:
        return ""

    for attr in ("content", "href", "src", "datetime"):
        value = tag.get(attr)
        if value:
            return clean_text(value, 2500)

    if tag.has_attr("itemscope"):
        for nested_name in ("name", "model", "value"):
            nested = _find_prop(tag, nested_name)
            if nested is not None:
                value = _prop_value(nested)
                if value:
                    return value

    return clean_text(tag.get_text(" ", strip=True), 2500)


def _prop(scope: Tag, name: str) -> str:
    return _prop_value(_find_prop(scope, name))


def _first_prop(scope: Tag, names: tuple[str, ...]) -> tuple[str, str]:
    for name in names:
        value = _prop(scope, name)
        if value:
            return value, name
    return "", ""


def _absolute(value: str, page_url: str) -> str:
    return urljoin(page_url, value) if value else ""


def extract_microdata_products(
    soup: BeautifulSoup,
    page_url: str,
) -> list[MarketEntity]:
    entities: list[MarketEntity] = []

    scopes = soup.find_all(
        attrs={
            "itemscope": True,
            "itemtype": re.compile(r"schema\.org/(?:[^\s]*/)?Product/?$", re.I),
        }
    )

    for scope in scopes:
        if not isinstance(scope, Tag):
            continue

        title = _prop(scope, "name")
        if not title:
            continue

        description = _prop(scope, "description")

        offers_scope = _find_prop(scope, "offers")
        if offers_scope is not None and not offers_scope.has_attr("itemscope"):
            offers_scope = None

        price_text, price_prop = _first_prop(
            offers_scope or scope,
            ("price", "lowPrice"),
        )
        if not price_text and offers_scope is not None:
            price_text, price_prop = _first_prop(
                scope,
                ("price", "lowPrice"),
            )
        price = parse_price(price_text)

        raw_currency = _prop(
            offers_scope or scope,
            "priceCurrency",
        )
        if not raw_currency and offers_scope is not None:
            raw_currency = _prop(scope, "priceCurrency")
        currency = clean_text(raw_currency or "EUR", 10).upper()

        raw_url = _prop(scope, "url")
        if not raw_url and offers_scope is not None:
            raw_url = _prop(offers_scope, "url")
        source_url = _absolute(raw_url, page_url) if raw_url else page_url

        image_raw = _prop(scope, "image")
        image_url = _absolute(image_raw, page_url)

        seller, seller_prop = _first_prop(
            scope,
            ("seller",),
        )
        if not seller and offers_scope is not None:
            seller, seller_prop = _first_prop(
                offers_scope,
                ("seller",),
            )
        if not seller:
            seller, seller_prop = _first_prop(
                scope,
                ("brand", "manufacturer"),
            )

        attributes: dict[str, str] = {}
        identity_sources: dict[str, str] = {}

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

        for target, source_names in mappings.items():
            value, source_name = _first_prop(scope, source_names)
            if value:
                attributes[target] = value
                identity_sources[target] = source_name

        field_evidence: dict[str, ExtractionEvidence] = {
            "title": _fact(
                title,
                page_url=page_url,
                confidence=0.93,
                evidence="microdata:itemprop=name",
            ),
            "source_url": _fact(
                source_url,
                page_url=page_url,
                confidence=0.93 if raw_url else 0.72,
                evidence=(
                    "microdata:itemprop=url"
                    if raw_url
                    else "page_url"
                ),
            ),
            "currency": _fact(
                currency,
                page_url=page_url,
                confidence=0.93 if raw_currency else 0.52,
                evidence=(
                    "microdata:itemprop=priceCurrency"
                    if raw_currency
                    else "default:EUR"
                ),
            ),
        }

        if description:
            field_evidence["description"] = _fact(
                description,
                page_url=page_url,
                confidence=0.93,
                evidence="microdata:itemprop=description",
            )
        if price is not None:
            field_evidence["price"] = _fact(
                price,
                page_url=page_url,
                confidence=0.93,
                evidence=f"microdata:itemprop={price_prop}",
            )
        if seller:
            field_evidence["seller"] = _fact(
                seller,
                page_url=page_url,
                confidence=0.90,
                evidence=f"microdata:itemprop={seller_prop}",
            )
        if image_url:
            field_evidence["image_url"] = _fact(
                image_url,
                page_url=page_url,
                confidence=0.93,
                evidence="microdata:itemprop=image",
            )

        for key, value in attributes.items():
            field_evidence[f"attributes.{key}"] = _fact(
                value,
                page_url=page_url,
                confidence=0.93,
                evidence=(
                    "microdata:itemprop="
                    + identity_sources[key]
                ),
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
                extraction_method="microdata",
                evidence=clean_text(
                    f"{title}. {description}",
                    800,
                ),
                field_evidence=field_evidence,
            )
        )

    return entities
