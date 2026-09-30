from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(_BootstrapPath(__file__).resolve().parents[1]),
)

from spriditis.core.projects import ResearchProject
from spriditis.search.query import build_search_queries


def words(value: str) -> set[str]:
    cleaned = value.casefold()

    for character in ".,;:!?()[]{}\"'":
        cleaned = cleaned.replace(
            character,
            " ",
        )

    return set(cleaned.split())


cases = [
    {
        "id": "broad_recovery_opel",
        "name": (
            "Opel Zafira 2005 cenas automašīnām "
            "ar tehnisko apskati"
        ),
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": [
            "Opel",
            "Zafira",
            "2005",
            "cenas",
            "automašīnām",
            "tehnisko",
            "apskati",
        ],
        "required": [
            "2005",
            "tehnisk",
            "apskat",
        ],
        "required_surface": {
            "2005",
            "tehnisko",
            "apskati",
        },
        "fillers": {
            "cenas",
            "ar",
        },
        "subject": {
            "opel",
            "zafira",
        },
    },
    {
        "id": "broad_recovery_desk",
        "name": (
            "Meklēju galdu ar regulējamu augstumu"
        ),
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": [
            "Meklēju",
            "galdu",
            "regulējamu",
            "augstumu",
        ],
        "required": [
            "regulējam",
            "augstum",
        ],
        "required_surface": {
            "regulējamu",
            "augstumu",
        },
        "fillers": {
            "meklēju",
            "ar",
        },
        "subject": {
            "galdu",
        },
    },
    {
        "id": "broad_recovery_headphones",
        "name": (
            "Find headphones with active "
            "noise cancellation"
        ),
        "languages": ["en"],
        "countries": ["US"],
        "keywords": [
            "Find",
            "headphones",
            "with",
            "active",
            "noise",
            "cancellation",
        ],
        "required": [
            "activ",
            "noise",
            "cancellation",
        ],
        "required_surface": {
            "active",
            "noise",
            "cancellation",
        },
        "fillers": {
            "find",
            "with",
        },
        "subject": {
            "headphones",
        },
    },
]


for case in cases:
    project = ResearchProject.model_validate(
        {
            "id": case["id"],
            "name": case["name"],
            "languages": case["languages"],
            "countries": case["countries"],
            "keywords": case["keywords"],
            "search": {
                "max_queries": 4,
                "max_recovery_queries": 2,
                "queries": [
                    case["name"],
                ],
            },
            "analysis": {
                "required_evidence_terms":
                    case["required"],
            },
        }
    )

    initial = build_search_queries(
        project
    )

    recovery = build_search_queries(
        project,
        recovery=True,
        exclude_queries={
            item.query
            for item in initial
        },
    )

    assert recovery, case["id"]
    assert len(recovery) <= 2

    initial_keys = {
        item.query.casefold()
        for item in initial
    }

    assert all(
        item.query.casefold()
        not in initial_keys
        for item in recovery
    )

    # Explicit configured user text stays untouched.
    # Generated queries must remove instruction/filler wording.
    for item in initial:
        if item.reason == "configured":
            continue

        assert not (
            words(item.query)
            & case["fillers"]
        ), (
            case["id"],
            item.query,
        )

    # Every constrained broad recovery query must preserve:
    #   - the subject;
    #   - every hard-constraint surface term;
    #   - no instruction/filler words.
    for item in recovery:
        query_words = words(
            item.query
        )

        assert item.reason.startswith(
            "recovery_"
        ), (
            case["id"],
            item.reason,
        )

        assert not (
            query_words
            & case["fillers"]
        ), (
            case["id"],
            item.query,
        )

        assert (
            query_words
            & case["subject"]
        ), (
            case["id"],
            item.query,
        )

        assert (
            case["required_surface"]
            <= query_words
        ), (
            case["id"],
            item.query,
            case["required_surface"],
        )


# --------------------------------------------------
# Pure-keyword broad research has no hard constraints.
# It still needs bounded distinct recovery.
# --------------------------------------------------

chair = ResearchProject.model_validate(
    {
        "id": "broad_recovery_chair",
        "name": "Ergonomic chair market",
        "languages": ["en"],
        "countries": ["US"],
        "keywords": [
            "ergonomic chair",
            "lumbar support",
            "mesh chair",
        ],
        "search": {
            "max_queries": 4,
            "max_recovery_queries": 2,
            "queries": [],
        },
    }
)

chair_initial = build_search_queries(
    chair
)

chair_recovery = build_search_queries(
    chair,
    recovery=True,
    exclude_queries={
        item.query
        for item in chair_initial
    },
)

assert chair_recovery
assert len(chair_recovery) <= 2

assert all(
    item.reason.startswith(
        "recovery_"
    )
    for item in chair_recovery
)

assert all(
    item.query.casefold()
    not in {
        initial.query.casefold()
        for initial in chair_initial
    }
    for item in chair_recovery
)


print(
    "SEARCH BROAD RECOVERY QUERY TEST OK"
)
print(
    "broad_recovery=nonempty"
)
print(
    "filler_terms=removed_from_generated_queries"
)
print(
    "hard_constraints=preserved_in_recovery"
)
print(
    "specific_target=protected_by_existing_regression"
)
