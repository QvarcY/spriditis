from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import Database


project = ResearchProject.model_validate({
    "id": "entity_cluster_merge",
    "name": "Entity cluster merge",
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


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == 10
        db.save_project(project)
        run_id = db.start_run(project)

        # Start with two separate clusters: A has GTIN, B has maker+model only.
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
        db.upsert_entity(project, run_id, a)
        db.upsert_entity(project, run_id, b)

        assert a.stable_key != b.stable_key

        # Later evidence strengthens B, but existing membership is intentionally
        # stable until an explicit merge command is issued.
        b_updated = b.model_copy(
            update={
                "attributes": {
                    "brand": "Acme",
                    "model": "X1",
                    "gtin": "4006381333931",
                }
            }
        )
        db.upsert_entity(project, run_id, b_updated)

        before_merge = db.entity_clusters(project.id)
        assert len(before_merge) == 2

        merged = db.merge_entity_clusters(
            project.id,
            b.stable_key,
            a.stable_key,
        )
        assert merged["decision"] == "merged"
        assert merged["reason"] == "explicit_strong_identity_match"
        assert merged["matched_signals"] == ["gtin_exact"]
        assert merged["source_member_count"] == 1
        assert merged["target_member_count"] == 1
        assert merged["merged_member_count"] == 1

        active_after_merge = db.entity_clusters(project.id)
        assert len(active_after_merge) == 1
        assert active_after_merge[0]["cluster_key"] == a.stable_key
        assert active_after_merge[0]["member_count"] == 2
        assert active_after_merge[0]["source_count"] == 2

        b_membership = db.conn.execute(
            """
            SELECT cluster_key
            FROM entity_cluster_members
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, b.stable_key),
        ).fetchone()
        assert b_membership == (a.stable_key,)

        source_cluster = db.conn.execute(
            """
            SELECT merged_into_cluster_key, merged_at
            FROM entity_clusters
            WHERE project_id=? AND cluster_key=?
            """,
            (project.id, b.stable_key),
        ).fetchone()
        assert source_cluster is not None
        assert source_cluster[0] == a.stable_key
        assert source_cluster[1]

        # Strong GTIN conflict must reject even an explicit merge.
        c = make_entity(
            title="Conflict C",
            url="https://c.example/product/c",
            domain="c.example",
            attributes={"gtin": "036000291452"},
        )
        d = make_entity(
            title="Conflict D",
            url="https://d.example/product/d",
            domain="d.example",
            attributes={"gtin": "9501234600000"},
        )
        db.upsert_entity(project, run_id, c)
        db.upsert_entity(project, run_id, d)

        conflict_before = db.conn.execute(
            """
            SELECT cluster_key
            FROM entity_cluster_members
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, d.stable_key),
        ).fetchone()

        conflict = db.merge_entity_clusters(
            project.id,
            d.stable_key,
            c.stable_key,
        )
        assert conflict["decision"] == "rejected"
        assert conflict["reason"] == "identity_conflict"
        assert conflict["conflicting_signals"] == ["gtin_conflict"]

        conflict_after = db.conn.execute(
            """
            SELECT cluster_key
            FROM entity_cluster_members
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, d.stable_key),
        ).fetchone()
        assert conflict_after == conflict_before

        # Title-only similarity remains insufficient for explicit merge.
        e = make_entity(
            title="Plain Ergonomic Chair",
            url="https://e.example/product/e",
            domain="e.example",
            attributes={},
        )
        f = make_entity(
            title="Plain Ergonomic Chair",
            url="https://f.example/product/f",
            domain="f.example",
            attributes={},
        )
        db.upsert_entity(project, run_id, e)
        db.upsert_entity(project, run_id, f)

        title_only_before = db.conn.execute(
            """
            SELECT cluster_key
            FROM entity_cluster_members
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, f.stable_key),
        ).fetchone()

        title_only = db.merge_entity_clusters(
            project.id,
            f.stable_key,
            e.stable_key,
        )
        assert title_only["decision"] == "rejected"
        assert title_only["reason"] == "no_strong_identity_match"
        assert title_only["matched_signals"] == []
        assert title_only["conflicting_signals"] == []

        title_only_after = db.conn.execute(
            """
            SELECT cluster_key
            FROM entity_cluster_members
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, f.stable_key),
        ).fetchone()
        assert title_only_after == title_only_before

        events = db.entity_cluster_merge_events(project.id)
        assert [event["decision"] for event in events] == [
            "merged",
            "rejected",
            "rejected",
        ]
        assert [event["reason"] for event in events] == [
            "explicit_strong_identity_match",
            "identity_conflict",
            "no_strong_identity_match",
        ]

        # Historical source-specific evidence remains intact.
        entity_count = db.conn.execute(
            "SELECT COUNT(*) FROM entities WHERE project_id=?",
            (project.id,),
        ).fetchone()[0]
        observation_count = db.conn.execute(
            "SELECT COUNT(*) FROM observations WHERE project_id=?",
            (project.id,),
        ).fetchone()[0]

        assert entity_count == 6
        assert observation_count == 7
    finally:
        db.close()

print("ENTITY CLUSTER MERGE TEST OK")
print("strong_match=merged")
print("identity_conflict=rejected")
print("title_only=rejected")
print("source_entities_preserved=6 observations_preserved=7")
