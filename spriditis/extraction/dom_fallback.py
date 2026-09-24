from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from spriditis.core.entities import ExtractionEvidence, MarketEntity

from .common import clean_text, parse_price


_PRICE_SUFFIX_RE = re.compile(
    r"(?<!\d)(\d{1,9}(?:[.,]\d{1,2})?)\s*"
    r"(EUR|USD|GBP|CHF|SEK|NOK|DKK|PLN|€|£)\b?",
    re.IGNORECASE,
)
_PRICE_PREFIX_RE = re.compile(
    r"\b(EUR|USD|GBP|CHF|SEK|NOK|DKK|PLN)\s*"
    r"(\d{1,9}(?:[.,]\d{1,2})?)(?!\d)",
    re.IGNORECASE,
)
_PRODUCT_HINT_RE = re.compile(
    r"(?:^|[-_\s])(product|product-detail|product_page|pdp|item-detail)(?:$|[-_\s])",
    re.IGNORECASE,
)
_BUY_TEXT_RE = re.compile(
    r"\b(add to cart|add to basket|buy now|buy|purchase|"
    r"pievienot grozam|ielikt grozā|grozā|pirkt|iegādāties)\b",
    re.IGNORECASE,
)


def _fact(
    value,
    *,
    page_url: str,
    confidence: float,
    evidence: str,
) -> ExtractionEvidence:
    return ExtractionEvidence(
        value=value,
        source_url=page_url,
        extraction_method="dom-fallback",
        confidence=confidence,
        evidence=evidence,
    )


def _marker_text(tag: Tag) -> str:
    parts = [
        str(tag.get("id") or ""),
        " ".join(tag.get("class") or []),
        str(tag.get("data-testid") or ""),
        str(tag.get("data-role") or ""),
        str(tag.get("data-component") or ""),
    ]
    return " ".join(parts).strip()


def _is_price_tag(tag: Tag) -> bool:
    if tag.has_attr("data-price"):
        return True
    marker = _marker_text(tag).casefold()
    return "price" in marker


def _explicit_price(text: str) -> tuple[float | None, str]:
    value = clean_text(text, 200)
    suffix = _PRICE_SUFFIX_RE.search(value)
    if suffix:
        amount = parse_price(suffix.group(1))
        token = suffix.group(2).upper()
    else:
        prefix = _PRICE_PREFIX_RE.search(value)
        if not prefix:
            return None, ""
        token = prefix.group(1).upper()
        amount = parse_price(prefix.group(2))

    currency = {
        "€": "EUR",
        "£": "GBP",
    }.get(token, token)
    return amount, currency


def _find_price(soup: BeautifulSoup) -> tuple[float | None, str, str]:
    for tag in soup.find_all(
        ["div", "span", "p", "strong", "b", "em", "ins", "meta"]
    ):
        if not isinstance(tag, Tag) or not _is_price_tag(tag):
            continue

        raw = (
            tag.get("data-price")
            or tag.get("content")
            or tag.get_text(" ", strip=True)
        )
        amount, currency = _explicit_price(str(raw or ""))
        if amount is not None and currency:
            marker = _marker_text(tag) or tag.name
            return amount, currency, marker

    return None, "", ""


def _find_title(soup: BeautifulSoup) -> tuple[str, str]:
    for tag in soup.find_all("h1"):
        if not isinstance(tag, Tag):
            continue
        title = clean_text(tag.get_text(" ", strip=True), 300)
        if 3 <= len(title) <= 300:
            return title, _marker_text(tag) or "h1"
    return "", ""


def _has_product_url_hint(page_url: str) -> bool:
    path = (urlparse(page_url).path or "").casefold()
    return any(
        token in path
        for token in (
            "/product/",
            "/products/",
            "/item/",
            "/prece/",
            "/produkts/",
            "/p/",
        )
    )


def _has_product_container_hint(soup: BeautifulSoup) -> bool:
    for tag in soup.find_all(["main", "article", "section", "div"]):
        if not isinstance(tag, Tag):
            continue
        marker = _marker_text(tag)
        if marker and _PRODUCT_HINT_RE.search(marker):
            return True
    return False


def _has_buy_action_hint(soup: BeautifulSoup) -> bool:
    for tag in soup.find_all(["button", "a", "input"]):
        if not isinstance(tag, Tag):
            continue
        text = clean_text(
            tag.get("value")
            or tag.get("aria-label")
            or tag.get_text(" ", strip=True),
            200,
        )
        if text and _BUY_TEXT_RE.search(text):
            return True
    return False


def _find_description(soup: BeautifulSoup) -> tuple[str, str]:
    for tag in soup.find_all(["div", "section", "article", "p"]):
        if not isinstance(tag, Tag):
            continue
        marker = _marker_text(tag).casefold()
        if not marker:
            continue
        if (
            "product-description" not in marker
            and "product_description" not in marker
            and "description" not in marker
        ):
            continue
        text = clean_text(tag.get_text(" ", strip=True), 2500)
        if len(text) >= 20:
            return text, _marker_text(tag)
    return "", ""


def extract_dom_fallback_product(
    soup: BeautifulSoup,
    page_url: str,
) -> MarketEntity | None:
    title, title_marker = _find_title(soup)
    if not title:
        return None

    price, currency, price_marker = _find_price(soup)
    if price is None or not currency:
        return None

    product_hints = [
        _has_product_url_hint(page_url),
        _has_product_container_hint(soup),
        _has_buy_action_hint(soup),
    ]
    if not any(product_hints):
        return None

    description, description_marker = _find_description(soup)

    field_evidence: dict[str, ExtractionEvidence] = {
        "title": _fact(
            title,
            page_url=page_url,
            confidence=0.72,
            evidence=f"dom:{title_marker}",
        ),
        "source_url": _fact(
            page_url,
            page_url=page_url,
            confidence=0.72,
            evidence="page_url",
        ),
        "price": _fact(
            price,
            page_url=page_url,
            confidence=0.68,
            evidence=f"dom:{price_marker}:explicit_currency",
        ),
        "currency": _fact(
            currency,
            page_url=page_url,
            confidence=0.68,
            evidence=f"dom:{price_marker}:explicit_currency",
        ),
    }

    if description:
        field_evidence["description"] = _fact(
            description,
            page_url=page_url,
            confidence=0.62,
            evidence=f"dom:{description_marker}",
        )

    return MarketEntity(
        title=title,
        entity_type="product",
        source_url=page_url,
        source_domain=(urlparse(page_url).hostname or "").lower(),
        description=description,
        price=price,
        currency=currency,
        extraction_method="dom-fallback",
        evidence=clean_text(f"{title}. {description}", 800),
        field_evidence=field_evidence,
    )
