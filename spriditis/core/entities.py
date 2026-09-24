from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ExtractionEvidence(BaseModel):
    value: Any
    source_url: str
    extraction_method: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""
    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


EVIDENCE_HIGH_CONFIDENCE_MIN = 0.90
EVIDENCE_MEDIUM_CONFIDENCE_MIN = 0.70


def evidence_confidence_band(confidence: float) -> str:
    if confidence >= EVIDENCE_HIGH_CONFIDENCE_MIN:
        return "high"
    if confidence >= EVIDENCE_MEDIUM_CONFIDENCE_MIN:
        return "medium"
    return "low"


def summarize_field_evidence(
    field_evidence: dict[str, ExtractionEvidence],
    *,
    expected_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_values = expected_values or {}
    bands = {"high": 0, "medium": 0, "low": 0}
    methods: dict[str, int] = {}
    supported: list[dict[str, Any]] = []
    mismatched: list[dict[str, Any]] = []
    default_fields: list[str] = []

    for field, fact in sorted(field_evidence.items()):
        expected_known = field in expected_values
        if expected_known and fact.value != expected_values[field]:
            mismatched.append(
                {
                    "field": field,
                    "current_value": expected_values[field],
                    "evidence_value": fact.value,
                    "extraction_method": fact.extraction_method,
                    "confidence": fact.confidence,
                }
            )
            continue

        band = evidence_confidence_band(fact.confidence)
        bands[band] += 1
        methods[fact.extraction_method or "unknown"] = (
            methods.get(fact.extraction_method or "unknown", 0) + 1
        )
        supported.append(
            {
                "field": field,
                "confidence": fact.confidence,
                "band": band,
                "extraction_method": fact.extraction_method,
                "evidence": fact.evidence,
            }
        )
        if fact.evidence.startswith("default:"):
            default_fields.append(field)

    missing = sorted(
        field
        for field in expected_values
        if field not in field_evidence
    )
    low_fields = [
        item
        for item in supported
        if item["band"] == "low"
    ]
    weakest = sorted(
        supported,
        key=lambda item: (item["confidence"], item["field"]),
    )[:5]

    return {
        "field_count": len(field_evidence),
        "supported_field_count": len(supported),
        "confidence_bands": bands,
        "methods": dict(sorted(methods.items())),
        "low_confidence_fields": low_fields,
        "weakest_fields": weakest,
        "missing_evidence_fields": missing,
        "mismatched_evidence_fields": mismatched,
        "default_fields": sorted(default_fields),
    }


class EntityEnrichment(BaseModel):
    is_relevant: bool = True
    category: str = "uncategorized"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    opportunity_notes: str = ""


class MarketEntity(BaseModel):
    title: str
    entity_type: str = "product"

    source_url: str
    source_domain: str = ""
    description: str = ""

    price: float | None = None
    currency: str = "EUR"
    seller: str = ""
    image_url: str = ""

    category: str = "uncategorized"
    is_relevant: bool = True
    confidence: float = 0.0
    relevance_score: float = 0.0

    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    opportunity_notes: str = ""

    extraction_method: str = ""
    evidence: str = ""
    field_evidence: dict[str, ExtractionEvidence] = Field(
        default_factory=dict
    )

    discovered_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def stable_key(self) -> str:
        base = "|".join(
            [
                self.entity_type.strip().lower(),
                self.source_url.strip().lower(),
                self.normalized_title,
            ]
        )
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    @property
    def normalized_title(self) -> str:
        return re.sub(r"\s+", " ", self.title).strip().lower()

    def _expected_evidence_values(self) -> dict[str, Any]:
        expected: dict[str, Any] = {
            "title": self.title,
            "source_url": self.source_url,
        }
        if self.description:
            expected["description"] = self.description
        if self.price is not None:
            expected["price"] = self.price
        if self.currency:
            expected["currency"] = self.currency
        if self.seller:
            expected["seller"] = self.seller
        if self.image_url:
            expected["image_url"] = self.image_url

        for key in (
            "gtin",
            "brand",
            "manufacturer",
            "model",
            "mpn",
            "sku",
        ):
            value = self.attributes.get(key)
            if value not in (None, ""):
                expected[f"attributes.{key}"] = value

        return expected

    def evidence_quality_summary(self) -> dict[str, Any]:
        return summarize_field_evidence(
            self.field_evidence,
            expected_values=self._expected_evidence_values(),
        )

    def apply_enrichment(self, enrichment: EntityEnrichment) -> "MarketEntity":
        data = self.model_dump()
        data.update(
            {
                "is_relevant": enrichment.is_relevant,
                "category": enrichment.category,
                "confidence": enrichment.confidence,
                "relevance_score": enrichment.relevance_score,
                "tags": enrichment.tags,
                "attributes": {
                    **data.get("attributes", {}),
                    **enrichment.attributes,
                },
                "opportunity_notes": enrichment.opportunity_notes,
            }
        )
        if enrichment.summary:
            data["description"] = enrichment.summary
        return MarketEntity(**data)

    def as_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)
