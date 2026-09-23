from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spriditis.core.entities import MarketEntity

from .common import clean_text, meta, parse_price


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

    currency = (
        meta(soup, prop="product:price:currency")
        or meta(soup, prop="og:price:currency")
        or "EUR"
    ).upper()

    description = (
        meta(soup, prop="og:description")
        or meta(soup, name="description")
    )
    image = meta(soup, prop="og:image")

    return MarketEntity(
        title=title,
        entity_type="product",
        source_url=page_url,
        source_domain=(urlparse(page_url).hostname or "").lower(),
        description=description,
        price=parse_price(amount),
        currency=currency,
        image_url=urljoin(page_url, image) if image else "",
        extraction_method="opengraph",
        evidence=clean_text(f"{title}. {description}", 800),
    )
