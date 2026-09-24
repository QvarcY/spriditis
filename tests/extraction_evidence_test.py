from __future__ import annotations

import json
import sys
from pathlib import Path as _BootstrapPath

from bs4 import BeautifulSoup

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import ResearchProject
from spriditis.extraction.engine import extract_entities
from spriditis.extraction.jsonld import extract_jsonld_products
from spriditis.extraction.opengraph import extract_opengraph_product


page_url = "https://shop.example/product/acme-x1"

jsonld_html = """
<html>
<head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Acme Chair X1",
  "description": "Ergonomic chair",
  "brand": {"@type": "Brand", "name": "Acme"},
  "model": "X1",
  "gtin13": "4006381333931",
  "offers": {
    "@type": "Offer",
    "price": "199.00",
    "priceCurrency": "USD",
    "url": "/product/acme-x1"
  }
}
</script>
</head>
</html>
"""

jsonld = extract_jsonld_products(
    BeautifulSoup(jsonld_html, "html.parser"),
    page_url,
)
assert len(jsonld) == 1
entity = jsonld[0]

assert entity.confidence == 0.0
assert entity.field_evidence["title"].value == "Acme Chair X1"
assert entity.field_evidence["title"].extraction_method == "json-ld"
assert entity.field_evidence["title"].confidence == 0.98
assert entity.field_evidence["price"].value == 199.0
assert entity.field_evidence["price"].confidence == 0.98
assert entity.field_evidence["currency"].value == "USD"
assert entity.field_evidence["currency"].confidence == 0.98
assert entity.field_evidence["attributes.gtin"].value == "4006381333931"
assert entity.field_evidence["attributes.brand"].value == "Acme"
assert entity.field_evidence["attributes.model"].value == "X1"
assert entity.field_evidence["attributes.gtin"].source_url == page_url

serialized = json.loads(entity.as_json())
assert serialized["field_evidence"]["price"]["value"] == 199.0
assert serialized["field_evidence"]["price"]["confidence"] == 0.98

jsonld_default_currency_html = """
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "No Currency Product",
  "offers": {"price": "10.00"}
}
</script>
"""
default_currency = extract_jsonld_products(
    BeautifulSoup(jsonld_default_currency_html, "html.parser"),
    page_url,
)[0]
assert default_currency.currency == "EUR"
assert default_currency.field_evidence["currency"].value == "EUR"
assert default_currency.field_evidence["currency"].confidence == 0.55
assert default_currency.field_evidence["currency"].evidence == "default:EUR"

og_html = """
<html>
<head>
<meta property="og:type" content="product">
<meta property="og:title" content="OpenGraph Chair">
<meta property="og:description" content="OG description">
<meta property="product:price:amount" content="149.50">
<meta property="og:image" content="/images/chair.jpg">
</head>
</html>
"""
og = extract_opengraph_product(
    BeautifulSoup(og_html, "html.parser"),
    page_url,
)
assert og is not None
assert og.confidence == 0.0
assert og.field_evidence["title"].confidence == 0.88
assert og.field_evidence["price"].value == 149.5
assert og.field_evidence["price"].confidence == 0.88
assert og.field_evidence["currency"].value == "EUR"
assert og.field_evidence["currency"].confidence == 0.50
assert og.field_evidence["currency"].evidence == "default:EUR"

project = ResearchProject.model_validate({
    "id": "extraction_evidence",
    "name": "Extraction evidence",
    "keywords": ["chair"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none"
    }
})

merged_html = """
<html>
<head>
<meta property="og:type" content="product">
<meta property="og:title" content="Acme Chair X1">
<meta property="og:description" content="Description from OpenGraph">
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Acme Chair X1",
  "offers": {
    "price": "199.00",
    "priceCurrency": "EUR"
  }
}
</script>
</head>
</html>
"""

merged = extract_entities(merged_html, page_url, project)
assert len(merged) == 1
merged_entity = merged[0]
assert merged_entity.extraction_method == "json-ld"
assert merged_entity.price == 199.0
assert merged_entity.description == "Description from OpenGraph"
assert merged_entity.field_evidence["price"].extraction_method == "json-ld"
assert (
    merged_entity.field_evidence["description"].extraction_method
    == "opengraph"
)
assert merged_entity.field_evidence["description"].confidence == 0.88

print("EXTRACTION EVIDENCE TEST OK")
print("entity_confidence_separate_from_extraction_confidence")
print("jsonld_direct=0.98 opengraph_direct=0.88")
print("default_currency=jsonld:0.55 opengraph:0.50")
print("merge_preserves_fallback_field_provenance")
