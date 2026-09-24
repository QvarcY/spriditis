from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
from tempfile import TemporaryDirectory

sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.core.entities import ExtractionEvidence, MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.storage.database import CURRENT_SCHEMA_VERSION, Database


def fact(
    value,
    *,
    url: str,
    confidence: float,
    evidence: str,
    method: str = "json-ld",
) -> ExtractionEvidence:
    return ExtractionEvidence(
        value=value,
        source_url=url,
        extraction_method=method,
        confidence=confidence,
        evidence=evidence,
    )


project = ResearchProject.model_validate({
    "id": "change_detection_diff",
    "name": "Change Detection diff",
    "keywords": ["product"],
    "seed_urls": [],
    "analysis": {
        "ai_enabled": False,
        "ai_provider": "none",
    },
})


def entity(
    *,
    title: str,
    url: str,
    domain: str,
    price: float | None,
    currency: str = "EUR",
    gtin: str = "",
) -> MarketEntity:
    attributes = {"gtin": gtin} if gtin else {}
    return MarketEntity(
        title=title,
        source_url=url,
        source_domain=domain,
        price=price,
        currency=currency,
        attributes=attributes,
        extraction_method="json-ld",
    )


drop_a = entity(
    title="Price Drop Product",
    url="https://price.example/product/drop",
    domain="price.example",
    price=100.0,
    gtin="4006381333931",
).model_copy(
    update={
        "field_evidence": {
            "price": fact(
                100.0,
                url="https://price.example/product/drop",
                confidence=0.98,
                evidence="jsonld:offers.price",
            ),
            "currency": fact(
                "EUR",
                url="https://price.example/product/drop",
                confidence=0.98,
                evidence="jsonld:offers.priceCurrency",
            ),
        }
    }
)
increase_a = entity(
    title="Price Increase Product",
    url="https://price.example/product/increase",
    domain="price.example",
    price=50.0,
    gtin="5901234123457",
)
disappeared = entity(
    title="Disappeared Product",
    url="https://old.example/product/gone",
    domain="old.example",
    price=25.0,
    gtin="036000291452",
)
source_old = entity(
    title="Cross Source Product",
    url="https://source-a.example/product/shared",
    domain="source-a.example",
    price=80.0,
    gtin="9501234600000",
)
currency_a = entity(
    title="Currency Changed Product",
    url="https://currency.example/product/1",
    domain="currency.example",
    price=10.0,
    currency="EUR",
)

drop_b = drop_a.model_copy(
    update={
        "price": 90.0,
        "field_evidence": {
            "price": fact(
                90.0,
                url="https://price.example/product/drop",
                confidence=0.93,
                evidence="microdata:itemprop=price",
                method="microdata",
            ),
            "currency": fact(
                "EUR",
                url="https://price.example/product/drop",
                confidence=0.93,
                evidence="microdata:itemprop=priceCurrency",
                method="microdata",
            ),
        },
    }
)
increase_b = increase_a.model_copy(update={"price": 65.0})
new_entity = entity(
    title="New Product",
    url="https://new.example/product/new",
    domain="new.example",
    price=30.0,
    gtin="5012345678900",
)
source_new = entity(
    title="Cross Source Product Alternate",
    url="https://source-b.example/product/shared",
    domain="source-b.example",
    price=82.0,
    gtin="9501234600000",
)
currency_b = currency_a.model_copy(
    update={
        "price": 8.0,
        "currency": "USD",
    }
)


with TemporaryDirectory() as tmp:
    db = Database(_BootstrapPath(tmp) / "spriditis.db")
    try:
        assert db.schema_version() == CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION == 12

        db.save_project(project)

        run_a = db.start_run(project)
        for item in (
            drop_a,
            increase_a,
            disappeared,
            source_old,
            currency_a,
        ):
            db.upsert_entity(project, run_a, item)

        run_b = db.start_run(project)
        for item in (
            drop_b,
            increase_b,
            new_entity,
            source_new,
            currency_b,
        ):
            db.upsert_entity(project, run_b, item)

        diff = db.compare_runs(project.id, run_a, run_b)

        assert diff["comparison_basis"] == {
            "entity_facts": "historical_observation_snapshots",
            "domain_health": "historical_page_visits",
            "feed_state": "historical_feed_snapshots",
            "identity": "current_canonical_membership",
        }
        assert diff["before_run"]["id"] == run_a
        assert diff["after_run"]["id"] == run_b
        assert diff["before_run"]["entity_count"] == 5
        assert diff["after_run"]["entity_count"] == 5

        assert diff["counts"] == {
            "NEW_ENTITY": 1,
            "ENTITY_DISAPPEARED": 1,
            "PRICE_DROP": 1,
            "PRICE_INCREASE": 1,
            "SELLER_CHANGED": 0,
            "DESCRIPTION_CHANGED": 0,
            "IMAGE_CHANGED": 0,
            "SOURCE_CHANGED": 1,
            "DOMAIN_FAILED": 0,
            "DOMAIN_RECOVERED": 0,
            "FEED_APPEARED": 0,
            "FEED_DISAPPEARED": 0,
            "FEED_NEW_ENTRIES": 0,
            "FEED_FAILED": 0,
            "FEED_RECOVERED": 0,
        }

        assert len(diff["events"]) == 5

        by_type = {
            event["change_type"]: event
            for event in diff["events"]
        }

        new_event = by_type["NEW_ENTITY"]
        assert new_event["title"] == "New Product"
        assert new_event["after"]["entity_keys"] == [
            new_entity.stable_key
        ]

        disappeared_event = by_type["ENTITY_DISAPPEARED"]
        assert disappeared_event["title"] == "Disappeared Product"
        assert disappeared_event["before"]["entity_keys"] == [
            disappeared.stable_key
        ]

        drop_event = by_type["PRICE_DROP"]
        assert drop_event["entity_key"] == drop_a.stable_key
        assert drop_event["source_domain"] == "price.example"
        assert drop_event["before"] == {
            "price": 100.0,
            "currency": "EUR",
        }
        assert drop_event["after"] == {
            "price": 90.0,
            "currency": "EUR",
        }
        assert drop_event["evidence"]["before_run_id"] == run_a
        assert drop_event["evidence"]["after_run_id"] == run_b
        assert (
            drop_event["evidence"]["before_field_evidence"]["price"]["value"]
            == 100.0
        )
        assert (
            drop_event["evidence"]["before_field_evidence"]["price"][
                "extraction_method"
            ]
            == "json-ld"
        )
        assert (
            drop_event["evidence"]["after_field_evidence"]["price"]["value"]
            == 90.0
        )
        assert (
            drop_event["evidence"]["after_field_evidence"]["price"][
                "extraction_method"
            ]
            == "microdata"
        )
        assert (
            drop_event["evidence"]["after_field_evidence"]["price"][
                "confidence"
            ]
            == 0.93
        )

        increase_event = by_type["PRICE_INCREASE"]
        assert increase_event["entity_key"] == increase_a.stable_key
        assert increase_event["before"]["price"] == 50.0
        assert increase_event["after"]["price"] == 65.0

        source_event = by_type["SOURCE_CHANGED"]
        assert source_event["title"] in {
            "Cross Source Product",
            "Cross Source Product Alternate",
        }
        assert source_event["evidence"]["removed_sources"] == [
            {
                "source_domain": "source-a.example",
                "source_url": "https://source-a.example/product/shared",
            }
        ]
        assert source_event["evidence"]["added_sources"] == [
            {
                "source_domain": "source-b.example",
                "source_url": "https://source-b.example/product/shared",
            }
        ]
        assert len(
            source_event["evidence"]["before_observation_ids"]
        ) == 1
        assert len(
            source_event["evidence"]["after_observation_ids"]
        ) == 1

        price_entity_keys = {
            event["entity_key"]
            for event in diff["events"]
            if event["change_type"] in {
                "PRICE_DROP",
                "PRICE_INCREASE",
            }
        }
        assert currency_a.stable_key not in price_entity_keys

        try:
            db.compare_runs(project.id, run_a, run_a)
        except ValueError as exc:
            assert "atšķirīgiem" in str(exc)
        else:
            raise AssertionError("Same-run diff must be rejected")

        try:
            db.compare_runs(project.id, run_a, 999999)
        except ValueError as exc:
            assert "Run nav atrasts" in str(exc)
        else:
            raise AssertionError("Missing run must be rejected")
    finally:
        db.close()

print("CHANGE DETECTION DIFF TEST OK")
print("events=new+disappeared+price_drop+price_increase+source_changed")
print("price_comparison=same_source_entity_only")
print("currency_mismatch=no_price_event")
print("price_event_provenance=historical_field_evidence")
print(f"schema_version={CURRENT_SCHEMA_VERSION}")
