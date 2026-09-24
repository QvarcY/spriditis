from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import Database


project = ResearchProject.model_validate({
    "id": "entity_resolution_review_queue",
    "name": "Entity resolution review queue",
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
    attributes: dict[str, str],
) -> MarketEntity:
    return MarketEntity(
        title=title,
        source_url=url,
        source_domain=domain,
        attributes=attributes,
        extraction_method="json-ld",
    )


a = make_entity(
    title="Catalog A",
    url="https://a.example/product/a",
    domain="a.example",
    attributes={"gtin": "4006381333931"},
)

b = make_entity(
    title="Catalog B",
    url="https://b.example/product/b",
    domain="b.example",
    attributes={"brand": "Acme", "model": "X1"},
)

bridge = make_entity(
    title="Catalog bridge",
    url="https://bridge.example/product/bridge",
    domain="bridge.example",
    attributes={
        "gtin": "4006381333931",
        "brand": "Acme",
        "model": "X1",
    },
)

conflict = make_entity(
    title="Catalog conflict",
    url="https://conflict.example/product/conflict",
    domain="conflict.example",
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
        db.upsert_entity(project, run_id, bridge)
        db.upsert_entity(project, run_id, conflict)

        queue = db.entity_resolution_review_queue(project.id)
        assert len(queue) == 2
        assert [row["decision"] for row in queue] == [
            "deferred_ambiguous",
            "created_separate",
        ]
        assert [row["reason"] for row in queue] == [
            "ambiguous_multiple_clusters",
            "identity_conflict",
        ]

        ambiguous_only = db.entity_resolution_review_queue(
            project.id,
            kind="ambiguous",
        )
        conflict_only = db.entity_resolution_review_queue(
            project.id,
            kind="conflict",
        )
        assert len(ambiguous_only) == 1
        assert len(conflict_only) == 1
        assert ambiguous_only[0]["entity_key"] == bridge.stable_key
        assert conflict_only[0]["entity_key"] == conflict.stable_key

        # Human chooses one strong candidate for the bridge entity.
        merge_bridge = db.merge_entity_clusters(
            project.id,
            bridge.stable_key,
            a.stable_key,
        )
        assert merge_bridge["decision"] == "merged"
        assert merge_bridge["reason"] == "explicit_strong_identity_match"

        queue_after_bridge = db.entity_resolution_review_queue(project.id)
        assert len(queue_after_bridge) == 1
        assert queue_after_bridge[0]["entity_key"] == conflict.stable_key
        assert queue_after_bridge[0]["decision"] == "created_separate"

        # A rejected review action must leave the item unresolved.
        rejected_conflict = db.merge_entity_clusters(
            project.id,
            conflict.stable_key,
            a.stable_key,
        )
        assert rejected_conflict["decision"] == "rejected"
        assert rejected_conflict["reason"] == "identity_conflict"

        queue_after_reject = db.entity_resolution_review_queue(project.id)
        assert len(queue_after_reject) == 1
        assert queue_after_reject[0]["entity_key"] == conflict.stable_key

        # Later evidence corrects the source identity. Existing membership
        # remains stable until the explicit merge is retried.
        corrected_conflict = conflict.model_copy(
            update={"attributes": {"gtin": "4006381333931"}}
        )
        db.upsert_entity(
            project,
            run_id,
            corrected_conflict,
        )

        queue_before_retry = db.entity_resolution_review_queue(project.id)
        assert len(queue_before_retry) == 1

        resolved_conflict = db.merge_entity_clusters(
            project.id,
            conflict.stable_key,
            a.stable_key,
        )
        assert resolved_conflict["decision"] == "merged"
        assert resolved_conflict["reason"] == "explicit_strong_identity_match"
        assert resolved_conflict["matched_signals"] == ["gtin_exact"]

        final_queue = db.entity_resolution_review_queue(project.id)
        assert final_queue == []

        merges = db.entity_cluster_merge_events(project.id)
        assert [row["decision"] for row in merges] == [
            "merged",
            "rejected",
            "merged",
        ]
        assert [row["reason"] for row in merges] == [
            "explicit_strong_identity_match",
            "identity_conflict",
            "explicit_strong_identity_match",
        ]
    finally:
        db.close()

print("ENTITY RESOLUTION REVIEW QUEUE TEST OK")
print("initial_unresolved=2 ambiguous=1 conflict=1")
print("rejected_merge_keeps_item_open")
print("resolved_queue=0")
