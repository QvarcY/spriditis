from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(_BootstrapPath(__file__).resolve().parents[1]),
)

from bs4 import BeautifulSoup

from spriditis.sources import ss_com


assert ss_com.matches(
    "https://www.ss.com/msg/lv/transport/cars/opel/zafira/example.html"
)

assert ss_com.matches(
    "https://www.ss.lv/msg/lv/transport/cars/opel/zafira/example.html"
)

assert ss_com.matches(
    "https://www.ss.lv/msg/ru/transport/cars/opel/zafira/example.html"
)

assert not ss_com.matches(
    "https://www.ss.lv/lv/archive/transport/cars/opel/zafira/sell/page6.html"
)

assert not ss_com.matches(
    "https://example.com/msg/lv/transport/cars/opel/zafira/example.html"
)


html = """
<html>
<head>
<meta property="og:description"
      content="Praktisks auto. TA līdz 01.06.2027.">
</head>
<body>
<table>
<tr><td>Marka</td><td>Opel Zafira</td></tr>
<tr><td>Izlaiduma gads:</td><td>2005 decembris</td></tr>
<tr><td>Motors:</td><td>1.9 dīzelis</td></tr>
<tr><td>Tehniskā apskate:</td><td>06.2027</td></tr>
<tr><td>Cena:</td><td>1 500 €</td></tr>
<tr><td>Vieta:</td><td>Valmiera un raj.</td></tr>
</table>
</body>
</html>
"""

url = (
    "https://www.ss.lv/msg/lv/transport/"
    "cars/opel/zafira/example.html"
)

entity = ss_com.extract_product(
    BeautifulSoup(html, "html.parser"),
    url,
)

assert entity is not None
assert entity.title == "Opel Zafira, 2005"
assert entity.price == 1500.0
assert entity.currency == "EUR"
assert entity.attributes["year"] == "2005 decembris"
assert entity.attributes["inspection_until"] == "06.2027"
assert entity.attributes["location"] == "Valmiera un raj."
assert entity.source_domain == "www.ss.lv"
assert entity.extraction_method == "ss.com-html"

print("SS.LV SOURCE REGRESSION TEST OK")
