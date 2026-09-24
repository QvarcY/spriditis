from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import ResearchProject
from spriditis.search.query import build_search_queries

project = ResearchProject.model_validate({
    "id": "query_test",
    "name": "Query test",
    "keywords": ["ergonomic chair", "lumbar support", "mesh chair"],
    "seed_urls": [],
    "search": {"max_queries": 3, "queries": ["custom chair market"]},
})
queries = build_search_queries(project)
assert [q.query for q in queries] == [
    "custom chair market",
    "ergonomic chair lumbar support mesh chair",
    "ergonomic chair lumbar support",
]
assert len({q.query.casefold() for q in queries}) == len(queries)
print("SEARCH QUERY TEST OK")
