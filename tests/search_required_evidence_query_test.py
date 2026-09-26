from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(_BootstrapPath(__file__).resolve().parents[1]),
)

from spriditis.core.projects import ResearchProject
from spriditis.search.query import build_search_queries


def project_for(
    *,
    topic: str,
    keywords: list[str],
    required: list[str],
) -> ResearchProject:
    return ResearchProject.model_validate(
        {
            "id": "required_query_test",
            "name": topic,
            "keywords": keywords,
            "seed_urls": [],
            "search": {
                "max_queries": 2,
                "queries": [topic],
            },
            "analysis": {
                "required_evidence_terms": required,
            },
        }
    )


cases = [
    (
        "Opel Zafira 2005 cenas automašīnām ar tehnisko apskati",
        [
            "Opel",
            "Zafira",
            "2005",
            "cenas",
            "automašīnām",
            "tehnisko",
            "apskati",
        ],
        ["2005", "tehnisk", "apskat"],
        ["2005", "tehnisko", "apskati"],
    ),
    (
        "Meklēju galdu ar regulējamu augstumu",
        [
            "Meklēju",
            "galdu",
            "regulējamu",
            "augstumu",
        ],
        ["regulējam", "augstum"],
        ["regulējamu", "augstumu"],
    ),
    (
        "Find headphones with active noise cancellation",
        [
            "Find",
            "headphones",
            "with",
            "active",
            "noise",
            "cancellation",
        ],
        ["activ", "noise", "cancellation"],
        ["active", "noise", "cancellation"],
    ),
]


for topic, keywords, required, expected_words in cases:
    project = project_for(
        topic=topic,
        keywords=keywords,
        required=required,
    )

    queries = build_search_queries(project)

    assert len(queries) == 2, queries
    assert queries[0].query == topic
    assert queries[1].reason == "required_evidence_bundle"

    generated = queries[1].query.casefold()

    for word in expected_words:
        assert word.casefold() in generated, (
            topic,
            generated,
            word,
        )

    print()
    print("TOPIC:", topic)
    print("Q1:", queries[0].query)
    print("Q2:", queries[1].query)


print()
print("SEARCH REQUIRED EVIDENCE QUERY TEST OK")
