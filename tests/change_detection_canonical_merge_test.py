from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "change_detection_canonical_merge",
    "name": "Change Detection canonical merge",
    "keywords": ["product"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


def make_entity(
    *,
    title: str,
    url: str,
    domain: str,
    price: float,
    attributes: dict[str, str],
) -> MarketEntity:
    return MarketEntity(
        title=title,
        source_url=url,
        source_domain=domain,
        price=price,
        currency="EUR",
        attributes=attributes,
        extraction_method="json-ld",
    )


source_a = make_entity(
    title="Canonical Product A",
    url="https://a.example/product/shared",
    domain="a.example",
    price=100.0,
    attributes={"gtin": "4006381333931"},
)

source_b = make_entity(
    title="Canonical Product B",
    url="https://b.example/product/shared",
    domain="b.example",
    price=105.0,
    attributes={"brand": "Acme", "model": "X1"},
)

source_b_resolved = source_b.model_copy(
    update={
        "attributes": {
            "brand": "Acme",
            "model": "X1",
            "gtin": "4006381333931",
        }
    }
)


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 11

        db.save_project(project)

        run_a = db.start_run(project)
        db.upsert_entity(project, run_a, source_a)

        run_b = db.start_run(project)
        db.upsert_entity(project, run_b, source_b)

        pre_merge = db.compare_runs(project.id, run_a, run_b)
        assert pre_merge["comparison_basis"] == {
            "facts": "historical_observation_snapshots",
            "identity": "current_canonical_membership",
        }
        assert pre_merge["counts"]["NEW_ENTITY"] == 1
        assert pre_merge["counts"]["ENTITY_DISAPPEARED"] == 1
        assert pre_merge["counts"]["SOURCE_CHANGED"] == 0

        # Later evidence strengthens source B, but its existing membership
        # intentionally remains stable until an explicit merge is requested.
        db.upsert_entity(project, run_b, source_b_resolved)

        merged = db.merge_entity_clusters(
            project.id,
            source_b.stable_key,
            source_a.stable_key,
        )
        assert merged["decision"] == "merged"
        assert merged["reason"] == "explicit_strong_identity_match"
        assert merged["matched_signals"] == ["gtin_exact"]

        post_merge = db.compare_runs(project.id, run_a, run_b)

        assert post_merge["counts"] == {
            "NEW_ENTITY": 0,
            "ENTITY_DISAPPEARED": 0,
            "PRICE_DROP": 0,
            "PRICE_INCREASE": 0,
            "SELLER_CHANGED": 0,
            "DESCRIPTION_CHANGED": 0,
            "IMAGE_CHANGED": 0,
            "SOURCE_CHANGED": 1,
        }
        assert len(post_merge["events"]) == 1

        event = post_merge["events"][0]
        assert event["change_type"] == "SOURCE_CHANGED"
        assert event["cluster_key"] == source_a.stable_key

        assert event["before"]["sources"] == [
            {
                "source_domain": "a.example",
                "source_url": "https://a.example/product/shared",
            }
        ]
        assert event["after"]["sources"] == [
            {
                "source_domain": "b.example",
                "source_url": "https://b.example/product/shared",
            }
        ]

        assert event["evidence"]["removed_sources"] == [
            {
                "source_domain": "a.example",
                "source_url": "https://a.example/product/shared",
            }
        ]
        assert event["evidence"]["added_sources"] == [
            {
                "source_domain": "b.example",
                "source_url": "https://b.example/product/shared",
            }
        ]

        assert len(event["evidence"]["before_observation_ids"]) == 1
        assert len(event["evidence"]["after_observation_ids"]) == 2

        # Recomputing a diff after a human/audited merge is intentionally
        # identity-normalized using current canonical membership, while all
        # field facts still come from immutable historical observations.
        assert post_merge["comparison_basis"] == {
            "facts": "historical_observation_snapshots",
            "identity": "current_canonical_membership",
        }
    finally:
        db.close()

print("CHANGE DETECTION CANONICAL MERGE TEST OK")
print("pre_merge=new+disappeared")
print("post_merge=source_changed_only")
print("facts=historical_observations")
print("identity=current_canonical_membership")
print("schema_version=11")
