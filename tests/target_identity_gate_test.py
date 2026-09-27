from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

sys.path.insert(
    0,
    str(_BootstrapPath(__file__).resolve().parents[1]),
)

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.reports.html import _analytics
from spriditis.resolution.target import apply_target_identity_gate


def project_with_target() -> ResearchProject:
    return ResearchProject.model_validate(
        {
            "id": "target_identity_test",
            "name": "Bambu Lab P1S Combo",
            "keywords": [
                "Bambu",
                "Lab",
                "P1S",
                "Combo",
                "piedāvājumi",
                "cenas",
            ],
            "seed_urls": [],
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
                "min_relevance_score": 0.35,
                "target_identity_terms": ["P1S", "Combo"],
                "target_identity_anchor_terms": ["P1S"],
            },
        }
    )


def entity(
    title: str,
    *,
    price: float | None,
    attributes: dict | None = None,
) -> MarketEntity:
    return MarketEntity(
        title=title,
        source_url="https://example.com/item",
        source_domain="example.com",
        price=price,
        seller="Example",
        is_relevant=True,
        relevance_score=0.80,
        attributes=attributes or {},
    )


project = project_with_target()

p1s = apply_target_identity_gate(
    entity(
        "Bambu Lab P1S Combo",
        price=606.0,
        attributes={
            "brand": "BAMBU LAB",
            "mpn": "BAMBUP1SCOM",
        },
    ),
    project,
)
assert p1s.is_relevant is True
assert p1s.attributes["target_identity_status"] == "confirmed"
assert p1s.attributes["target_identity_reason"] == "target_identity_exact"

p2s = apply_target_identity_gate(
    entity(
        "Bambu Lab P2S Combo 3D printeris",
        price=826.0,
        attributes={
            "brand": "BAMBU LAB",
            "mpn": "BAMBUP2SC",
        },
    ),
    project,
)
assert p2s.is_relevant is False
assert p2s.attributes["target_identity_status"] == "rejected"
assert p2s.attributes["target_identity_reason"] == "target_model_conflict"

x2d = apply_target_identity_gate(
    entity(
        "Bambu Lab X2D Combo 3D printeris",
        price=939.0,
        attributes={
            "brand": "BAMBU LAB",
            "mpn": "BAMBUX2DC",
        },
    ),
    project,
)
assert x2d.is_relevant is False
assert x2d.attributes["target_identity_status"] == "rejected"
assert x2d.attributes["target_identity_reason"] == "target_model_conflict"

category = apply_target_identity_gate(
    entity(
        "BAMBU LAB",
        price=28.0,
        attributes={"brand": "BAMBU LAB"},
    ),
    project,
)
assert category.is_relevant is False
assert category.attributes["target_identity_status"] == "rejected"
assert category.attributes["target_identity_reason"] == "target_model_missing"

incomplete = apply_target_identity_gate(
    entity(
        "Bambu Lab P1S 3D printeris",
        price=549.0,
        attributes={"brand": "BAMBU LAB"},
    ),
    project,
)
assert incomplete.is_relevant is False
assert incomplete.attributes["target_identity_status"] == "uncertain"
assert incomplete.attributes["target_identity_reason"] == "target_identity_incomplete"

stats = _analytics([p1s, p2s, x2d, category, incomplete])
assert stats["relevant"] == 1
assert stats["priced"] == 1
assert stats["min_price"] == 606.0
assert stats["max_price"] == 606.0
assert stats["median_price"] == 606.0

broad_project = ResearchProject.model_validate(
    {
        "id": "broad_market_test",
        "name": "3D printeri Latvijā",
        "keywords": ["printeri", "Latvijā"],
        "seed_urls": [],
    }
)
broad = apply_target_identity_gate(
    entity("Bambu Lab P2S Combo", price=826.0),
    broad_project,
)
assert broad.is_relevant is True
assert "target_identity_status" not in broad.attributes

print("TARGET IDENTITY GATE TEST OK")
