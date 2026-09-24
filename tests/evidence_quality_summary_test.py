from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import ExtractionEvidence, MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "evidence_quality_summary",
    "name": "Evidence quality summary",
    "keywords": ["chair"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


def fact(
    value,
    *,
    method: str,
    confidence: float,
    evidence: str,
) -> ExtractionEvidence:
    return ExtractionEvidence(
        value=value,
        source_url="https://shop.example/product/acme-x2",
        extraction_method=method,
        confidence=confidence,
        evidence=evidence,
    )


entity = MarketEntity(
    title="Acme Chair X2",
    source_url="https://shop.example/product/acme-x2",
    source_domain="shop.example",
    description="Current product description",
    price=129.99,
    currency="EUR",
    seller="Example Shop",
    image_url="https://shop.example/images/acme-x2.jpg",
    attributes={"gtin": "4006381333931"},
    extraction_method="mixed",
    field_evidence={
        "title": fact(
            "Acme Chair X2",
            method="json-ld",
            confidence=0.98,
            evidence="jsonld:name",
        ),
        "source_url": fact(
            "https://shop.example/product/acme-x2",
            method="json-ld",
            confidence=0.98,
            evidence="jsonld:url",
        ),
        "price": fact(
            129.99,
            method="dom-fallback",
            confidence=0.68,
            evidence="dom:product-price:explicit_currency",
        ),
        "currency": fact(
            "EUR",
            method="json-ld",
            confidence=0.55,
            evidence="default:EUR",
        ),
        "seller": fact(
            "Example Shop",
            method="meistardarbs-html",
            confidence=0.78,
            evidence="visible_seller",
        ),
        "description": fact(
            "Old product description",
            method="opengraph",
            confidence=0.88,
            evidence="opengraph:og:description",
        ),
        "attributes.gtin": fact(
            "4006381333931",
            method="microdata",
            confidence=0.93,
            evidence="microdata:itemprop=gtin13",
        ),
    },
)

quality = entity.evidence_quality_summary()

assert "score" not in quality
assert "average_confidence" not in quality
assert quality["field_count"] == 7
assert quality["supported_field_count"] == 6
assert quality["confidence_bands"] == {
    "high": 3,
    "medium": 1,
    "low": 2,
}
assert quality["methods"] == {
    "dom-fallback": 1,
    "json-ld": 3,
    "meistardarbs-html": 1,
    "microdata": 1,
}
assert [item["field"] for item in quality["low_confidence_fields"]] == [
    "currency",
    "price",
]
assert quality["default_fields"] == ["currency"]
assert quality["missing_evidence_fields"] == ["image_url"]
assert len(quality["mismatched_evidence_fields"]) == 1
assert quality["mismatched_evidence_fields"][0]["field"] == "description"
assert quality["mismatched_evidence_fields"][0]["current_value"] == (
    "Current product description"
)
assert quality["mismatched_evidence_fields"][0]["evidence_value"] == (
    "Old product description"
)
assert quality["weakest_fields"][0]["field"] == "currency"
assert quality["weakest_fields"][0]["confidence"] == 0.55

legacy_like = MarketEntity(
    title="Legacy Product",
    source_url="https://legacy.example/product/1",
    source_domain="legacy.example",
    currency="EUR",
    extraction_method="legacy",
)

with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 11

        db.save_project(project)
        run_id = db.start_run(project)
        db.upsert_entity(project, run_id, entity)
        db.upsert_entity(project, run_id, legacy_like)

        summary = db.project_evidence_quality(project.id)

        assert "score" not in summary
        assert "average_confidence" not in summary
        assert summary["entity_count"] == 2
        assert summary["entities_with_evidence"] == 1
        assert summary["entities_without_evidence"] == 1
        assert summary["evidence_fact_count"] == 7
        assert summary["supported_field_count"] == 6
        assert summary["confidence_bands"] == {
            "high": 3,
            "medium": 1,
            "low": 2,
        }
        assert summary["methods"] == {
            "json-ld": 3,
            "dom-fallback": 1,
            "meistardarbs-html": 1,
            "microdata": 1,
        }

        low_counts = {
            row["field"]: row["count"]
            for row in summary["low_confidence_fields"]
        }
        assert low_counts == {
            "currency": 1,
            "price": 1,
        }

        missing_counts = {
            row["field"]: row["count"]
            for row in summary["missing_evidence_fields"]
        }
        assert missing_counts == {
            "currency": 1,
            "image_url": 1,
            "source_url": 1,
            "title": 1,
        }

        mismatch_counts = {
            row["field"]: row["count"]
            for row in summary["mismatched_evidence_fields"]
        }
        assert mismatch_counts == {"description": 1}

        default_counts = {
            row["field"]: row["count"]
            for row in summary["default_fields"]
        }
        assert default_counts == {"currency": 1}

        explained = db.explain_entity_cluster(
            project.id,
            entity.stable_key,
        )
        assert explained is not None
        assert len(explained["members"]) == 1

        member_quality = explained["members"][0]["evidence_quality"]
        assert member_quality["confidence_bands"] == {
            "high": 3,
            "medium": 1,
            "low": 2,
        }
        assert member_quality["missing_evidence_fields"] == ["image_url"]
        assert (
            member_quality["mismatched_evidence_fields"][0]["field"]
            == "description"
        )
    finally:
        db.close()

print("EVIDENCE QUALITY SUMMARY TEST OK")
print("bands=high:3 medium:1 low:2")
print("missing_evidence=image_url+legacy_fields")
print("mismatched_evidence=description")
print("default_evidence=currency")
print("project_summary=no_opaque_score")
