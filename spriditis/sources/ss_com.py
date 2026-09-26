from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from spriditis.core.entities import ExtractionEvidence, MarketEntity
from spriditis.extraction.common import (
    clean_text,
    meta,
    parse_explicit_money,
    parse_price,
)


_LABEL_ALIASES = {
    "marka": "make_model",
    "izlaiduma gads": "year",
    "motors": "engine",
    "ātrumkārba": "transmission",
    "nobraukums, km": "mileage_km",
    "krāsa": "color",
    "virsbūves tips": "body_type",
    "vietu skaits": "seats",
    "tehniskā apskate": "inspection_until",
    "cena": "price",
    "vieta": "location",
}


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
        extraction_method="ss.com-html",
        confidence=confidence,
        evidence=evidence,
    )


def matches(page_url: str) -> bool:
    parsed = urlparse(page_url)
    host = (parsed.hostname or "").lower()
    return (
        host == "ss.com"
        or host.endswith(".ss.com")
    ) and "/msg/" in (parsed.path or "")


def _normalize_label(value: str) -> str:
    return clean_text(value, 120).strip().rstrip(":").casefold()


def _row_fields(soup: BeautifulSoup) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}

    for row in soup.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [
            cell
            for cell in row.find_all(["td", "th"], recursive=False)
            if isinstance(cell, Tag)
        ]
        if len(cells) < 2:
            continue

        label = _normalize_label(cells[0].get_text(" ", strip=True))
        if label not in _LABEL_ALIASES:
            continue

        value = clean_text(
            " ".join(
                cell.get_text(" ", strip=True)
                for cell in cells[1:]
            ),
            1200,
        )
        if value:
            result[_LABEL_ALIASES[label]] = (
                value,
                f"table:{label}",
            )

    if result:
        return result

    # Mobile/alternate markup fallback: scan compact label/value blocks.
    text = clean_text(soup.get_text(" ", strip=True), 30000)
    labels = sorted(_LABEL_ALIASES, key=len, reverse=True)
    for index, label in enumerate(labels):
        pattern = re.compile(
            rf"(?i)(?:^|\s){re.escape(label)}\s*:\s*(.+?)"
            rf"(?=(?:\s+(?:{'|'.join(re.escape(x) for x in labels)})\s*:)|$)"
        )
        match = pattern.search(text)
        if match:
            result[_LABEL_ALIASES[label]] = (
                clean_text(match.group(1), 1200),
                f"text:{label}",
            )

    return result


def _description(soup: BeautifulSoup) -> str:
    return (
        meta(soup, prop="og:description")
        or meta(soup, name="description")
    )


def _title(
    soup: BeautifulSoup,
    fields: dict[str, tuple[str, str]],
) -> str:
    make_model = fields.get("make_model", ("", ""))[0]
    year = fields.get("year", ("", ""))[0]

    if make_model:
        year_match = re.search(r"\b(?:19|20)\d{2}\b", year)
        if year_match and year_match.group(0) not in make_model:
            return clean_text(
                f"{make_model}, {year_match.group(0)}",
                300,
            )
        return clean_text(make_model, 300)

    og_title = meta(soup, prop="og:title")
    if og_title:
        return clean_text(
            re.sub(r"^SS\.COM\s*", "", og_title, flags=re.IGNORECASE),
            300,
        )

    title_tag = soup.find("title")
    if title_tag:
        return clean_text(
            re.sub(
                r"^SS\.COM\s*",
                "",
                title_tag.get_text(" ", strip=True),
                flags=re.IGNORECASE,
            ),
            300,
        )

    return ""


def extract_product(
    soup: BeautifulSoup,
    page_url: str,
) -> MarketEntity | None:
    if not matches(page_url):
        return None

    fields = _row_fields(soup)
    title = _title(soup, fields)
    if not title:
        return None

    description = _description(soup)

    price_text = fields.get("price", ("", ""))[0]
    price, currency = parse_explicit_money(price_text)
    price_evidence = fields.get("price", ("", ""))[1]

    if price is None:
        price, currency = parse_explicit_money(
            f"{meta(soup, prop='og:title')} {description}"
        )
        if price is not None:
            price_evidence = "opengraph:title|description:explicit_money"

    attributes: dict[str, object] = {}
    attribute_evidence: dict[str, str] = {}

    for key in (
        "make_model",
        "year",
        "engine",
        "transmission",
        "mileage_km",
        "color",
        "body_type",
        "seats",
        "inspection_until",
        "location",
    ):
        value, evidence = fields.get(key, ("", ""))
        if not value:
            continue

        if key == "mileage_km":
            digits = re.sub(r"\D", "", value)
            attributes[key] = int(digits) if digits else value
        elif key == "seats":
            match = re.search(r"\d+", value)
            attributes[key] = int(match.group(0)) if match else value
        else:
            attributes[key] = value

        attribute_evidence[key] = evidence

    image = meta(soup, prop="og:image")
    image_url = urljoin(page_url, image) if image else ""

    field_evidence: dict[str, ExtractionEvidence] = {
        "title": _fact(
            title,
            page_url=page_url,
            confidence=0.92,
            evidence="ss.com:listing_fields|title",
        ),
        "source_url": _fact(
            page_url,
            page_url=page_url,
            confidence=0.99,
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
            confidence=0.94 if price_text else 0.74,
            evidence=price_evidence or "explicit_money",
        )
        field_evidence["currency"] = _fact(
            currency or "EUR",
            page_url=page_url,
            confidence=0.94 if price_text else 0.74,
            evidence=price_evidence or "explicit_money",
        )

    if image_url:
        field_evidence["image_url"] = _fact(
            image_url,
            page_url=page_url,
            confidence=0.88,
            evidence="opengraph:og:image",
        )

    for key, value in attributes.items():
        field_evidence[f"attributes.{key}"] = _fact(
            value,
            page_url=page_url,
            confidence=0.90,
            evidence=f"ss.com:{attribute_evidence[key]}",
        )

    return MarketEntity(
        title=title,
        entity_type="product",
        source_url=page_url,
        source_domain=(urlparse(page_url).hostname or "").lower(),
        description=description,
        price=price,
        currency=currency or "EUR",
        image_url=image_url,
        extraction_method="ss.com-html",
        evidence=clean_text(
            " ".join(
                [
                    title,
                    description,
                    " ".join(str(value) for value in attributes.values()),
                ]
            ),
            1200,
        ),
        attributes=attributes,
        field_evidence=field_evidence,
    )
