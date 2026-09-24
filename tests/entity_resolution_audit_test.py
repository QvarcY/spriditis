from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "entity_resolution_audit",
    "name": "Entity resolution audit",
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


gtin_entity = make_entity(
    title="Catalog item A",
    url="https://a.example/product/a",
    domain="a.example",
    attributes={"gtin": "4006381333931"},
)

maker_model_entity = make_entity(
    title="Catalog item B",
    url="https://b.example/product/b",
    domain="b.example",
    attributes={"brand": "Acme", "model": "X1"},
)

bridge_entity = make_entity(
    title="Catalog item bridge",
    url="https://bridge.example/product/bridge",
    domain="bridge.example",
    attributes={
        "gtin": "4006381333931",
        "brand": "Acme",
        "model": "X1",
    },
)

conflict_entity = make_entity(
    title="Catalog item conflict",
    url="https://conflict.example/product/conflict",
    domain="conflict.example",
    attributes={"gtin": "036000291452"},
)

with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        db.save_project(project)
        run_id = db.start_run(project)

        db.upsert_entity(project, run_id, gtin_entity)
        db.upsert_entity(project, run_id, maker_model_entity)
        db.upsert_entity(project, run_id, bridge_entity)
        db.upsert_entity(project, run_id, conflict_entity)

        events = db.entity_resolution_events(
            project.id,
            run_id=run_id,
        )
        assert len(events) == 4

        first, second, bridge, conflict = events

        assert first["decision"] == "new_cluster"
        assert first["reason"] == "no_candidates"
        assert first["candidate_cluster_keys"] == []
        assert first["conflict_cluster_keys"] == []
        assert first["compared_entities"] == 0

        assert second["decision"] == "new_cluster"
        assert second["reason"] == "no_strong_match"
        assert second["candidate_cluster_keys"] == []
        assert second["conflict_cluster_keys"] == []
        assert second["compared_entities"] == 1

        assert bridge["decision"] == "deferred_ambiguous"
        assert bridge["reason"] == "ambiguous_multiple_clusters"
        assert len(bridge["candidate_cluster_keys"]) == 2
        assert bridge["selected_cluster_key"] == bridge["entity_key"]
        assert set(bridge["matched_signals"]) == {
            "gtin_exact",
            "maker_model_exact",
        }
        assert bridge["compared_entities"] == 2

        assert conflict["decision"] == "created_separate"
        assert conflict["reason"] == "identity_conflict"
        assert conflict["candidate_cluster_keys"] == []
        assert len(conflict["conflict_cluster_keys"]) == 2
        assert conflict["conflicting_signals"] == ["gtin_conflict"]
        assert conflict["selected_cluster_key"] == conflict["entity_key"]
        assert conflict["compared_entities"] == 3

        clusters = db.entity_clusters(project.id)
        assert len(clusters) == 4
        assert all(cluster["member_count"] == 1 for cluster in clusters)

        trace = db.trace_run(project.id, run_id)
        assert trace is not None
        assert len(trace["entity_resolution_events"]) == 4
        assert [
            item["decision"]
            for item in trace["entity_resolution_events"]
        ] == [
            "new_cluster",
            "new_cluster",
            "deferred_ambiguous",
            "created_separate",
        ]

        # Re-observing an already-clustered source entity is not a new
        # identity-resolution decision.
        db.upsert_entity(
            project,
            run_id,
            gtin_entity.model_copy(update={"price": 99.0}),
        )
        events_after_repeat = db.entity_resolution_events(
            project.id,
            run_id=run_id,
        )
        assert len(events_after_repeat) == 4
    finally:
        db.close()

print("ENTITY RESOLUTION AUDIT TEST OK")
print(
    "decisions=new_cluster > new_cluster > "
    "deferred_ambiguous > created_separate"
)
print("ambiguous_cluster_merge=deferred")
print("identity_conflict=audited")
