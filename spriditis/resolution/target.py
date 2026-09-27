from __future__ import annotations

import re
from dataclasses import dataclass

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.resolution.identity import normalize_text


_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _tokens(value: object) -> list[str]:
    return _TOKEN_RE.findall(normalize_text(value))


def _normalized_terms(values: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        for token in _tokens(value):
            if token in seen:
                continue
            seen.add(token)
            result.append(token)

    return tuple(result)


def _identity_tokens(entity: MarketEntity) -> set[str]:
    values: list[object] = [entity.title]

    attributes = {
        str(key).casefold(): value
        for key, value in entity.attributes.items()
    }

    for key in (
        "brand",
        "manufacturer",
        "model",
        "model_number",
        "mpn",
        "sku",
        "gtin",
    ):
        value = attributes.get(key)
        if value not in (None, ""):
            values.append(value)

    tokens: set[str] = set()
    for value in values:
        tokens.update(_tokens(value))

    return tokens


def _modelish_tokens(tokens: set[str]) -> set[str]:
    return {
        token
        for token in tokens
        if any(char.isdigit() for char in token)
    }


@dataclass(frozen=True)
class TargetIdentityDecision:
    outcome: str
    reason: str
    required_terms: tuple[str, ...] = ()
    anchor_terms: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()
    missing_terms: tuple[str, ...] = ()
    candidate_model_terms: tuple[str, ...] = ()


def evaluate_target_identity(
    entity: MarketEntity,
    project: ResearchProject,
) -> TargetIdentityDecision:
    required_terms = _normalized_terms(
        project.analysis.target_identity_terms
    )
    anchor_terms = _normalized_terms(
        project.analysis.target_identity_anchor_terms
    )

    if not required_terms or not anchor_terms:
        return TargetIdentityDecision(
            outcome="not_evaluated",
            reason="no_target_identity",
        )

    identity_tokens = _identity_tokens(entity)

    matched_terms = tuple(
        term for term in required_terms if term in identity_tokens
    )
    missing_terms = tuple(
        term for term in required_terms if term not in identity_tokens
    )

    matched_anchors = {
        term for term in anchor_terms if term in identity_tokens
    }

    if not missing_terms:
        return TargetIdentityDecision(
            outcome="confirmed",
            reason="target_identity_exact",
            required_terms=required_terms,
            anchor_terms=anchor_terms,
            matched_terms=matched_terms,
            missing_terms=(),
            candidate_model_terms=tuple(
                sorted(_modelish_tokens(identity_tokens))
            ),
        )

    if matched_anchors == set(anchor_terms):
        return TargetIdentityDecision(
            outcome="uncertain",
            reason="target_identity_incomplete",
            required_terms=required_terms,
            anchor_terms=anchor_terms,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
            candidate_model_terms=tuple(
                sorted(_modelish_tokens(identity_tokens))
            ),
        )

    candidate_model_terms = _modelish_tokens(identity_tokens)
    target_model_terms = _modelish_tokens(set(anchor_terms))

    reason = (
        "target_model_conflict"
        if target_model_terms and candidate_model_terms
        else "target_model_missing"
    )

    return TargetIdentityDecision(
        outcome="rejected",
        reason=reason,
        required_terms=required_terms,
        anchor_terms=anchor_terms,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
        candidate_model_terms=tuple(sorted(candidate_model_terms)),
    )


def apply_target_identity_gate(
    entity: MarketEntity,
    project: ResearchProject,
) -> MarketEntity:
    decision = evaluate_target_identity(entity, project)

    if decision.outcome == "not_evaluated":
        return entity

    attributes = dict(entity.attributes)
    attributes.update(
        {
            "target_identity_status": decision.outcome,
            "target_identity_reason": decision.reason,
            "target_identity_required_terms": list(
                decision.required_terms
            ),
            "target_identity_anchor_terms": list(
                decision.anchor_terms
            ),
            "target_identity_matched_terms": list(
                decision.matched_terms
            ),
            "target_identity_missing_terms": list(
                decision.missing_terms
            ),
            "target_identity_candidate_model_terms": list(
                decision.candidate_model_terms
            ),
        }
    )

    return entity.model_copy(
        update={
            "is_relevant": (
                entity.is_relevant
                and decision.outcome == "confirmed"
            ),
            "attributes": attributes,
        }
    )
