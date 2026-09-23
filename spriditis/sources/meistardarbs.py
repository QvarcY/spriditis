from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spriditis.core.entities import MarketEntity
from spriditis.extraction.common import PRICE_RE, clean_text, meta, parse_price


def matches(page_url: str) -> bool:
    host = (urlparse(page_url).hostname or "").lower()
    return host == "meistardarbs.lv" or host.endswith(".meistardarbs.lv")


def extract_product(
    soup: BeautifulSoup,
    page_url: str,
) -> MarketEntity | None:
    if not matches(page_url):
        return None

    h1 = soup.find("h1")
    if not h1:
        return None

    page_text = clean_text(soup.get_text(" ", strip=True), 20000)
    if "Preces apraksts:" not in page_text:
        return None

    title = clean_text(h1.get_text(" ", strip=True), 300)
    if not title:
        return None

    price = None
    title_pos = page_text.find(title)
    scan = page_text[title_pos:title_pos + 1600] if title_pos >= 0 else page_text[:1600]
    match = PRICE_RE.search(scan)
    if match:
        price = parse_price(match.group(1))

    seller = ""
    seller_header = soup.find(
        lambda tag: (
            tag.name in {"h3", "h4", "h5", "div", "span", "p"}
            and "Informācija par pārdevēju"
            in clean_text(tag.get_text(" ", strip=True), 300)
        )
    )
    if seller_header:
        for candidate in seller_header.find_all_next(["h5", "h4", "a"], limit=10):
            text = clean_text(candidate.get_text(" ", strip=True), 200)
            if text and text not in {
                "Sūtīt ziņu",
                "Nosūtīt ziņu",
                "Pārdevēja profils",
            }:
                seller = text
                break

    description = ""
    after = page_text.split("Preces apraksts:", 1)[1]
    for marker in (
        "Piegādes nosacījumi:",
        "Apmaksas veidi:",
        "Informācija par pārdevēju",
    ):
        if marker in after:
            after = after.split(marker, 1)[0]
    description = clean_text(after, 2500)

    image = meta(soup, prop="og:image")

    return MarketEntity(
        title=title,
        entity_type="product",
        source_url=page_url,
        source_domain=(urlparse(page_url).hostname or "").lower(),
        description=description,
        price=price,
        currency="EUR",
        seller=seller,
        image_url=urljoin(page_url, image) if image else "",
        extraction_method="meistardarbs-html",
        evidence=clean_text(f"{title}. {description}", 800),
    )
