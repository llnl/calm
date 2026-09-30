"""Stable identifiers for manuscript-facing CALM qualification claims."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClaimId(str, Enum):
    """Stable identifiers shared by benchmark code, reports, and manuscripts."""

    C1_STRAIN_DOMAIN = "C1"
    C2_FINITE_COMPLETENESS = "C2"
    C3_COUPLED_IDENTITY = "C3"
    C4_REPRESENTATION_INVARIANCE = "C4"
    C5_EXTENSION_STABILITY = "C5"
    C6_PUBLIC_API_PARITY = "C6"
    C7_ZSL_COMPARISON = "C7"
    C8_PERFORMANCE_SCALING = "C8"


class ClaimStatus(str, Enum):
    """Allowed evidence dispositions for one claim."""

    PASS = "pass"
    FAIL = "fail"
    DESCRIPTIVE_ONLY = "descriptive_only"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class ClaimDefinition:
    """Human-readable definition and evidence class for one stable claim."""

    claim_id: ClaimId
    title: str
    statement: str
    evidence_kind: str


CLAIM_REGISTRY: dict[ClaimId, ClaimDefinition] = {
    ClaimId.C1_STRAIN_DOMAIN: ClaimDefinition(
        claim_id=ClaimId.C1_STRAIN_DOMAIN,
        title="Principal-strain admissibility",
        statement=(
            "The principal-strain gate defines and enforces the declared "
            "mechanical admissibility domain."
        ),
        evidence_kind="pass_fail",
    ),
    ClaimId.C2_FINITE_COMPLETENESS: ClaimDefinition(
        claim_id=ClaimId.C2_FINITE_COMPLETENESS,
        title="Finite-domain completeness",
        statement=(
            "The production search recovers the complete primitive coupled-pair "
            "inventory within declared finite bounds."
        ),
        evidence_kind="pass_fail",
    ),
    ClaimId.C3_COUPLED_IDENTITY: ClaimDefinition(
        claim_id=ClaimId.C3_COUPLED_IDENTITY,
        title="Coupled A/B identity",
        statement=(
            "CALM preserves physically distinct coupled A/B relationships."
        ),
        evidence_kind="pass_fail",
    ),
    ClaimId.C4_REPRESENTATION_INVARIANCE: ClaimDefinition(
        claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
        title="Representation invariance",
        statement=(
            "Equivalent descriptions are merged under the declared identity "
            "policy and only under that policy."
        ),
        evidence_kind="pass_fail",
    ),
    ClaimId.C5_EXTENSION_STABILITY: ClaimDefinition(
        claim_id=ClaimId.C5_EXTENSION_STABILITY,
        title="Search-extension stability",
        statement=(
            "Extending the finite search preserves prior identities and stable "
            "first-discovery indices."
        ),
        evidence_kind="pass_fail",
    ),
    ClaimId.C6_PUBLIC_API_PARITY: ClaimDefinition(
        claim_id=ClaimId.C6_PUBLIC_API_PARITY,
        title="Public API parity",
        statement=(
            "The public project workflow returns the same scientific inventory "
            "as the production kernel."
        ),
        evidence_kind="pass_fail",
    ),
    ClaimId.C7_ZSL_COMPARISON: ClaimDefinition(
        claim_id=ClaimId.C7_ZSL_COMPARISON,
        title="Controlled ZSL comparison",
        statement=(
            "CALM and pymatgen ZSL are compared under common gates and explicit "
            "post-processing identities."
        ),
        evidence_kind="descriptive",
    ),
    ClaimId.C8_PERFORMANCE_SCALING: ClaimDefinition(
        claim_id=ClaimId.C8_PERFORMANCE_SCALING,
        title="Performance scaling",
        statement=(
            "The optimized CALM implementation provides measurable acceleration "
            "relative to the exact reference algorithm while preserving the "
            "same scientific inventory."
        ),
        evidence_kind="descriptive_with_correctness_guard",
    ),
}


def ordered_claim_ids() -> tuple[ClaimId, ...]:
    """Return claim identifiers in manuscript/report order."""

    return tuple(ClaimId)


def parse_claim_id(value: str) -> ClaimId:
    """Parse a short claim identifier such as ``C3``."""

    normalized = value.strip().upper()
    try:
        return ClaimId(normalized)
    except ValueError as exc:
        allowed = ", ".join(claim.value for claim in ordered_claim_ids())
        raise ValueError(
            f"unknown claim identifier {value!r}; expected one of {allowed}"
        ) from exc
