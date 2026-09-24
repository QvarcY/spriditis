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

unrelated_gtin = make_entity(
    title="Unrelated GTIN product",
    url="https://unrelated.example/product/u",
    domain="unrelated.example",
    attributes={"gtin": "5901234123457"},
)

cluster_seed = make_entity(
    title="Acme X2 seed",
    url="https://seed.example/product/x2",
    domain="seed.example",
    attributes={"brand": "Acme", "model": "X2"},
)

cluster_member = make_entity(
    title="Acme X2 member",
    url="https://member.example/product/x2",
    domain="member.example",
    attributes={
        "brand": "Acme",
        "model": "X2",
        "gtin": "036000291452",
    },
)

hard_conflict = make_entity(
    title="Acme X2 conflicting GTIN",
    url="https://hard-conflict.example/product/x2",
    domain="hard-conflict.example",
    attributes={
        "brand": "Acme",
        "model": "X2",
        "gtin": "9501234600000",
    },
)


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        db.save_project(project)
        run_id = db.start_run(project)

        for entity in (
            gtin_entity,
            maker_model_entity,
            bridge_entity,
            unrelated_gtin,
            cluster_seed,
            cluster_member,
            hard_conflict,
        ):
            db.upsert_entity(project, run_id, entity)

        events = db.entity_resolution_events(
            project.id,
            run_id=run_id,
        )
        assert len(events) == 7

        (
            first,
            second,
            bridge,
            unrelated,
            seed,
            member,
            conflict,
        ) = events

        assert first["decision"] == "new_cluster"
        assert first["reason"] == "no_candidates"
        assert first["candidate_cluster_keys"] == []
        assert first["conflict_cluster_keys"] == []
        assert first["compared_entities"] == 0

        assert second["decision"] == "new_cluster"
        assert second["reason"] == "no_strong_match"
        assert second["candidate_cluster_keys"] == []
        assert second["conflict_cluster_keys"] == []

        assert bridge["decision"] == "deferred_ambiguous"
        assert bridge["reason"] == "ambiguous_multiple_clusters"
        assert len(bridge["candidate_cluster_keys"]) == 2
        assert bridge["selected_cluster_key"] == bridge["entity_key"]
        assert set(bridge["matched_signals"]) == {
            "gtin_exact",
            "maker_model_exact",
        }
        assert bridge["conflict_cluster_keys"] == []

        # A different GTIN on an otherwise unrelated product is not an
        # identity conflict. It is simply insufficient evidence for a match.
        assert unrelated["decision"] == "new_cluster"
        assert unrelated["reason"] == "no_strong_match"
        assert unrelated["candidate_cluster_keys"] == []
        assert unrelated["conflict_cluster_keys"] == []
        assert unrelated["conflicting_signals"] == []

        assert seed["decision"] == "new_cluster"
        assert seed["reason"] == "no_strong_match"

        # The second X2 entity joins the seed by maker+model even though
        # unrelated clusters elsewhere may have different GTINs.
        assert member["decision"] == "linked"
        assert member["reason"] == "maker_model_exact"
        assert member["candidate_cluster_keys"] == [
            cluster_seed.stable_key
        ]
        assert member["conflict_cluster_keys"] == []

        # The third X2 entity matches the seed by maker+model but conflicts
        # with another member of that same candidate cluster by GTIN. The
        # cluster must be vetoed instead of accepting the positive match.
        assert conflict["decision"] == "created_separate"
        assert conflict["reason"] == "target_cluster_identity_conflict"
        assert conflict["candidate_cluster_keys"] == []
        assert conflict["conflict_cluster_keys"] == [
            cluster_seed.stable_key
        ]
        assert conflict["matched_signals"] == ["maker_model_exact"]
        assert conflict["conflicting_signals"] == ["gtin_conflict"]
        assert conflict["selected_cluster_key"] == conflict["entity_key"]

        clusters = db.entity_clusters(project.id)
        by_key = {cluster["cluster_key"]: cluster for cluster in clusters}
        assert by_key[cluster_seed.stable_key]["member_count"] == 2
        assert by_key[hard_conflict.stable_key]["member_count"] == 1

        trace = db.trace_run(project.id, run_id)
        assert trace is not None
        assert len(trace["entity_resolution_events"]) == 7

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
        assert len(events_after_repeat) == 7
    finally:
        db.close()

print("ENTITY RESOLUTION AUDIT TEST OK")
print("unrelated_gtin=new_cluster_not_conflict")
print("target_cluster_match_plus_gtin_conflict=hard_veto")
print("hard_veto_signals=maker_model_exact+gtin_conflict")
print("ambiguous_cluster_merge=deferred")
