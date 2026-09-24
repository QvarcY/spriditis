from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

from bs4 import BeautifulSoup

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import ResearchProject
from spriditis.extraction.engine import extract_entities
from spriditis.extraction.microdata import extract_microdata_products


page_url = "https://shop.example/catalog/acme-x1"

microdata_html = """
<html>
<body>
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Acme Chair X1</span>
  <div itemprop="description">Ergonomic microdata chair</div>
  <link itemprop="url" href="/product/acme-x1">
  <img itemprop="image" src="/images/acme-x1.jpg">
  <div itemprop="brand" itemscope itemtype="https://schema.org/Brand">
    <meta itemprop="name" content="Acme">
  </div>
  <div itemprop="manufacturer" itemscope itemtype="https://schema.org/Organization">
    <span itemprop="name">Acme Manufacturing</span>
  </div>
  <span itemprop="model">X1</span>
  <span itemprop="mpn">ACME-X1</span>
  <span itemprop="sku">SKU-X1</span>
  <span itemprop="gtin13">4006381333931</span>
  <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
    <meta itemprop="price" content="179.90">
    <meta itemprop="priceCurrency" content="USD">
    <link itemprop="url" href="/offer/acme-x1">
    <div itemprop="seller" itemscope itemtype="https://schema.org/Organization">
      <meta itemprop="name" content="Micro Shop">
    </div>
  </div>
</div>
</body>
</html>
"""

entities = extract_microdata_products(
    BeautifulSoup(microdata_html, "html.parser"),
    page_url,
)
assert len(entities) == 1
entity = entities[0]

assert entity.title == "Acme Chair X1"
assert entity.source_url == "https://shop.example/product/acme-x1"
assert entity.source_domain == "shop.example"
assert entity.description == "Ergonomic microdata chair"
assert entity.price == 179.90
assert entity.currency == "USD"
assert entity.seller == "Micro Shop"
assert entity.image_url == "https://shop.example/images/acme-x1.jpg"
assert entity.attributes == {
    "brand": "Acme",
    "manufacturer": "Acme Manufacturing",
    "model": "X1",
    "mpn": "ACME-X1",
    "sku": "SKU-X1",
    "gtin": "4006381333931",
}
assert entity.extraction_method == "microdata"
assert entity.confidence == 0.0

assert entity.field_evidence["title"].confidence == 0.93
assert entity.field_evidence["price"].confidence == 0.93
assert entity.field_evidence["currency"].confidence == 0.93
assert entity.field_evidence["seller"].confidence == 0.90
assert entity.field_evidence["attributes.gtin"].confidence == 0.93
assert (
    entity.field_evidence["attributes.gtin"].evidence
    == "microdata:itemprop=gtin13"
)

default_currency_html = """
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Microdata Product</span>
  <meta itemprop="price" content="12.50">
</div>
"""
default_entity = extract_microdata_products(
    BeautifulSoup(default_currency_html, "html.parser"),
    page_url,
)[0]
assert default_entity.currency == "EUR"
assert default_entity.field_evidence["currency"].confidence == 0.52
assert default_entity.field_evidence["currency"].evidence == "default:EUR"

project = ResearchProject.model_validate({
    "id": "microdata_priority",
    "name": "Microdata priority",
    "keywords": ["chair"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none"
    }
})

priority_html = """
<html>
<head>
<meta property="og:type" content="product">
<meta property="og:title" content="Acme Chair X1">
<meta property="product:price:amount" content="99.00">
<meta property="product:price:currency" content="EUR">
</head>
<body>
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Acme Chair X1</span>
  <meta itemprop="price" content="149.00">
  <meta itemprop="priceCurrency" content="EUR">
</div>
</body>
</html>
"""

merged = extract_entities(priority_html, page_url, project)
assert len(merged) == 1
assert merged[0].extraction_method == "microdata"
assert merged[0].price == 149.0
assert merged[0].field_evidence["price"].extraction_method == "microdata"
assert merged[0].field_evidence["price"].confidence == 0.93

jsonld_priority_html = """
<html>
<head>
<meta property="og:type" content="product">
<meta property="og:title" content="Acme Chair X1">
<meta property="product:price:amount" content="99.00">
</head>
<body>
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Acme Chair X1</span>
  <meta itemprop="price" content="149.00">
</div>
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
</body>
</html>
"""

merged_jsonld = extract_entities(
    jsonld_priority_html,
    page_url,
    project,
)
assert len(merged_jsonld) == 1
assert merged_jsonld[0].extraction_method == "json-ld"
assert merged_jsonld[0].price == 199.0
assert (
    merged_jsonld[0].field_evidence["price"].extraction_method
    == "json-ld"
)

print("MICRODATA EXTRACTION TEST OK")
print("priority=json-ld > microdata > opengraph")
print("microdata_direct=0.93 seller=0.90")
print("microdata_default_currency=0.52")
print("identity_fields=brand+manufacturer+model+mpn+sku+gtin")
print("nested_scopes=brand+manufacturer+seller")
