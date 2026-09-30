from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.crawler.coverage import ResearchCoverage


def product(domain: str, index: int) -> MarketEntity:
    return MarketEntity(
        title=f"Product {index}",
        source_url=f"https://{domain}/product/{index}",
        source_domain=domain,
    )


# --------------------------------------------------
# BROAD EXPEDITION
#
# max_domains is retained/deep-crawl capacity,
# not the total number of productive domains that
# research may discover.
# --------------------------------------------------

project = ResearchProject.model_validate({
    "id": "c2-retention",
    "name": "C2 retention",
    "keywords": ["product"],
    "crawl": {
        "mode": "expedition",
        "max_domains": 2,
        "max_probe_domains": 5,
        "max_probe_pages_total": 10,
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})

coverage = ResearchCoverage.for_project(project)

assert coverage.source_goal == 2
assert coverage.productive_domains == set()
assert coverage.retained_domains == set()

coverage.observe_entities(
    "one.example",
    [product("one.example", 1)],
)

coverage.observe_entities(
    "two.example",
    [product("two.example", 2)],
)

coverage.observe_entities(
    "three.example",
    [product("three.example", 3)],
)

assert coverage.productive_domains == {
    "one.example",
    "two.example",
    "three.example",
}

assert coverage.retained_domains == {
    "one.example",
    "two.example",
}

# A productive overflow source stays productive even
# when retained capacity is already full.
assert "three.example" in coverage.productive_domains
assert "three.example" not in coverage.retained_domains

# During an active probe the domain may still be
# temporarily occupied. Once exhausted/released,
# only retained productive sources continue occupying
# retained source capacity.
activated = {
    "one.example",
    "two.example",
    "three.example",
}

assert coverage.occupied_domains(activated) == activated

coverage.exhausted_domains.add("three.example")
coverage.released_domains.add("three.example")

assert coverage.occupied_domains(activated) == {
    "one.example",
    "two.example",
}

snapshot = coverage.snapshot()

assert snapshot["productive_domains"] == [
    "one.example",
    "three.example",
    "two.example",
]

assert snapshot["retained_domains"] == [
    "one.example",
    "two.example",
]


# --------------------------------------------------
# PROBE BUDGETS CAN BE DISABLED
# --------------------------------------------------

disabled = ResearchProject.model_validate({
    "id": "c2-disabled",
    "name": "C2 disabled",
    "crawl": {
        "mode": "expedition",
        "max_domains": 1,
        "max_probe_domains": 0,
        "max_probe_pages_total": 0,
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})

assert disabled.crawl.max_probe_domains == 0
assert disabled.crawl.max_probe_pages_total == 0


# --------------------------------------------------
# SPECIFIC TARGET
#
# Broad retained-domain semantics must not replace
# existing specific-target priced-domain occupancy.
# --------------------------------------------------

specific_project = ResearchProject.model_validate({
    "id": "c2-specific",
    "name": "C2 specific target",
    "crawl": {
        "mode": "expedition",
        "max_domains": 1,
    },
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
        "target_identity_terms": ["Acme"],
        "target_identity_anchor_terms": ["Acme"],
    },
})

specific = ResearchCoverage.for_project(specific_project)

assert specific.specific_target is True

specific.observe_entities(
    "target.example",
    [product("target.example", 1)],
)

assert specific.productive_domains == {
    "target.example",
}

# Broad retained-source promotion is intentionally
# not used for specific-target research.
assert specific.retained_domains == set()

print("CANDIDATE PROBE RETENTION TEST OK")
