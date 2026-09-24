from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.projects import ResearchProject
from spriditis.search.query import build_search_queries


project = ResearchProject.model_validate({
    "id": "adaptive_query_priority",
    "name": "Adaptive query priority",
    "keywords": [
        "ergonomic chair",
        "lumbar support",
        "mesh chair",
    ],
    "seed_urls": [],
    "search": {
        "provider": "none",
        "max_queries": 4,
        "queries": ["custom chair market"],
    },
})

memory = [
    {
        "provider": "fake",
        "query_text": "custom chair market",
        "productive_domain_rate": 0.0,
        "productive_domains": 0,
        "unique_domains": 4,
        "runs": 2,
    },
    {
        "provider": "fake",
        "query_text": "ergonomic chair mesh chair",
        "productive_domain_rate": 1.0,
        "productive_domains": 2,
        "unique_domains": 2,
        "runs": 2,
    },
    {
        "provider": "fake",
        "query_text": "ergonomic chair lumbar support",
        "productive_domain_rate": 0.0,
        "productive_domains": 0,
        "unique_domains": 3,
        "runs": 2,
    },
]

queries = build_search_queries(
    project,
    query_memory=memory,
    provider="fake",
)

assert [query.query for query in queries] == [
    "custom chair market",
    "ergonomic chair mesh chair",
    "ergonomic chair lumbar support mesh chair",
    "lumbar support mesh chair",
]

# Explicit user configuration always wins, even with nonproductive history.
assert queries[0].reason == "configured"
assert queries[0].memory_state == "nonproductive"

# Productive historical generated query is promoted ahead of untested queries.
assert queries[1].memory_state == "productive"
assert queries[1].memory_productive_domain_rate == 1.0
assert queries[1].memory_productive_domains == 2
assert queries[1].memory_unique_domains == 2
assert queries[1].memory_runs == 2

# Untested exploration stays ahead of historically nonproductive generated query.
assert queries[2].memory_state == "untested"
assert all(
    query.query != "ergonomic chair lumbar support"
    for query in queries
)

# Provider history is isolated: another provider must not influence ordering.
baseline = build_search_queries(
    project,
    query_memory=memory,
    provider="other-provider",
)
assert [query.query for query in baseline] == [
    "custom chair market",
    "ergonomic chair lumbar support mesh chair",
    "ergonomic chair lumbar support",
    "ergonomic chair mesh chair",
]
assert all(query.memory_state == "untested" for query in baseline)

print("ADAPTIVE QUERY PRIORITY TEST OK")
print("configured > productive memory > untested > nonproductive")
print("productive_query=ergonomic chair mesh chair")
