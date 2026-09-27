from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import ResearchProject
from spriditis.search.query import build_search_queries


project = ResearchProject.model_validate(
    {
        "id": "target_identity_query_test",
        "name": "Bambu Lab P1S Combo",
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": [
            "Atrodi",
            "Latvijas",
            "veikalos",
            "Bambu",
            "Lab",
            "P1S",
            "Combo",
            "piedāvājumus",
        ],
        "search": {
            "max_queries": 4,
            "queries": [
                (
                    "Atrodi Latvijas veikalos Bambu Lab P1S Combo "
                    "piedāvājumus un salīdzini cenas."
                )
            ],
        },
        "analysis": {
            "target_identity_terms": ["P1S", "Combo"],
            "target_identity_anchor_terms": ["P1S"],
        },
    }
)

queries = build_search_queries(project)

assert queries[0].reason == "configured"
assert queries[1].query == "Bambu Lab P1S Combo Latvija"
assert queries[1].reason == "target_identity_locale"
assert queries[2].query == "Bambu Lab P1S Combo cena"
assert queries[3].query == "Bambu Lab P1S Combo veikals Latvija"
assert all(
    "P1S" in query.query and "Combo" in query.query
    for query in queries[1:]
)
assert "Atrodi Latvijas veikalos" not in {
    query.query for query in queries[1:]
}

recovery = build_search_queries(
    project, recovery=True, exclude_queries={item.query for item in queries[:2]},
)
assert all(item.query not in {q.query for q in queries[:2]} for item in recovery)
assert all("P1S" in item.query and "Combo" in item.query for item in recovery)
assert len(recovery) <= project.search.max_recovery_queries

constrained = project.model_copy(deep=True)
constrained.analysis.required_evidence_terms = ["warranty"]
assert "warranty" in build_search_queries(constrained)[1].query

for terms, anchors, keywords, country in [
    (["16", "Pro"], ["16"], ["Compare", "iPhone", "16", "Pro"], "DE"),
    (["7800X3D"], ["7800X3D"], ["Find", "AMD", "Ryzen", "7", "7800X3D"], "US"),
    (["2005"], ["2005"], ["Find", "Opel", "Zafira", "2005"], "EE"),
]:
    other = project.model_copy(deep=True)
    other.analysis.target_identity_terms = terms
    other.analysis.target_identity_anchor_terms = anchors
    other.keywords = keywords
    other.languages = ["en"]
    other.countries = [country]
    other.search.queries = []
    generated = build_search_queries(other)
    assert all(all(term in query.query for term in terms) for query in generated)
    assert country in generated[0].query
    assert all("Bambu" not in query.query and "Latvija" not in query.query for query in generated)


broad = project.model_copy(
    update={
        "analysis": project.analysis.model_copy(
            update={
                "target_identity_terms": [],
                "target_identity_anchor_terms": [],
            }
        )
    }
)

broad_queries = build_search_queries(broad)
assert all(
    not query.reason.startswith("target_identity")
    for query in broad_queries
)

print("SEARCH TARGET IDENTITY QUERY TEST OK")
