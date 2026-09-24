from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spriditis.core.entities import ExtractionEvidence, MarketEntity

from .common import clean_text, meta, parse_price


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
        extraction_method="opengraph",
        confidence=confidence,
        evidence=evidence,
    )


def extract_opengraph_product(
    soup: BeautifulSoup,
    page_url: str,
) -> MarketEntity | None:
    title = meta(soup, prop="og:title")
    amount = (
        meta(soup, prop="product:price:amount")
        or meta(soup, prop="og:price:amount")
    )
    og_type = meta(soup, prop="og:type").lower()

    if not title:
        return None
    if "product" not in og_type and not amount:
        return None

    raw_currency = (
        meta(soup, prop="product:price:currency")
        or meta(soup, prop="og:price:currency")
    )
    currency = (raw_currency or "EUR").upper()

    description = (
        meta(soup, prop="og:description")
        or meta(soup, name="description")
    )
    image = meta(soup, prop="og:image")

    price = parse_price(amount)
    image_url = urljoin(page_url, image) if image else ""

    field_evidence: dict[str, ExtractionEvidence] = {
        "title": _fact(
            title,
            page_url=page_url,
            confidence=0.88,
            evidence="opengraph:og:title",
        ),
        "source_url": _fact(
            page_url,
            page_url=page_url,
            confidence=0.88,
            evidence="page_url",
        ),
    }

    if description:
        field_evidence["description"] = _fact(
            description,
            page_url=page_url,
            confidence=0.88,
            evidence="opengraph:og:description|meta:description",
        )
    if price is not None:
        field_evidence["price"] = _fact(
            price,
            page_url=page_url,
            confidence=0.88,
            evidence="opengraph:product:price:amount|og:price:amount",
        )
    if currency:
        field_evidence["currency"] = _fact(
            currency,
            page_url=page_url,
            confidence=0.88 if raw_currency else 0.50,
            evidence=(
                "opengraph:product:price:currency|og:price:currency"
                if raw_currency
                else "default:EUR"
            ),
        )
    if image_url:
        field_evidence["image_url"] = _fact(
            image_url,
            page_url=page_url,
            confidence=0.88,
            evidence="opengraph:og:image",
        )

    return MarketEntity(
        title=title,
        entity_type="product",
        source_url=page_url,
        source_domain=(urlparse(page_url).hostname or "").lower(),
        description=description,
        price=price,
        currency=currency,
        image_url=image_url,
        extraction_method="opengraph",
        evidence=clean_text(f"{title}. {description}", 800),
        field_evidence=field_evidence,
    )
