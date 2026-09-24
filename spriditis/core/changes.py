from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field


CHANGE_TYPES = (
    "NEW_ENTITY",
    "ENTITY_DISAPPEARED",
    "PRICE_DROP",
    "PRICE_INCREASE",
    "SELLER_CHANGED",
    "DESCRIPTION_CHANGED",
    "IMAGE_CHANGED",
    "SOURCE_CHANGED",
    "DOMAIN_FAILED",
    "DOMAIN_RECOVERED",
    "FEED_NEW_ENTRIES",
    "FEED_FAILED",
    "FEED_RECOVERED",
)

FIELD_CHANGE_MIN_CONFIDENCE = 0.70


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


def _normalized_field_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def _supported_field_fact(
    entity: dict[str, Any],
    field: str,
) -> dict[str, Any] | None:
    field_evidence = entity.get("field_evidence") or {}
    fact = field_evidence.get(field)
    if not isinstance(fact, dict):
        return None

    if _normalized_field_value(fact.get("value")) != _normalized_field_value(
        entity.get(field)
    ):
        return None

    try:
        confidence = float(fact.get("confidence") or 0.0)
    except (TypeError, ValueError):
        return None

    if confidence < FIELD_CHANGE_MIN_CONFIDENCE:
        return None

    return fact


def classify_domain_visits(
    visits: list[dict[str, Any]],
) -> dict[str, Any]:
    reachable_visit_ids: list[int] = []
    failure_visit_ids: list[int] = []
    ignored_visit_ids: list[int] = []
    outcomes: list[dict[str, Any]] = []

    for visit in visits:
        visit_id = int(visit["id"])
        outcome = str(visit.get("outcome") or "unknown")
        status = visit.get("http_status")

        outcomes.append(
            {
                "visit_id": visit_id,
                "outcome": outcome,
                "http_status": status,
                "url": visit.get("final_url") or visit.get("url") or "",
            }
        )

        if outcome in {"html_ok", "non_html"}:
            reachable_visit_ids.append(visit_id)
            continue

        if outcome == "http_status" and status is not None:
            try:
                numeric_status = int(status)
            except (TypeError, ValueError):
                ignored_visit_ids.append(visit_id)
                continue

            if numeric_status >= 500:
                failure_visit_ids.append(visit_id)
            else:
                reachable_visit_ids.append(visit_id)
            continue

        if outcome.startswith("http_error:"):
            failure_visit_ids.append(visit_id)
            continue

        ignored_visit_ids.append(visit_id)

    if reachable_visit_ids:
        state = "reachable"
    elif failure_visit_ids:
        state = "failed"
    else:
        state = "unknown"

    return {
        "state": state,
        "visit_ids": sorted(
            reachable_visit_ids
            + failure_visit_ids
            + ignored_visit_ids
        ),
        "reachable_visit_ids": sorted(reachable_visit_ids),
        "failure_visit_ids": sorted(failure_visit_ids),
        "ignored_visit_ids": sorted(ignored_visit_ids),
        "outcomes": outcomes,
    }


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

    before_domains = before.get("domains", {})
    after_domains = after.get("domains", {})

    for domain in sorted(set(before_domains) & set(after_domains)):
        old_domain = before_domains[domain]
        new_domain = after_domains[domain]
        old_state = old_domain["state"]
        new_state = new_domain["state"]

        if old_state == "reachable" and new_state == "failed":
            change_type = "DOMAIN_FAILED"
        elif old_state == "failed" and new_state == "reachable":
            change_type = "DOMAIN_RECOVERED"
        else:
            continue

        events.append(
            ChangeEvent(
                change_type=change_type,
                cluster_key="",
                title=domain,
                source_domain=domain,
                before={"state": old_state},
                after={"state": new_state},
                evidence={
                    "before_run_id": before["run_id"],
                    "after_run_id": after["run_id"],
                    "before_visit_ids": old_domain["visit_ids"],
                    "after_visit_ids": new_domain["visit_ids"],
                    "before_reachable_visit_ids": old_domain[
                        "reachable_visit_ids"
                    ],
                    "after_reachable_visit_ids": new_domain[
                        "reachable_visit_ids"
                    ],
                    "before_failure_visit_ids": old_domain[
                        "failure_visit_ids"
                    ],
                    "after_failure_visit_ids": new_domain[
                        "failure_visit_ids"
                    ],
                    "before_outcomes": old_domain["outcomes"],
                    "after_outcomes": new_domain["outcomes"],
                },
            )
        )

    before_feeds = before.get("feeds", {})
    after_feeds = after.get("feeds", {})

    for feed_url in sorted(set(before_feeds) & set(after_feeds)):
        old_feed = before_feeds[feed_url]
        new_feed = after_feeds[feed_url]
        old_status = old_feed.get("status") or "unknown"
        new_status = new_feed.get("status") or "unknown"

        if old_status == "active" and new_status == "error":
            events.append(
                ChangeEvent(
                    change_type="FEED_FAILED",
                    cluster_key="",
                    title=feed_url,
                    source_url=feed_url,
                    source_domain=new_feed.get("domain") or old_feed.get("domain") or "",
                    before={
                        "status": old_status,
                        "last_error": old_feed.get("last_error") or "",
                    },
                    after={
                        "status": new_status,
                        "last_error": new_feed.get("last_error") or "",
                    },
                    evidence={
                        "before_run_id": before["run_id"],
                        "after_run_id": after["run_id"],
                        "before_snapshot_id": old_feed["id"],
                        "after_snapshot_id": new_feed["id"],
                    },
                )
            )
        elif old_status == "error" and new_status == "active":
            events.append(
                ChangeEvent(
                    change_type="FEED_RECOVERED",
                    cluster_key="",
                    title=feed_url,
                    source_url=feed_url,
                    source_domain=new_feed.get("domain") or old_feed.get("domain") or "",
                    before={
                        "status": old_status,
                        "last_error": old_feed.get("last_error") or "",
                    },
                    after={
                        "status": new_status,
                        "last_error": new_feed.get("last_error") or "",
                    },
                    evidence={
                        "before_run_id": before["run_id"],
                        "after_run_id": after["run_id"],
                        "before_snapshot_id": old_feed["id"],
                        "after_snapshot_id": new_feed["id"],
                    },
                )
            )

        try:
            old_new_entries = int(old_feed.get("new_entries") or 0)
            new_new_entries = int(new_feed.get("new_entries") or 0)
        except (TypeError, ValueError):
            continue

        delta = new_new_entries - old_new_entries
        if new_status != "active" or delta <= 0:
            continue

        events.append(
            ChangeEvent(
                change_type="FEED_NEW_ENTRIES",
                cluster_key="",
                title=feed_url,
                source_url=feed_url,
                source_domain=new_feed.get("domain") or old_feed.get("domain") or "",
                before={
                    "new_entries_total": old_new_entries,
                    "last_entry_id": old_feed.get("last_entry_id") or "",
                },
                after={
                    "new_entries_total": new_new_entries,
                    "last_entry_id": new_feed.get("last_entry_id") or "",
                },
                evidence={
                    "new_entries_delta": delta,
                    "before_run_id": before["run_id"],
                    "after_run_id": after["run_id"],
                    "before_snapshot_id": old_feed["id"],
                    "after_snapshot_id": new_feed["id"],
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
            old_price is not None
            and new_price is not None
            and old_currency
            and old_currency == new_currency
            and old_price != new_price
        ):
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

        field_changes = (
            ("seller", "SELLER_CHANGED"),
            ("description", "DESCRIPTION_CHANGED"),
            ("image_url", "IMAGE_CHANGED"),
        )
        for field, change_type in field_changes:
            old_fact = _supported_field_fact(old, field)
            new_fact = _supported_field_fact(new, field)
            if old_fact is None or new_fact is None:
                continue

            old_value = _normalized_field_value(old.get(field))
            new_value = _normalized_field_value(new.get(field))
            if old_value == new_value:
                continue

            events.append(
                ChangeEvent(
                    change_type=change_type,
                    cluster_key=new["cluster_key"],
                    entity_key=entity_key,
                    title=new["title"] or old["title"],
                    source_url=new["source_url"],
                    source_domain=new["source_domain"],
                    before={field: old.get(field)},
                    after={field: new.get(field)},
                    evidence={
                        "field": field,
                        "minimum_confidence": FIELD_CHANGE_MIN_CONFIDENCE,
                        "before_observation_id": old["observation_id"],
                        "after_observation_id": new["observation_id"],
                        "before_run_id": before["run_id"],
                        "after_run_id": after["run_id"],
                        "before_field_evidence": old_fact,
                        "after_field_evidence": new_fact,
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
