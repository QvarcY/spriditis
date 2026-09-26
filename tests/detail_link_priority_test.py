from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(_BootstrapPath(__file__).resolve().parents[1]),
)

from bs4 import BeautifulSoup

from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import _link_relevance_context
from spriditis.crawler.policy import text_relevance_score


project = ResearchProject.model_validate(
    {
        "id": "detail-priority-test",
        "name": "Detail priority test",
        "keywords": [
            "Opel",
            "Zafira",
            "2005",
            "cenas",
            "automašīnām",
            "tehnisko",
            "apskati",
        ],
        "analysis": {
            "required_evidence_terms": [
                "2005",
                "tehnisk",
                "apskat",
            ],
        },
    }
)


html = """
<table>
  <tr>
    <td>
      <a href="/msg/lv/transport/cars/opel/zafira/example.html">
        Skate līdz 23.02.2027. Labs, kopts auto.
      </a>
    </td>
    <td>2005</td>
    <td>1.9D</td>
    <td>413 tūkst.</td>
    <td>1 500 €</td>
  </tr>
</table>
"""

soup = BeautifulSoup(html, "html.parser")
tag = soup.find("a")

assert tag is not None

context = _link_relevance_context(tag)

print("ROW CONTEXT:", context)

assert "2005" in context
assert "1 500" in context
assert "Skate līdz" in context


detail_url = (
    "https://example.lv/msg/lv/transport/"
    "cars/opel/zafira/example.html"
)

category_url = (
    "https://example.lv/lv/transport/"
    "cars/opel/zafira/search"
)

detail_score = text_relevance_score(
    project,
    detail_url,
    context,
)

category_score = text_relevance_score(
    project,
    category_url,
    "Opel Zafira",
)

explicit_constraint_score = text_relevance_score(
    project,
    detail_url,
    (
        "Opel Zafira 2005 "
        "ar svaigu tehnisko apskati "
        "1 500 EUR"
    ),
)

print("DETAIL SCORE:", detail_score)
print("CATEGORY SCORE:", category_score)
print(
    "EXPLICIT CONSTRAINT SCORE:",
    explicit_constraint_score,
)

assert detail_score > category_score
assert explicit_constraint_score >= detail_score

# Outside a table the behaviour stays simple and predictable.
plain = BeautifulSoup(
    '<a href="/about">Par mums</a>',
    "html.parser",
).find("a")

assert plain is not None
assert _link_relevance_context(plain) == "Par mums"

print("DETAIL LINK PRIORITY TEST OK")
