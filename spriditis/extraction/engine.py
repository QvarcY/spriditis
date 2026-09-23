from __future__ import annotations

from bs4 import BeautifulSoup

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.sources import meistardarbs

from .jsonld import extract_jsonld_products
from .opengraph import extract_opengraph_product


def _richness(entity: MarketEntity) -> int:
    return (
        (2 if entity.price is not None else 0)
        + (1 if entity.seller else 0)
        + (2 if entity.description else 0)
        + (1 if entity.image_url else 0)
        + (2 if entity.extraction_method == "json-ld" else 0)
    )


def _merge(a: MarketEntity, b: MarketEntity) -> MarketEntity:
    primary, secondary = (a, b) if _richness(a) >= _richness(b) else (b, a)
    data = primary.model_dump()

    for field in (
        "seller",
        "description",
        "image_url",
        "evidence",
        "source_domain",
    ):
        if not data.get(field) and getattr(secondary, field):
            data[field] = getattr(secondary, field)

    if data.get("price") is None and secondary.price is not None:
        data["price"] = secondary.price

    return MarketEntity(**data)


def extract_entities(
    html: str,
    page_url: str,
    project: ResearchProject,
) -> list[MarketEntity]:
    if project.entity_type != "product":
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[MarketEntity] = []

    candidates.extend(extract_jsonld_products(soup, page_url))

    if meistardarbs.matches(page_url):
        special = meistardarbs.extract_product(soup, page_url)
        if special:
            candidates.append(special)

    og = extract_opengraph_product(soup, page_url)
    if og:
        candidates.append(og)

    by_title: dict[str, MarketEntity] = {}
    for entity in candidates:
        key = entity.normalized_title
        if key in by_title:
            by_title[key] = _merge(by_title[key], entity)
        else:
            by_title[key] = entity

    return list(by_title.values())
