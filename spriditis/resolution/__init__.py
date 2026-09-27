from .identity import (
    EntityIdentity,
    ResolutionDecision,
    extract_identity,
    normalize_gtin,
    resolve_entities,
)
from .target import (
    TargetIdentityDecision,
    apply_target_identity_gate,
    evaluate_target_identity,
)

__all__ = [
    "EntityIdentity",
    "ResolutionDecision",
    "TargetIdentityDecision",
    "apply_target_identity_gate",
    "evaluate_target_identity",
    "extract_identity",
    "normalize_gtin",
    "resolve_entities",
]
