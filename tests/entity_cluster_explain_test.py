from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import Database


project = ResearchProject.model_validate({
    "id": "entity_cluster_explain",
    "name": "Entity cluster explain",
    "keywords": ["chair"],
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
    price: float | None,
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


a = make_entity(
    title="Acme Chair A",
    url="https://a.example/product/a",
    domain="a.example",
    price=199.0,
    attributes={"gtin": "4006381333931"},
)

b = make_entity(
    title="Acme Chair B",
    url="https://b.example/product/b",
    domain="b.example",
    price=205.0,
    attributes={"brand": "Acme", "model": "X1"},
)

conflict = make_entity(
    title="Acme Chair Conflict",
    url="https://conflict.example/product/c",
    domain="conflict.example",
    price=189.0,
    attributes={"gtin": "036000291452"},
)


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == 10
        db.save_project(project)
        run_id = db.start_run(project)

        db.upsert_entity(project, run_id, a)
        db.upsert_entity(project, run_id, b)

        b_updated = b.model_copy(
            update={
                "price": 202.0,
                "attributes": {
                    "brand": "Acme",
                    "model": "X1",
                    "gtin": "4006381333931",
                },
            }
        )
        db.upsert_entity(project, run_id, b_updated)

        merged = db.merge_entity_clusters(
            project.id,
            b.stable_key,
            a.stable_key,
        )
        assert merged["decision"] == "merged"

        db.upsert_entity(project, run_id, conflict)

        active = db.explain_entity_cluster(
            project.id,
            a.stable_key,
        )
        assert active is not None
        assert active["status"] == "active"
        assert active["merged_into_cluster_key"] == ""
        assert active["member_count"] == 2
        assert active["source_count"] == 2
        assert active["observation_count"] == 3
        assert active["identity_signals"]["gtin"] == [
            "4006381333931",
        ]
        assert active["identity_signals"]["brand"] == ["Acme"]
        assert active["identity_signals"]["model"] == ["X1"]
        assert {
            member["source_domain"]
            for member in active["members"]
        } == {"a.example", "b.example"}
        assert {
            len(member["observations"])
            for member in active["members"]
        } == {1, 2}
        assert len(active["resolution_events"]) == 2
        assert [event["decision"] for event in active["resolution_events"]] == [
            "new_cluster",
            "new_cluster",
        ]
        assert len(active["merge_events"]) == 1
        assert active["merge_events"][0]["decision"] == "merged"
        assert (
            active["merge_events"][0]["reason"]
            == "explicit_strong_identity_match"
        )
        assert active["review_items"] == []

        historical = db.explain_entity_cluster(
            project.id,
            b.stable_key,
        )
        assert historical is not None
        assert historical["status"] == "merged"
        assert historical["merged_into_cluster_key"] == a.stable_key
        assert historical["merged_at"]
        assert historical["member_count"] == 0
        assert historical["source_count"] == 0
        assert historical["observation_count"] == 0
        assert len(historical["resolution_events"]) == 1
        assert historical["resolution_events"][0]["entity_key"] == b.stable_key
        assert len(historical["merge_events"]) == 1
        assert (
            historical["merge_events"][0]["source_cluster_key"]
            == b.stable_key
        )
        assert (
            historical["merge_events"][0]["target_cluster_key"]
            == a.stable_key
        )

        unresolved = db.explain_entity_cluster(
            project.id,
            conflict.stable_key,
        )
        assert unresolved is not None
        assert unresolved["status"] == "active"
        assert unresolved["member_count"] == 1
        assert unresolved["source_count"] == 1
        assert unresolved["observation_count"] == 1
        assert unresolved["identity_signals"]["gtin"] == [
            "036000291452",
        ]
        assert len(unresolved["resolution_events"]) == 1
        assert (
            unresolved["resolution_events"][0]["decision"]
            == "created_separate"
        )
        assert (
            unresolved["resolution_events"][0]["reason"]
            == "identity_conflict"
        )
        assert len(unresolved["review_items"]) == 1
        assert (
            unresolved["review_items"][0]["decision"]
            == "created_separate"
        )
        assert (
            unresolved["review_items"][0]["reason"]
            == "identity_conflict"
        )

        missing = db.explain_entity_cluster(
            project.id,
            "missing-cluster",
        )
        assert missing is None
    finally:
        db.close()

print("ENTITY CLUSTER EXPLAIN TEST OK")
print("active_cluster=members+observations+identity+history")
print("merged_cluster=redirect+merge_history")
print("unresolved_cluster=review_item_visible")
