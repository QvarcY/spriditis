from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

from bs4 import BeautifulSoup

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import ResearchProject
from spriditis.extraction.dom_fallback import extract_dom_fallback_product
from spriditis.extraction.engine import extract_entities


product_url = "https://shop.example/product/acme-chair-x2"

valid_html = """
<html>
<body>
<main class="product-detail">
  <h1>Acme Chair X2</h1>
  <div class="product-price">129.99 EUR</div>
  <div class="product-description">
    Ergonomic office chair with adjustable lumbar support.
  </div>
  <button>Add to cart</button>
</main>
</body>
</html>
"""

entity = extract_dom_fallback_product(
    BeautifulSoup(valid_html, "html.parser"),
    product_url,
)
assert entity is not None
assert entity.title == "Acme Chair X2"
assert entity.price == 129.99
assert entity.currency == "EUR"
assert entity.description == (
    "Ergonomic office chair with adjustable lumbar support."
)
assert entity.extraction_method == "dom-fallback"
assert entity.confidence == 0.0
assert entity.field_evidence["title"].confidence == 0.72
assert entity.field_evidence["price"].confidence == 0.68
assert entity.field_evidence["currency"].confidence == 0.68
assert entity.field_evidence["description"].confidence == 0.62
assert (
    "explicit_currency"
    in entity.field_evidence["price"].evidence
)

prefix_html = """
<html>
<body>
<section class="product">
  <h1>Acme Desk Lamp</h1>
  <span class="price">GBP 79.90</span>
  <button>Buy now</button>
</section>
</body>
</html>
"""
prefix = extract_dom_fallback_product(
    BeautifulSoup(prefix_html, "html.parser"),
    "https://shop.example/item/acme-desk-lamp",
)
assert prefix is not None
assert prefix.price == 79.90
assert prefix.currency == "GBP"

no_currency_html = """
<html>
<body>
<div class="product-detail">
  <h1>Acme Chair X3</h1>
  <div class="price">129.99</div>
  <button>Add to cart</button>
</div>
</body>
</html>
"""
assert (
    extract_dom_fallback_product(
        BeautifulSoup(no_currency_html, "html.parser"),
        "https://shop.example/product/acme-chair-x3",
    )
    is None
)

article_html = """
<html>
<body>
<article>
  <h1>Best office chairs under 100 EUR</h1>
  <p>Our favourite chair costs 99 EUR this week.</p>
</article>
</body>
</html>
"""
assert (
    extract_dom_fallback_product(
        BeautifulSoup(article_html, "html.parser"),
        "https://blog.example/best-office-chairs",
    )
    is None
)

pricing_page_html = """
<html>
<body>
<main>
  <h1>Membership plans</h1>
  <div class="price">19 EUR</div>
</main>
</body>
</html>
"""
assert (
    extract_dom_fallback_product(
        BeautifulSoup(pricing_page_html, "html.parser"),
        "https://service.example/pricing",
    )
    is None
)

project = ResearchProject.model_validate({
    "id": "dom_fallback",
    "name": "DOM fallback",
    "keywords": ["chair"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none"
    }
})

fallback_only = extract_entities(
    valid_html,
    product_url,
    project,
)
assert len(fallback_only) == 1
assert fallback_only[0].extraction_method == "dom-fallback"
assert fallback_only[0].price == 129.99

structured_html = """
<html>
<body>
<main class="product-detail">
  <h1>Acme Chair X2</h1>
  <div class="product-price">129.99 EUR</div>
  <button>Add to cart</button>
</main>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "Acme Chair X2",
  "offers": {
    "price": "199.00",
    "priceCurrency": "EUR"
  }
}
</script>
</body>
</html>
"""

structured = extract_entities(
    structured_html,
    product_url,
    project,
)
assert len(structured) == 1
assert structured[0].extraction_method == "json-ld"
assert structured[0].price == 199.0
assert structured[0].field_evidence["price"].confidence == 0.98

print("DOM FALLBACK EXTRACTION TEST OK")
print("fallback_requires=title+semantic_price+explicit_currency+product_hint")
print("dom_confidence=title:0.72 price:0.68 description:0.62")
print("no_currency=rejected")
print("article_and_pricing_false_positives=rejected")
print("structured_extraction_suppresses_dom_fallback")
