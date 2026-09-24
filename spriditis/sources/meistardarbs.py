from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from spriditis.core.entities import ExtractionEvidence, MarketEntity
from spriditis.extraction.common import PRICE_RE, clean_text, meta, parse_price


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
        extraction_method="meistardarbs-html",
        confidence=confidence,
        evidence=evidence,
    )


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
    price_currency = ""
    title_pos = page_text.find(title)
    scan = page_text[title_pos:title_pos + 1600] if title_pos >= 0 else page_text[:1600]
    match = PRICE_RE.search(scan)
    if match:
        price = parse_price(match.group(1))
        price_currency = "EUR"

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

    image_url = urljoin(page_url, image) if image else ""

    field_evidence: dict[str, ExtractionEvidence] = {
        "title": _fact(
            title,
            page_url=page_url,
            confidence=0.86,
            evidence="meistardarbs:h1",
        ),
        "source_url": _fact(
            page_url,
            page_url=page_url,
            confidence=0.90,
            evidence="page_url",
        ),
    }

    if description:
        field_evidence["description"] = _fact(
            description,
            page_url=page_url,
            confidence=0.82,
            evidence="meistardarbs:Preces apraksts",
        )
    if price is not None:
        field_evidence["price"] = _fact(
            price,
            page_url=page_url,
            confidence=0.84,
            evidence="meistardarbs:visible_price",
        )
    if price_currency:
        field_evidence["currency"] = _fact(
            price_currency,
            page_url=page_url,
            confidence=0.84,
            evidence="meistardarbs:visible_price_currency",
        )
    if seller:
        field_evidence["seller"] = _fact(
            seller,
            page_url=page_url,
            confidence=0.78,
            evidence="meistardarbs:Informācija par pārdevēju",
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
        currency="EUR",
        seller=seller,
        image_url=image_url,
        extraction_method="meistardarbs-html",
        evidence=clean_text(f"{title}. {description}", 800),
        field_evidence=field_evidence,
    )
