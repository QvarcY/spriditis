from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from spriditis.core.entities import MarketEntity
from spriditis.extraction.jsonld import extract_jsonld_products
from spriditis.resolution.identity import (
    normalize_gtin,
    resolve_entities,
)


def entity(
    *,
    title: str,
    domain: str,
    attributes: dict[str, str],
) -> MarketEntity:
    return MarketEntity(
        title=title,
        source_url=f"https://{domain}/product/item",
        source_domain=domain,
        attributes=attributes,
    )


assert normalize_gtin("4006 381333931") == "4006381333931"
assert normalize_gtin("036000291452") == "036000291452"
assert normalize_gtin("4006381333932") == ""

html_a = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Acme Ergonomic Chair X1",
  "url": "/products/x1",
  "brand": {"@type": "Brand", "name": "Acme"},
  "manufacturer": {"@type": "Organization", "name": "Acme Industries"},
  "model": "X1",
  "mpn": "AC-X1",
  "sku": "STORE-A-123",
  "gtin13": "4006381333931",
  "offers": {
    "@type": "Offer",
    "price": "199.00",
    "priceCurrency": "EUR"
  }
}
</script>
</head><body></body></html>
"""

html_b = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Ergonomic Office Chair X1 by Acme",
  "url": "/catalog/acme-x1",
  "brand": "Acme",
  "model": "X1",
  "sku": "OTHER-999",
  "gtin": "4006381333931",
  "offers": {
    "@type": "Offer",
    "price": "205.00",
    "priceCurrency": "EUR"
  }
}
</script>
</head><body></body></html>
"""

left = extract_jsonld_products(
    BeautifulSoup(html_a, "html.parser"),
    "https://shop-a.example/catalog",
)[0]
right = extract_jsonld_products(
    BeautifulSoup(html_b, "html.parser"),
    "https://shop-b.example/catalog",
)[0]

assert left.attributes == {
    "brand": "Acme",
    "manufacturer": "Acme Industries",
    "model": "X1",
    "mpn": "AC-X1",
    "sku": "STORE-A-123",
    "gtin": "4006381333931",
}
assert right.attributes["brand"] == "Acme"
assert right.attributes["model"] == "X1"
assert right.attributes["gtin"] == "4006381333931"

decision = resolve_entities(left, right)
assert decision.outcome == "match"
assert decision.reason == "gtin_exact"
assert decision.matched_signals == ("gtin_exact",)

gtin_conflict = resolve_entities(
    entity(
        title="Same title",
        domain="one.example",
        attributes={"gtin": "4006381333931"},
    ),
    entity(
        title="Same title",
        domain="two.example",
        attributes={"gtin": "036000291452"},
    ),
)
assert gtin_conflict.outcome == "conflict"
assert gtin_conflict.reason == "gtin_conflict"

maker_model = resolve_entities(
    entity(
        title="Chair X1 black",
        domain="one.example",
        attributes={"brand": "Acme", "model": "X-1"},
    ),
    entity(
        title="Acme office chair model X1",
        domain="two.example",
        attributes={"manufacturer": "ACME", "model": "X1"},
    ),
)
assert maker_model.outcome == "match"
assert maker_model.reason == "maker_model_exact"

maker_mpn = resolve_entities(
    entity(
        title="Acme chair",
        domain="one.example",
        attributes={"brand": "Acme", "mpn": "AC-X1"},
    ),
    entity(
        title="Office chair",
        domain="two.example",
        attributes={"manufacturer": "Acme", "mpn": "ACX1"},
    ),
)
assert maker_mpn.outcome == "match"
assert maker_mpn.reason == "maker_mpn_exact"

cross_source_sku = resolve_entities(
    entity(
        title="Chair X1",
        domain="one.example",
        attributes={"sku": "SKU-100"},
    ),
    entity(
        title="Chair X1",
        domain="two.example",
        attributes={"sku": "SKU-100"},
    ),
)
assert cross_source_sku.outcome == "insufficient"
assert cross_source_sku.reason == "supporting_signals_only"
assert "sku_cross_source_only" in cross_source_sku.supporting_signals
assert "title_exact" in cross_source_sku.supporting_signals

same_source_sku = resolve_entities(
    entity(
        title="Chair X1",
        domain="one.example",
        attributes={"sku": "SKU-100"},
    ),
    entity(
        title="Chair X1 updated",
        domain="one.example",
        attributes={"sku": "SKU100"},
    ),
)
assert same_source_sku.outcome == "match"
assert same_source_sku.reason == "source_sku_exact"

title_only = resolve_entities(
    entity(
        title="Universal Ergonomic Chair",
        domain="one.example",
        attributes={},
    ),
    entity(
        title="Universal   Ergonomic Chair",
        domain="two.example",
        attributes={},
    ),
)
assert title_only.outcome == "insufficient"
assert title_only.reason == "supporting_signals_only"
assert title_only.supporting_signals == ("title_exact",)

invalid_gtin_falls_back = resolve_entities(
    entity(
        title="Acme X2",
        domain="one.example",
        attributes={
            "gtin": "4006381333932",
            "brand": "Acme",
            "model": "X2",
        },
    ),
    entity(
        title="Acme model X2",
        domain="two.example",
        attributes={
            "brand": "Acme",
            "model": "X-2",
        },
    ),
)
assert invalid_gtin_falls_back.outcome == "match"
assert invalid_gtin_falls_back.reason == "maker_model_exact"

print("ENTITY IDENTITY RESOLUTION TEST OK")
print(
    "priority=gtin_exact > maker_model_exact > "
    "maker_mpn_exact > source_sku_exact"
)
print("cross_source_sku=insufficient")
print("title_only=insufficient")
