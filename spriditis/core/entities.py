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
