from __future__ import annotations

import json
import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import ExtractionEvidence, MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


project = ResearchProject.model_validate({
    "id": "field_evidence_persistence",
    "name": "Field evidence persistence",
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


first = MarketEntity(
    title="Acme Chair X2",
    source_url="https://shop.example/product/acme-x2",
    source_domain="shop.example",
    price=129.99,
    currency="EUR",
    extraction_method="dom-fallback",
    field_evidence={
        "title": fact(
            "Acme Chair X2",
            method="dom-fallback",
            confidence=0.72,
            evidence="dom:h1",
        ),
        "price": fact(
            129.99,
            method="dom-fallback",
            confidence=0.68,
            evidence="dom:product-price:explicit_currency",
        ),
        "currency": fact(
            "EUR",
            method="dom-fallback",
            confidence=0.68,
            evidence="dom:product-price:explicit_currency",
        ),
    },
)

second = first.model_copy(
    update={
        "price": 149.0,
        "extraction_method": "microdata",
        "field_evidence": {
            "title": fact(
                "Acme Chair X2",
                method="microdata",
                confidence=0.93,
                evidence="microdata:itemprop=name",
            ),
            "price": fact(
                149.0,
                method="microdata",
                confidence=0.93,
                evidence="microdata:itemprop=price",
            ),
            "currency": fact(
                "EUR",
                method="microdata",
                confidence=0.93,
                evidence="microdata:itemprop=priceCurrency",
            ),
        },
    }
)


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 11

        db.save_project(project)
        run_id = db.start_run(project)

        db.upsert_entity(project, run_id, first)

        current_raw = db.conn.execute(
            """
            SELECT field_evidence_json
            FROM entities
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, first.stable_key),
        ).fetchone()
        assert current_raw is not None
        current = json.loads(current_raw[0])
        assert current["price"]["value"] == 129.99
        assert current["price"]["confidence"] == 0.68
        assert current["price"]["extraction_method"] == "dom-fallback"

        rows = db._cluster_member_rows(
            project.id,
            first.stable_key,
        )
        assert len(rows) == 1
        reloaded = db._entity_from_storage_row(rows[0])
        assert reloaded.field_evidence["price"].value == 129.99
        assert reloaded.field_evidence["price"].confidence == 0.68

        explain = db.explain_entity_cluster(
            project.id,
            first.stable_key,
        )
        assert explain is not None
        assert len(explain["members"]) == 1
        assert (
            explain["members"][0]["field_evidence"]["price"]["value"]
            == 129.99
        )
        assert (
            explain["members"][0]["field_evidence"]["price"]["confidence"]
            == 0.68
        )

        db.upsert_entity(project, run_id, second)

        updated_raw = db.conn.execute(
            """
            SELECT last_price, extraction_method, field_evidence_json
            FROM entities
            WHERE project_id=? AND entity_key=?
            """,
            (project.id, first.stable_key),
        ).fetchone()
        assert updated_raw is not None
        assert updated_raw[0] == 149.0
        assert updated_raw[1] == "microdata"

        updated = json.loads(updated_raw[2])
        assert updated["price"]["value"] == 149.0
        assert updated["price"]["confidence"] == 0.93
        assert updated["price"]["extraction_method"] == "microdata"

        snapshots = db.conn.execute(
            """
            SELECT snapshot_json
            FROM observations
            WHERE project_id=? AND entity_key=?
            ORDER BY id
            """,
            (project.id, first.stable_key),
        ).fetchall()
        assert len(snapshots) == 2

        first_snapshot = json.loads(snapshots[0][0])
        second_snapshot = json.loads(snapshots[1][0])

        assert first_snapshot["price"] == 129.99
        assert (
            first_snapshot["field_evidence"]["price"]["confidence"]
            == 0.68
        )
        assert (
            first_snapshot["field_evidence"]["price"]["extraction_method"]
            == "dom-fallback"
        )

        assert second_snapshot["price"] == 149.0
        assert (
            second_snapshot["field_evidence"]["price"]["confidence"]
            == 0.93
        )
        assert (
            second_snapshot["field_evidence"]["price"]["extraction_method"]
            == "microdata"
        )
    finally:
        db.close()

print("FIELD EVIDENCE PERSISTENCE TEST OK")
print("schema_version=11")
print("current_entity_evidence=latest")
print("observation_snapshots=historical")
print("cluster_explain=current_field_evidence_visible")
