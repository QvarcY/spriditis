from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from spriditis.core.entities import MarketEntity


_GTIN_KEYS = (
    "gtin14",
    "gtin13",
    "gtin12",
    "gtin8",
    "gtin",
    "ean13",
    "ean",
    "upc",
)


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def normalize_code(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).upper()
    return re.sub(r"[^0-9A-Z]+", "", text)


def normalize_gtin(value: object) -> str:
    if value is None:
        return ""

    digits = re.sub(r"\D+", "", str(value))
    if len(digits) not in {8, 12, 13, 14}:
        return ""

    body = digits[:-1]
    expected = int(digits[-1])

    checksum = 0
    for index, char in enumerate(reversed(body), start=1):
        weight = 3 if index % 2 == 1 else 1
        checksum += int(char) * weight

    check_digit = (10 - (checksum % 10)) % 10
    return digits if check_digit == expected else ""


def _attributes(entity: MarketEntity) -> dict[str, object]:
    return {
        str(key).casefold(): value
        for key, value in entity.attributes.items()
    }


def _first_attribute(
    attributes: dict[str, object],
    *keys: str,
) -> object:
    for key in keys:
        value = attributes.get(key.casefold())
        if value not in (None, ""):
            return value
    return ""


@dataclass(frozen=True)
class EntityIdentity:
    source_domain: str
    normalized_title: str
    gtin: str = ""
    brand: str = ""
    manufacturer: str = ""
    model: str = ""
    mpn: str = ""
    sku: str = ""

    @property
    def maker_names(self) -> frozenset[str]:
        return frozenset(
            item
            for item in (self.brand, self.manufacturer)
            if item
        )


@dataclass(frozen=True)
class ResolutionDecision:
    outcome: str
    reason: str
    matched_signals: tuple[str, ...] = ()
    supporting_signals: tuple[str, ...] = ()
    conflicting_signals: tuple[str, ...] = ()
    left: EntityIdentity | None = None
    right: EntityIdentity | None = None


def extract_identity(entity: MarketEntity) -> EntityIdentity:
    attributes = _attributes(entity)

    gtin = ""
    for key in _GTIN_KEYS:
        gtin = normalize_gtin(attributes.get(key))
        if gtin:
            break

    return EntityIdentity(
        source_domain=entity.source_domain.strip().casefold(),
        normalized_title=normalize_text(entity.title),
        gtin=gtin,
        brand=normalize_text(
            _first_attribute(attributes, "brand")
        ),
        manufacturer=normalize_text(
            _first_attribute(attributes, "manufacturer")
        ),
        model=normalize_code(
            _first_attribute(attributes, "model", "model_number")
        ),
        mpn=normalize_code(
            _first_attribute(attributes, "mpn")
        ),
        sku=normalize_code(
            _first_attribute(attributes, "sku")
        ),
    )


def resolve_entities(
    left_entity: MarketEntity,
    right_entity: MarketEntity,
) -> ResolutionDecision:
    left = extract_identity(left_entity)
    right = extract_identity(right_entity)

    matched: list[str] = []
    supporting: list[str] = []
    conflicting: list[str] = []

    if left.gtin and right.gtin:
        if left.gtin == right.gtin:
            matched.append("gtin_exact")
            return ResolutionDecision(
                outcome="match",
                reason="gtin_exact",
                matched_signals=tuple(matched),
                supporting_signals=tuple(supporting),
                conflicting_signals=tuple(conflicting),
                left=left,
                right=right,
            )

        conflicting.append("gtin_conflict")
        return ResolutionDecision(
            outcome="conflict",
            reason="gtin_conflict",
            matched_signals=tuple(matched),
            supporting_signals=tuple(supporting),
            conflicting_signals=tuple(conflicting),
            left=left,
            right=right,
        )

    shared_makers = left.maker_names & right.maker_names

    if (
        shared_makers
        and left.model
        and right.model
        and left.model == right.model
    ):
        matched.append("maker_model_exact")
        if (
            left.normalized_title
            and left.normalized_title == right.normalized_title
        ):
            supporting.append("title_exact")
        return ResolutionDecision(
            outcome="match",
            reason="maker_model_exact",
            matched_signals=tuple(matched),
            supporting_signals=tuple(supporting),
            conflicting_signals=tuple(conflicting),
            left=left,
            right=right,
        )

    if (
        shared_makers
        and left.mpn
        and right.mpn
        and left.mpn == right.mpn
    ):
        matched.append("maker_mpn_exact")
        if (
            left.normalized_title
            and left.normalized_title == right.normalized_title
        ):
            supporting.append("title_exact")
        return ResolutionDecision(
            outcome="match",
            reason="maker_mpn_exact",
            matched_signals=tuple(matched),
            supporting_signals=tuple(supporting),
            conflicting_signals=tuple(conflicting),
            left=left,
            right=right,
        )

    if left.sku and right.sku and left.sku == right.sku:
        if (
            left.source_domain
            and left.source_domain == right.source_domain
        ):
            matched.append("source_sku_exact")
            return ResolutionDecision(
                outcome="match",
                reason="source_sku_exact",
                matched_signals=tuple(matched),
                supporting_signals=tuple(supporting),
                conflicting_signals=tuple(conflicting),
                left=left,
                right=right,
            )
        supporting.append("sku_cross_source_only")

    if (
        left.normalized_title
        and left.normalized_title == right.normalized_title
    ):
        supporting.append("title_exact")

    if shared_makers:
        supporting.append("maker_overlap")

    return ResolutionDecision(
        outcome="insufficient",
        reason=(
            "supporting_signals_only"
            if supporting
            else "no_identity_match"
        ),
        matched_signals=tuple(matched),
        supporting_signals=tuple(supporting),
        conflicting_signals=tuple(conflicting),
        left=left,
        right=right,
    )
