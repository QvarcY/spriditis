from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field


CHANGE_TYPES = (
    "NEW_ENTITY",
    "ENTITY_DISAPPEARED",
    "PRICE_DROP",
    "PRICE_INCREASE",
    "SOURCE_CHANGED",
)


class ChangeEvent(BaseModel):
    change_type: str
    cluster_key: str
    entity_key: str = ""
    title: str = ""
    source_url: str = ""
    source_domain: str = ""
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


def _decimal_price(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def compare_run_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[ChangeEvent]:
    events: list[ChangeEvent] = []

    before_clusters = before["clusters"]
    after_clusters = after["clusters"]

    before_keys = set(before_clusters)
    after_keys = set(after_clusters)

    for cluster_key in sorted(after_keys - before_keys):
        cluster = after_clusters[cluster_key]
        events.append(
            ChangeEvent(
                change_type="NEW_ENTITY",
                cluster_key=cluster_key,
                title=cluster["title"],
                after={
                    "sources": cluster["sources"],
                    "entity_keys": cluster["entity_keys"],
                },
                evidence={
                    "run_id": after["run_id"],
                    "observation_ids": cluster["observation_ids"],
                },
            )
        )

    for cluster_key in sorted(before_keys - after_keys):
        cluster = before_clusters[cluster_key]
        events.append(
            ChangeEvent(
                change_type="ENTITY_DISAPPEARED",
                cluster_key=cluster_key,
                title=cluster["title"],
                before={
                    "sources": cluster["sources"],
                    "entity_keys": cluster["entity_keys"],
                },
                evidence={
                    "run_id": before["run_id"],
                    "observation_ids": cluster["observation_ids"],
                },
            )
        )

    for cluster_key in sorted(before_keys & after_keys):
        old_cluster = before_clusters[cluster_key]
        new_cluster = after_clusters[cluster_key]

        old_sources = {
            (item["source_domain"], item["source_url"])
            for item in old_cluster["sources"]
        }
        new_sources = {
            (item["source_domain"], item["source_url"])
            for item in new_cluster["sources"]
        }

        if old_sources != new_sources:
            added = sorted(new_sources - old_sources)
            removed = sorted(old_sources - new_sources)
            events.append(
                ChangeEvent(
                    change_type="SOURCE_CHANGED",
                    cluster_key=cluster_key,
                    title=new_cluster["title"] or old_cluster["title"],
                    before={
                        "sources": [
                            {
                                "source_domain": domain,
                                "source_url": url,
                            }
                            for domain, url in sorted(old_sources)
                        ]
                    },
                    after={
                        "sources": [
                            {
                                "source_domain": domain,
                                "source_url": url,
                            }
                            for domain, url in sorted(new_sources)
                        ]
                    },
                    evidence={
                        "before_observation_ids": old_cluster[
                            "observation_ids"
                        ],
                        "after_observation_ids": new_cluster[
                            "observation_ids"
                        ],
                        "added_sources": [
                            {"source_domain": domain, "source_url": url}
                            for domain, url in added
                        ],
                        "removed_sources": [
                            {"source_domain": domain, "source_url": url}
                            for domain, url in removed
                        ],
                    },
                )
            )

    before_entities = before["entities"]
    after_entities = after["entities"]

    for entity_key in sorted(set(before_entities) & set(after_entities)):
        old = before_entities[entity_key]
        new = after_entities[entity_key]

        old_price = _decimal_price(old.get("price"))
        new_price = _decimal_price(new.get("price"))
        old_currency = old.get("currency") or ""
        new_currency = new.get("currency") or ""

        if (
            old_price is None
            or new_price is None
            or not old_currency
            or old_currency != new_currency
            or old_price == new_price
        ):
            continue

        change_type = (
            "PRICE_DROP"
            if new_price < old_price
            else "PRICE_INCREASE"
        )
        events.append(
            ChangeEvent(
                change_type=change_type,
                cluster_key=new["cluster_key"],
                entity_key=entity_key,
                title=new["title"] or old["title"],
                source_url=new["source_url"],
                source_domain=new["source_domain"],
                before={
                    "price": float(old_price),
                    "currency": old_currency,
                },
                after={
                    "price": float(new_price),
                    "currency": new_currency,
                },
                evidence={
                    "before_observation_id": old["observation_id"],
                    "after_observation_id": new["observation_id"],
                    "before_run_id": before["run_id"],
                    "after_run_id": after["run_id"],
                    "before_field_evidence": {
                        field: old["field_evidence"][field]
                        for field in ("price", "currency")
                        if field in old["field_evidence"]
                    },
                    "after_field_evidence": {
                        field: new["field_evidence"][field]
                        for field in ("price", "currency")
                        if field in new["field_evidence"]
                    },
                },
            )
        )

    order = {name: index for index, name in enumerate(CHANGE_TYPES)}
    return sorted(
        events,
        key=lambda event: (
            order.get(event.change_type, len(order)),
            event.cluster_key,
            event.entity_key,
            event.source_url,
        ),
    )
