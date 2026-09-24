from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import ExtractionEvidence, MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "change_detection_field_changes",
    "name": "Change Detection field changes",
    "keywords": ["product"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


def fact(
    value,
    *,
    url: str,
    method: str,
    confidence: float,
    evidence: str,
) -> ExtractionEvidence:
    return ExtractionEvidence(
        value=value,
        source_url=url,
        extraction_method=method,
        confidence=confidence,
        evidence=evidence,
    )


def base_entity(
    *,
    title: str,
    url: str,
    domain: str,
    seller: str = "",
    description: str = "",
    image_url: str = "",
    field_evidence: dict[str, ExtractionEvidence] | None = None,
) -> MarketEntity:
    return MarketEntity(
        title=title,
        source_url=url,
        source_domain=domain,
        seller=seller,
        description=description,
        image_url=image_url,
        extraction_method="mixed",
        field_evidence=field_evidence or {},
    )


seller_url = "https://shop.example/product/seller"
seller_a = base_entity(
    title="Seller Product",
    url=seller_url,
    domain="shop.example",
    seller="Old Shop",
    field_evidence={
        "seller": fact(
            "Old Shop",
            url=seller_url,
            method="json-ld",
            confidence=0.98,
            evidence="jsonld:seller",
        )
    },
)
seller_b = seller_a.model_copy(
    update={
        "seller": "New Shop",
        "field_evidence": {
            "seller": fact(
                "New Shop",
                url=seller_url,
                method="microdata",
                confidence=0.93,
                evidence="microdata:itemprop=seller",
            )
        },
    }
)

description_url = "https://shop.example/product/description"
description_a = base_entity(
    title="Description Product",
    url=description_url,
    domain="shop.example",
    description="Old description",
    field_evidence={
        "description": fact(
            "Old description",
            url=description_url,
            method="json-ld",
            confidence=0.98,
            evidence="jsonld:description",
        )
    },
)
description_b = description_a.model_copy(
    update={
        "description": "New description",
        "field_evidence": {
            "description": fact(
                "New description",
                url=description_url,
                method="meistardarbs-html",
                confidence=0.82,
                evidence="visible_description",
            )
        },
    }
)

image_page_url = "https://shop.example/product/image"
image_a = base_entity(
    title="Image Product",
    url=image_page_url,
    domain="shop.example",
    image_url="https://cdn.example/old.jpg",
    field_evidence={
        "image_url": fact(
            "https://cdn.example/old.jpg",
            url=image_page_url,
            method="opengraph",
            confidence=0.88,
            evidence="opengraph:og:image",
        )
    },
)
image_b = image_a.model_copy(
    update={
        "image_url": "https://cdn.example/new.jpg",
        "field_evidence": {
            "image_url": fact(
                "https://cdn.example/new.jpg",
                url=image_page_url,
                method="json-ld",
                confidence=0.98,
                evidence="jsonld:image",
            )
        },
    }
)

low_url = "https://shop.example/product/low-confidence"
low_a = base_entity(
    title="Low Confidence Product",
    url=low_url,
    domain="shop.example",
    description="Old low confidence text",
    field_evidence={
        "description": fact(
            "Old low confidence text",
            url=low_url,
            method="dom-fallback",
            confidence=0.62,
            evidence="dom:description",
        )
    },
)
low_b = low_a.model_copy(
    update={
        "description": "New low confidence text",
        "field_evidence": {
            "description": fact(
                "New low confidence text",
                url=low_url,
                method="dom-fallback",
                confidence=0.62,
                evidence="dom:description",
            )
        },
    }
)

stale_url = "https://shop.example/product/stale-evidence"
stale_a = base_entity(
    title="Stale Evidence Product",
    url=stale_url,
    domain="shop.example",
    seller="Seller A",
    field_evidence={
        "seller": fact(
            "Seller A",
            url=stale_url,
            method="json-ld",
            confidence=0.98,
            evidence="jsonld:seller",
        )
    },
)
stale_b = stale_a.model_copy(
    update={
        "seller": "Seller B",
        "field_evidence": {
            "seller": fact(
                "Different Seller",
                url=stale_url,
                method="json-ld",
                confidence=0.98,
                evidence="jsonld:seller",
            )
        },
    }
)

missing_url = "https://shop.example/product/missing-evidence"
missing_a = base_entity(
    title="Missing Evidence Product",
    url=missing_url,
    domain="shop.example",
    image_url="https://cdn.example/a.jpg",
)
missing_b = missing_a.model_copy(
    update={
        "image_url": "https://cdn.example/b.jpg",
    }
)


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 11

        db.save_project(project)

        run_a = db.start_run(project)
        for item in (
            seller_a,
            description_a,
            image_a,
            low_a,
            stale_a,
            missing_a,
        ):
            db.upsert_entity(project, run_a, item)

        run_b = db.start_run(project)
        for item in (
            seller_b,
            description_b,
            image_b,
            low_b,
            stale_b,
            missing_b,
        ):
            db.upsert_entity(project, run_b, item)

        diff = db.compare_runs(project.id, run_a, run_b)

        assert diff["counts"] == {
            "NEW_ENTITY": 0,
            "ENTITY_DISAPPEARED": 0,
            "PRICE_DROP": 0,
            "PRICE_INCREASE": 0,
            "SELLER_CHANGED": 1,
            "DESCRIPTION_CHANGED": 1,
            "IMAGE_CHANGED": 1,
            "SOURCE_CHANGED": 0,
        }
        assert len(diff["events"]) == 3

        by_type = {
            event["change_type"]: event
            for event in diff["events"]
        }

        seller_event = by_type["SELLER_CHANGED"]
        assert seller_event["before"] == {"seller": "Old Shop"}
        assert seller_event["after"] == {"seller": "New Shop"}
        assert seller_event["evidence"]["field"] == "seller"
        assert seller_event["evidence"]["minimum_confidence"] == 0.70
        assert (
            seller_event["evidence"]["before_field_evidence"][
                "extraction_method"
            ]
            == "json-ld"
        )
        assert (
            seller_event["evidence"]["after_field_evidence"][
                "extraction_method"
            ]
            == "microdata"
        )

        description_event = by_type["DESCRIPTION_CHANGED"]
        assert description_event["before"] == {
            "description": "Old description"
        }
        assert description_event["after"] == {
            "description": "New description"
        }
        assert (
            description_event["evidence"]["after_field_evidence"][
                "confidence"
            ]
            == 0.82
        )

        image_event = by_type["IMAGE_CHANGED"]
        assert image_event["before"] == {
            "image_url": "https://cdn.example/old.jpg"
        }
        assert image_event["after"] == {
            "image_url": "https://cdn.example/new.jpg"
        }

        event_entity_keys = {
            event["entity_key"]
            for event in diff["events"]
        }
        assert low_a.stable_key not in event_entity_keys
        assert stale_a.stable_key not in event_entity_keys
        assert missing_a.stable_key not in event_entity_keys
    finally:
        db.close()

print("CHANGE DETECTION FIELD CHANGES TEST OK")
print("events=seller+description+image")
print("minimum_confidence=0.70")
print("low_confidence=suppressed")
print("mismatched_evidence=suppressed")
print("missing_evidence=suppressed")
print("schema_version=11")
