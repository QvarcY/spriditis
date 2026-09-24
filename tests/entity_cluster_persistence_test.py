from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


project = ResearchProject.model_validate({
    "id": "entity_cluster_persistence",
    "name": "Entity cluster persistence",
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


shop_a = make_entity(
    title="Acme Ergonomic Chair X1",
    url="https://shop-a.example/products/x1",
    domain="shop-a.example",
    price=199.0,
    attributes={
        "brand": "Acme",
        "model": "X1",
        "gtin": "4006381333931",
    },
)

shop_b = make_entity(
    title="Ergonomic Office Chair X1 by Acme",
    url="https://shop-b.example/catalog/acme-x1",
    domain="shop-b.example",
    price=205.0,
    attributes={
        "manufacturer": "Acme",
        "model": "X1",
        "gtin": "4006381333931",
    },
)

title_only = make_entity(
    title="Acme Ergonomic Chair X1",
    url="https://shop-c.example/products/generic-x1",
    domain="shop-c.example",
    price=179.0,
    attributes={},
)

with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == 9
        db.save_project(project)
        run_id = db.start_run(project)

        db.upsert_entity(project, run_id, shop_a)
        db.upsert_entity(project, run_id, shop_b)
        db.upsert_entity(project, run_id, title_only)

        # Repeat observation from shop A must not create another cluster/member.
        shop_a_repeat = shop_a.model_copy(update={"price": 189.0})
        db.upsert_entity(project, run_id, shop_a_repeat)

        result = ResearchRunResult(project_id=project.id)
        result.entities = [
            shop_a_repeat,
            shop_b,
            title_only,
        ]
        db.finish_run(run_id, result)

        clusters = db.entity_clusters(project.id)
        assert len(clusters) == 2

        merged = next(
            cluster
            for cluster in clusters
            if cluster["source_count"] == 2
        )
        separate = next(
            cluster
            for cluster in clusters
            if cluster["source_count"] == 1
        )

        assert merged["member_count"] == 2
        assert merged["source_count"] == 2
        assert {
            member["source_domain"]
            for member in merged["members"]
        } == {
            "shop-a.example",
            "shop-b.example",
        }

        reasons = {
            member["source_domain"]: member["match_reason"]
            for member in merged["members"]
        }
        assert reasons["shop-a.example"] == "new_cluster"
        assert reasons["shop-b.example"] == "gtin_exact"

        assert separate["member_count"] == 1
        assert separate["source_count"] == 1
        assert separate["members"][0]["source_domain"] == "shop-c.example"
        assert separate["members"][0]["match_reason"] == "new_cluster"

        entity_count = db.conn.execute(
            "SELECT COUNT(*) FROM entities WHERE project_id=?",
            (project.id,),
        ).fetchone()[0]
        observation_count = db.conn.execute(
            "SELECT COUNT(*) FROM observations WHERE project_id=?",
            (project.id,),
        ).fetchone()[0]
        member_count = db.conn.execute(
            """
            SELECT COUNT(*)
            FROM entity_cluster_members
            WHERE project_id=?
            """,
            (project.id,),
        ).fetchone()[0]

        assert entity_count == 3
        assert observation_count == 4
        assert member_count == 3

        trace = db.trace_run(project.id, run_id)
        assert trace is not None
        assert len(trace["observations"]) == 4

        shop_a_clusters = {
            row["cluster_key"]
            for row in trace["observations"]
            if row["source_domain"] == "shop-a.example"
        }
        shop_b_clusters = {
            row["cluster_key"]
            for row in trace["observations"]
            if row["source_domain"] == "shop-b.example"
        }
        shop_c_clusters = {
            row["cluster_key"]
            for row in trace["observations"]
            if row["source_domain"] == "shop-c.example"
        }

        assert len(shop_a_clusters) == 1
        assert shop_a_clusters == shop_b_clusters
        assert shop_c_clusters != shop_a_clusters

        latest_shop_a = db.conn.execute(
            """
            SELECT last_price
            FROM entities
            WHERE project_id=? AND source_domain='shop-a.example'
            """,
            (project.id,),
        ).fetchone()
        assert latest_shop_a == (189.0,)
    finally:
        db.close()

print("ENTITY CLUSTER PERSISTENCE TEST OK")
print("source_entities=3 observations=4 canonical_clusters=2")
print("cross_source_gtin_cluster_members=2")
print("title_only_cluster_members=1")
