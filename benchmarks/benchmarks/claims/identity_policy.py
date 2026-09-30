"""C3/C4 coupled-identity policy and metamorphic qualification.

The fixtures in this module are deliberately small and hand-declared.  They
exercise CALM's exact primitive coupled-pair identity directly, without running
surface-cell enumeration.  Every expected equivalence, distinction, or policy
rejection is specified independently of the production result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ._support import matrix_payload, write_csv_atomic, write_jsonl_atomic
from .claim_ids import ClaimId, ClaimStatus
from .manifest import (
    artifact_record,
    build_manifest,
    canonical_json_bytes,
    sha256_bytes,
    write_json_atomic,
)
from .schemas import (
    ClaimResult,
    IdentityPolicyObservation,
    MetamorphicObservation,
)


IDENTITY_POLICY_SUMMARY_SCHEMA = "calm.identity_policy_qualification/v1"
IDENTITY_CLASSIFICATION_SCHEMA = "calm.identity_classification/v1"
DEFAULT_PROFILE = "standard"
SUPPORTED_PROFILES = ("smoke", "standard")
IDENTITY_ALGORITHM = "primitive_coupled_pair_v2"

IDENTITY_PAIR_KEY_FULL = (-1, 0, 0, -1, 1, 0, 0, 1)
SIGMA5_PAIR_KEY_FULL = (-4, -3, -3, -1, 5, 3, 0, 1)

I2 = np.eye(2, dtype=int)
SHEAR = np.array([[1, 1], [0, 1]], dtype=int)
ROTATION_90 = np.array([[0, -1], [1, 0]], dtype=int)
ROTATION_180 = ROTATION_90 @ ROTATION_90
REFLECTION = np.array([[1, 0], [0, -1]], dtype=int)
SIGMA5_A = np.array([[2, -1], [1, 2]], dtype=int)
SIGMA5_B = np.array([[2, 1], [-1, 2]], dtype=int)
COMMON_RIGHT_PROPER = np.array([[2, 1], [1, 1]], dtype=int)
COMMON_RIGHT_IMPROPER = np.array([[0, 1], [1, 0]], dtype=int)
REPEAT_FACTOR_TWO = np.array([[2, 0], [0, 1]], dtype=int)


def _stack(block_a: np.ndarray, block_b: np.ndarray) -> np.ndarray:
    return np.vstack([np.asarray(block_a, dtype=int), np.asarray(block_b, dtype=int)])


def _determinant(matrix: np.ndarray) -> int:
    array = np.asarray(matrix, dtype=object)
    return int(array[0, 0]) * int(array[1, 1]) - int(array[0, 1]) * int(
        array[1, 0]
    )


def identity_group() -> tuple[np.ndarray, ...]:
    return (I2.copy(),)


def full_square_group() -> tuple[np.ndarray, ...]:
    rotations = (
        I2,
        ROTATION_90,
        ROTATION_180,
        ROTATION_180 @ ROTATION_90,
    )
    operations: dict[tuple[int, int, int, int], np.ndarray] = {}
    for rotation in rotations:
        for operation in (rotation, REFLECTION @ rotation):
            key = tuple(int(value) for value in operation.ravel())
            operations[key] = np.asarray(operation, dtype=int)
    return tuple(operations[key] for key in sorted(operations))


def _policy(
    *,
    pair_symmetry: str = "full",
    correspondence_orientation: str = "proper",
    identify_material_exchange: bool = False,
) -> dict[str, Any]:
    return {
        "key_version": 1,
        "pair_symmetry_policy": pair_symmetry,
        "correspondence_orientation": correspondence_orientation,
        "material_exchange_identified": identify_material_exchange,
    }


def _policy_object(policy: Mapping[str, Any]):
    from calm.interface.matching._types import PairIdentityPolicy2D

    return PairIdentityPolicy2D(
        pair_symmetry=str(policy["pair_symmetry_policy"]),
        correspondence_orientation=str(policy["correspondence_orientation"]),
        identify_material_exchange=bool(
            policy["material_exchange_identified"]
        ),
        key_version=int(policy["key_version"]),
    )


def _group_payload(group: Sequence[np.ndarray]) -> list[list[list[int]]]:
    return [matrix_payload(operation) for operation in group]


def _classification_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    selected = {
        "schema": payload["schema"],
        "status": payload["status"],
        "source_pair_matrix": payload["source_pair_matrix"],
        "source_determinants": payload["source_determinants"],
        "relative_orientation_sign": payload["relative_orientation_sign"],
        "policy": payload["policy"],
        "point_group_A": payload["point_group_A"],
        "point_group_B": payload["point_group_B"],
    }
    for key in (
        "primitive_pair_key",
        "primitive_pair_key_sha256",
        "primitive_matrix",
        "canonical_matrix",
        "repeat_index",
        "source_right_factor",
        "canonicalization_witness",
        "error",
    ):
        if key in payload:
            selected[key] = payload[key]
    return selected


def classify_source_pair(
    source_pair: np.ndarray,
    *,
    policy: Mapping[str, Any],
    point_group_a: Sequence[np.ndarray],
    point_group_b: Sequence[np.ndarray],
) -> dict[str, Any]:
    """Classify one exact source pair under the complete declared policy."""

    from calm.interface.matching._pair_identity import (
        canonicalize_primitive_pair_2d,
    )
    from calm.math2d.paired_lattice import primitiveize_pair_matrix_2d

    source = np.asarray(source_pair)
    if source.shape != (4, 2):
        raise ValueError("source_pair must have shape (4, 2)")
    if source.dtype.kind not in {"i", "u", "O"}:
        raise TypeError("source_pair must contain exact integers")
    exact = np.asarray(source, dtype=int)
    determinant_a = _determinant(exact[:2])
    determinant_b = _determinant(exact[2:])
    if determinant_a == 0 or determinant_b == 0:
        raise ValueError("both source blocks must be nonsingular")
    orientation_sign = 1 if determinant_a * determinant_b > 0 else -1
    policy_payload = dict(policy)
    base = {
        "schema": IDENTITY_CLASSIFICATION_SCHEMA,
        "identity_algorithm": IDENTITY_ALGORITHM,
        "source_pair_matrix": matrix_payload(exact),
        "source_pair_sha256": sha256_bytes(canonical_json_bytes(matrix_payload(exact))),
        "source_determinants": {
            "A": determinant_a,
            "B": determinant_b,
        },
        "relative_orientation_sign": orientation_sign,
        "policy": policy_payload,
        "point_group_A": _group_payload(point_group_a),
        "point_group_B": _group_payload(point_group_b),
    }
    if (
        policy_payload["correspondence_orientation"] == "proper"
        and orientation_sign < 0
    ):
        return {**base, "status": "orientation_rejected"}

    try:
        factorization = primitiveize_pair_matrix_2d(exact)
        primitive = np.asarray(factorization.primitive_matrix, dtype=int)
        result = canonicalize_primitive_pair_2d(
            primitive,
            point_group_A=tuple(point_group_a),
            point_group_B=tuple(point_group_b),
            policy=_policy_object(policy_payload),
        )
        key = tuple(int(value) for value in result.key)
        canonical = np.asarray(result.canonical_matrix, dtype=int)
        right = np.asarray(result.common_right_transform, dtype=int)
        transformed = np.vstack(
            [
                np.asarray(result.point_operation_A, dtype=int) @ primitive[:2],
                np.asarray(result.point_operation_B, dtype=int) @ primitive[2:],
            ]
        )
        reconstructed = transformed @ right
        return {
            **base,
            "status": "projected",
            "primitive_pair_key": list(key),
            "primitive_pair_key_sha256": sha256_bytes(
                canonical_json_bytes(list(key))
            ),
            "primitive_matrix": matrix_payload(primitive),
            "canonical_matrix": matrix_payload(canonical),
            "repeat_index": int(factorization.repeat_index),
            "source_right_factor": matrix_payload(
                np.asarray(factorization.source_right_factor, dtype=int)
            ),
            "primitiveization_verified": bool(
                np.array_equal(
                    primitive
                    @ np.asarray(factorization.source_right_factor, dtype=int),
                    exact,
                )
            ),
            "canonicalization_witness": {
                "point_operation_A": matrix_payload(
                    np.asarray(result.point_operation_A, dtype=int)
                ),
                "point_operation_B": matrix_payload(
                    np.asarray(result.point_operation_B, dtype=int)
                ),
                "common_right_transform": matrix_payload(right),
                "common_right_determinant": _determinant(right),
                "pivot_rows": list(result.pivot_rows),
                "material_exchange_applied": bool(
                    result.material_exchange_applied
                ),
                "reconstruction_verified": bool(
                    np.array_equal(reconstructed, canonical)
                ),
            },
        }
    except (TypeError, ValueError, RuntimeError) as exc:
        return {
            **base,
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _actual_relation(
    baseline: Mapping[str, Any],
    variant: Mapping[str, Any],
) -> str:
    baseline_status = baseline["status"]
    variant_status = variant["status"]
    if baseline_status != "projected":
        return f"baseline_{baseline_status}"
    if variant_status == "orientation_rejected":
        return "variant_rejected"
    if variant_status != "projected":
        return f"variant_{variant_status}"
    return (
        "equivalent"
        if baseline["primitive_pair_key"] == variant["primitive_pair_key"]
        else "distinct"
    )


def _identity_observation(
    *,
    observation_id: str,
    claim_id: ClaimId,
    category: str,
    expected_outcome: str,
    baseline_matrix: np.ndarray,
    variant_matrix: np.ndarray,
    policy: Mapping[str, Any],
    baseline_group_a: Sequence[np.ndarray],
    baseline_group_b: Sequence[np.ndarray],
    variant_group_a: Sequence[np.ndarray] | None = None,
    variant_group_b: Sequence[np.ndarray] | None = None,
    expected_baseline_key: Sequence[int] | None = None,
    expected_variant_key: Sequence[int] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> IdentityPolicyObservation:
    baseline = classify_source_pair(
        baseline_matrix,
        policy=policy,
        point_group_a=baseline_group_a,
        point_group_b=baseline_group_b,
    )
    variant = classify_source_pair(
        variant_matrix,
        policy=policy,
        point_group_a=(
            baseline_group_a if variant_group_a is None else variant_group_a
        ),
        point_group_b=(
            baseline_group_b if variant_group_b is None else variant_group_b
        ),
    )
    actual = _actual_relation(baseline, variant)
    key_checks: dict[str, bool] = {}
    if expected_baseline_key is not None:
        key_checks["baseline_expected_key_match"] = (
            baseline.get("primitive_pair_key")
            == [int(value) for value in expected_baseline_key]
        )
    if expected_variant_key is not None:
        key_checks["variant_expected_key_match"] = (
            variant.get("primitive_pair_key")
            == [int(value) for value in expected_variant_key]
        )
    passed = actual == expected_outcome and all(key_checks.values())
    return IdentityPolicyObservation(
        observation_id=observation_id,
        claim_id=claim_id,
        category=category,
        expected_outcome=expected_outcome,
        actual_outcome=actual,
        passed=passed,
        policy=dict(policy),
        baseline=_classification_summary(baseline),
        variant=_classification_summary(variant),
        diagnostics={**dict(diagnostics or {}), **key_checks},
    )


def _metamorphic_observation(
    *,
    observation_id: str,
    transformation: str,
    expected_relation: str,
    baseline_matrix: np.ndarray,
    transformed_matrix: np.ndarray,
    policy: Mapping[str, Any],
    baseline_group_a: Sequence[np.ndarray],
    baseline_group_b: Sequence[np.ndarray],
    transformed_group_a: Sequence[np.ndarray] | None = None,
    transformed_group_b: Sequence[np.ndarray] | None = None,
    expected_transformed_repeat_index: int | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> MetamorphicObservation:
    baseline = classify_source_pair(
        baseline_matrix,
        policy=policy,
        point_group_a=baseline_group_a,
        point_group_b=baseline_group_b,
    )
    transformed = classify_source_pair(
        transformed_matrix,
        policy=policy,
        point_group_a=(
            baseline_group_a
            if transformed_group_a is None
            else transformed_group_a
        ),
        point_group_b=(
            baseline_group_b
            if transformed_group_b is None
            else transformed_group_b
        ),
    )
    actual = _actual_relation(baseline, transformed)
    repeat_check = True
    if expected_transformed_repeat_index is not None:
        repeat_check = transformed.get("repeat_index") == int(
            expected_transformed_repeat_index
        )
    passed = actual == expected_relation and repeat_check
    return MetamorphicObservation(
        observation_id=observation_id,
        transformation=transformation,
        expected_relation=expected_relation,
        actual_relation=actual,
        passed=passed,
        policy=dict(policy),
        baseline=_classification_summary(baseline),
        transformed=_classification_summary(transformed),
        diagnostics={
            **dict(diagnostics or {}),
            "expected_transformed_repeat_index": expected_transformed_repeat_index,
            "transformed_repeat_index_match": repeat_check,
        },
    )


def _identity_observations(profile: str) -> tuple[IdentityPolicyObservation, ...]:
    identity = identity_group()
    d4 = full_square_group()
    identity_pair = _stack(I2, I2)
    shear_pair = _stack(I2, SHEAR)
    swapped_pair = _stack(SHEAR, I2)
    sigma5_pair = _stack(SIGMA5_A, SIGMA5_B)
    reflected_sigma5 = _stack(REFLECTION @ SIGMA5_A, SIGMA5_B)
    independently_changed = _stack(I2, SHEAR)
    left_rotated = _stack(ROTATION_90, SHEAR)
    mirrored_pair = _stack(I2, REFLECTION)

    c3_observations = [
        _identity_observation(
            observation_id="C3.identity_vs_sigma5_full_d4",
            claim_id=ClaimId.C3_COUPLED_IDENTITY,
            category="physically_distinct_relationships",
            expected_outcome="distinct",
            baseline_matrix=identity_pair,
            variant_matrix=sigma5_pair,
            policy=_policy(),
            baseline_group_a=d4,
            baseline_group_b=d4,
            expected_baseline_key=IDENTITY_PAIR_KEY_FULL,
            expected_variant_key=SIGMA5_PAIR_KEY_FULL,
            diagnostics={
                "hand_declared_reason": (
                    "primitive identity and primitive Sigma5 are distinct "
                    "coupled relationships even though both use square parents"
                )
            },
        ),
        _identity_observation(
            observation_id="C3.independent_right_change_not_common",
            claim_id=ClaimId.C3_COUPLED_IDENTITY,
            category="forbidden_independent_basis_change",
            expected_outcome="distinct",
            baseline_matrix=identity_pair,
            variant_matrix=independently_changed,
            policy=_policy(),
            baseline_group_a=identity,
            baseline_group_b=identity,
            diagnostics={
                "hand_declared_reason": (
                    "only one common interface-cell basis relabeling is "
                    "admissible; changing B independently changes the coupling"
                )
            },
        ),
        _identity_observation(
            observation_id="C3.ordered_material_swap_distinct",
            claim_id=ClaimId.C3_COUPLED_IDENTITY,
            category="ordered_material_identity",
            expected_outcome="distinct",
            baseline_matrix=shear_pair,
            variant_matrix=swapped_pair,
            policy=_policy(identify_material_exchange=False),
            baseline_group_a=identity,
            baseline_group_b=identity,
            diagnostics={
                "hand_declared_reason": (
                    "A/B exchange is distinct when materials are ordered"
                )
            },
        ),
        _identity_observation(
            observation_id="C3.unadmitted_left_rotation_distinct",
            claim_id=ClaimId.C3_COUPLED_IDENTITY,
            category="explicit_surface_group_boundary",
            expected_outcome="distinct",
            baseline_matrix=shear_pair,
            variant_matrix=left_rotated,
            policy=_policy(),
            baseline_group_a=identity,
            baseline_group_b=identity,
            diagnostics={
                "hand_declared_reason": (
                    "a left action is not an equivalence unless the operation "
                    "is explicitly admitted by the parent surface group"
                )
            },
        ),
    ]

    c4_observations = [
        _identity_observation(
            observation_id="C4.reflection_merges_under_full_symmetry",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="pair_symmetry_policy",
            expected_outcome="equivalent",
            baseline_matrix=sigma5_pair,
            variant_matrix=reflected_sigma5,
            policy=_policy(
                pair_symmetry="full",
                correspondence_orientation="all",
            ),
            baseline_group_a=d4,
            baseline_group_b=d4,
        ),
        _identity_observation(
            observation_id="C4.reflection_distinct_under_proper_symmetry",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="pair_symmetry_policy",
            expected_outcome="distinct",
            baseline_matrix=sigma5_pair,
            variant_matrix=reflected_sigma5,
            policy=_policy(
                pair_symmetry="proper",
                correspondence_orientation="all",
            ),
            baseline_group_a=d4,
            baseline_group_b=d4,
        ),
        _identity_observation(
            observation_id="C4.exchange_merges_only_when_enabled",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="material_exchange_policy",
            expected_outcome="equivalent",
            baseline_matrix=shear_pair,
            variant_matrix=swapped_pair,
            policy=_policy(identify_material_exchange=True),
            baseline_group_a=identity,
            baseline_group_b=identity,
        ),
        _identity_observation(
            observation_id="C4.exchange_remains_distinct_when_disabled",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="material_exchange_policy",
            expected_outcome="distinct",
            baseline_matrix=shear_pair,
            variant_matrix=swapped_pair,
            policy=_policy(identify_material_exchange=False),
            baseline_group_a=identity,
            baseline_group_b=identity,
        ),
        _identity_observation(
            observation_id="C4.mirrored_correspondence_rejected_when_proper",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="correspondence_orientation_policy",
            expected_outcome="variant_rejected",
            baseline_matrix=identity_pair,
            variant_matrix=mirrored_pair,
            policy=_policy(correspondence_orientation="proper"),
            baseline_group_a=identity,
            baseline_group_b=identity,
        ),
        _identity_observation(
            observation_id="C4.mirrored_correspondence_admitted_when_all",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="correspondence_orientation_policy",
            expected_outcome="distinct",
            baseline_matrix=identity_pair,
            variant_matrix=mirrored_pair,
            policy=_policy(correspondence_orientation="all"),
            baseline_group_a=identity,
            baseline_group_b=identity,
            diagnostics={"variant_expected_status": "projected"},
        ),
        _identity_observation(
            observation_id="C4.left_rotation_merges_when_group_admits_it",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="surface_group_policy",
            expected_outcome="equivalent",
            baseline_matrix=shear_pair,
            variant_matrix=left_rotated,
            policy=_policy(),
            baseline_group_a=d4,
            baseline_group_b=d4,
        ),
        _identity_observation(
            observation_id="C4.left_rotation_distinct_when_group_omits_it",
            claim_id=ClaimId.C4_REPRESENTATION_INVARIANCE,
            category="surface_group_policy",
            expected_outcome="distinct",
            baseline_matrix=shear_pair,
            variant_matrix=left_rotated,
            policy=_policy(),
            baseline_group_a=identity,
            baseline_group_b=identity,
        ),
    ]
    if profile == "smoke":
        return tuple((*c3_observations[:2], *c4_observations[:3]))
    return tuple((*c3_observations, *c4_observations))


def _metamorphic_observations(profile: str) -> tuple[MetamorphicObservation, ...]:
    identity = identity_group()
    d4 = full_square_group()
    shear_pair = _stack(I2, SHEAR)
    admitted_left = _stack(ROTATION_90, ROTATION_180 @ SHEAR)

    observations = [
        _metamorphic_observation(
            observation_id="C4.common_right_proper_invariance",
            transformation="common right GL(2,Z) relabeling with determinant +1",
            expected_relation="equivalent",
            baseline_matrix=shear_pair,
            transformed_matrix=shear_pair @ COMMON_RIGHT_PROPER,
            policy=_policy(),
            baseline_group_a=identity,
            baseline_group_b=identity,
        ),
        _metamorphic_observation(
            observation_id="C4.nonprimitive_repetition_invariance",
            transformation="nonprimitive common-right repetition followed by saturation",
            expected_relation="equivalent",
            baseline_matrix=shear_pair,
            transformed_matrix=shear_pair @ REPEAT_FACTOR_TWO,
            policy=_policy(),
            baseline_group_a=identity,
            baseline_group_b=identity,
            expected_transformed_repeat_index=2,
        ),
        _metamorphic_observation(
            observation_id="C4.independent_admitted_left_operations",
            transformation="independent admitted A- and B-side surface operations",
            expected_relation="equivalent",
            baseline_matrix=shear_pair,
            transformed_matrix=admitted_left,
            policy=_policy(),
            baseline_group_a=d4,
            baseline_group_b=d4,
        ),
    ]
    if profile == "smoke":
        return tuple(observations)

    reversed_duplicate_d4 = tuple(reversed(d4)) + (I2.copy(),)
    baseline = classify_source_pair(
        shear_pair,
        policy=_policy(correspondence_orientation="all"),
        point_group_a=d4,
        point_group_b=d4,
    )
    canonical_matrix = np.asarray(baseline["canonical_matrix"], dtype=int)
    observations.extend(
        [
            _metamorphic_observation(
                observation_id="C4.common_right_improper_invariance",
                transformation=(
                    "common right GL(2,Z) relabeling with determinant -1"
                ),
                expected_relation="equivalent",
                baseline_matrix=shear_pair,
                transformed_matrix=shear_pair @ COMMON_RIGHT_IMPROPER,
                policy=_policy(),
                baseline_group_a=identity,
                baseline_group_b=identity,
            ),
            _metamorphic_observation(
                observation_id="C4.surface_group_order_and_duplicate_invariance",
                transformation=(
                    "reorder admitted point-group operations and repeat identity"
                ),
                expected_relation="equivalent",
                baseline_matrix=shear_pair,
                transformed_matrix=shear_pair,
                policy=_policy(),
                baseline_group_a=d4,
                baseline_group_b=d4,
                transformed_group_a=reversed_duplicate_d4,
                transformed_group_b=reversed_duplicate_d4,
            ),
            _metamorphic_observation(
                observation_id="C4.canonicalization_idempotence",
                transformation="reclassify the returned canonical matrix",
                expected_relation="equivalent",
                baseline_matrix=shear_pair,
                transformed_matrix=canonical_matrix,
                policy=_policy(correspondence_orientation="all"),
                baseline_group_a=d4,
                baseline_group_b=d4,
            ),
        ]
    )
    return tuple(observations)


@dataclass(frozen=True)
class IdentityPolicyConfig:
    profile: str = DEFAULT_PROFILE

    def __post_init__(self) -> None:
        if self.profile not in SUPPORTED_PROFILES:
            raise ValueError(
                f"profile must be one of {', '.join(SUPPORTED_PROFILES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"profile": self.profile}


def _observation_spec_hash(observation: Mapping[str, Any]) -> str:
    stable = {
        key: observation[key]
        for key in (
            "schema",
            "observation_id",
            "claim_id",
            "category",
            "transformation",
            "expected_outcome",
            "expected_relation",
            "policy",
        )
        if key in observation
    }
    for side in ("baseline", "variant", "transformed"):
        if side in observation:
            stable[side] = {
                "source_pair_matrix": observation[side]["source_pair_matrix"],
                "policy": observation[side]["policy"],
                "point_group_A": observation[side]["point_group_A"],
                "point_group_B": observation[side]["point_group_B"],
            }
    return sha256_bytes(canonical_json_bytes(stable))


@dataclass(frozen=True)
class IdentityPolicyArtifacts:
    manifest: Path
    summary: Path
    identity_observations: Path
    metamorphic_observations: Path
    summary_csv: Path
    claim_result_paths: tuple[Path, ...]
    results: tuple[ClaimResult, ...]

    @property
    def evidence_paths(self) -> tuple[Path, ...]:
        return (
            self.summary,
            self.identity_observations,
            self.metamorphic_observations,
            self.summary_csv,
        )


def run_identity_policy_qualification(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    config: IdentityPolicyConfig,
    selected_claims: Sequence[ClaimId] = (
        ClaimId.C3_COUPLED_IDENTITY,
        ClaimId.C4_REPRESENTATION_INVARIANCE,
    ),
) -> IdentityPolicyArtifacts:
    """Execute hand-declared C3/C4 identity and metamorphic expectations."""

    selected = tuple(selected_claims)
    allowed = {
        ClaimId.C3_COUPLED_IDENTITY,
        ClaimId.C4_REPRESENTATION_INVARIANCE,
    }
    if not selected or any(claim not in allowed for claim in selected):
        raise ValueError("selected_claims must be a nonempty subset of C3 and C4")

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    identity_observations = tuple(
        observation
        for observation in _identity_observations(config.profile)
        if observation.claim_id in selected
    )
    metamorphic_observations = (
        _metamorphic_observations(config.profile)
        if ClaimId.C4_REPRESENTATION_INVARIANCE in selected
        else ()
    )

    identity_rows = tuple(observation.to_dict() for observation in identity_observations)
    metamorphic_rows = tuple(
        observation.to_dict() for observation in metamorphic_observations
    )
    identity_path = write_jsonl_atomic(
        root / "identity_policy_observations.jsonl",
        identity_rows,
    )
    metamorphic_path = write_jsonl_atomic(
        root / "metamorphic_observations.jsonl",
        metamorphic_rows,
    )

    all_rows = (*identity_rows, *metamorphic_rows)
    summary_rows = tuple(
        {
            "observation_id": row["observation_id"],
            "claim_id": row["claim_id"],
            "kind": (
                "identity_policy"
                if "expected_outcome" in row
                else "metamorphic"
            ),
            "category_or_transformation": row.get(
                "category", row.get("transformation")
            ),
            "expected": row.get("expected_outcome", row.get("expected_relation")),
            "actual": row.get("actual_outcome", row.get("actual_relation")),
            "passed": row["passed"],
        }
        for row in all_rows
    )
    summary_csv_path = write_csv_atomic(
        root / "identity_policy_summary.csv",
        summary_rows,
    )

    results: list[ClaimResult] = []
    claim_result_paths: list[Path] = []
    for claim_id in selected:
        rows = tuple(row for row in all_rows if row["claim_id"] == claim_id.value)
        passed_count = sum(bool(row["passed"]) for row in rows)
        all_passed = passed_count == len(rows) and bool(rows)
        if claim_id is ClaimId.C3_COUPLED_IDENTITY:
            summary = (
                "All hand-declared physically distinct coupled A/B relationships "
                "remain distinct under the selected policies."
                if all_passed
                else "One or more hand-declared distinct coupled relationships "
                "were incorrectly merged or failed classification."
            )
            notes = (
                "Expected distinctions are hand-declared rather than generated "
                "from the production canonicalizer.",
                "Anchor keys for primitive identity and primitive Sigma5 are "
                "frozen from the independent equal-square reference.",
            )
        else:
            summary = (
                "All equivalent descriptions merge, and policy-sensitive "
                "descriptions change only under the explicitly selected policy."
                if all_passed
                else "One or more representation or policy metamorphic "
                "expectations failed."
            )
            notes = (
                "The suite covers common-right GL(2,Z) actions, saturation, "
                "admitted surface operations, group ordering, idempotence, "
                "reflection, correspondence orientation, and material exchange.",
                "Primitive-parent basis reparameterization and Cartesian rotation "
                "are qualified at the search level by C2 rather than duplicated "
                "inside the pair-identity stage.",
            )
        evidence_files = (
            (
                "identity_policy_summary.json",
                "identity_policy_observations.jsonl",
                "identity_policy_summary.csv",
            )
            if claim_id is ClaimId.C3_COUPLED_IDENTITY
            else (
                "identity_policy_summary.json",
                "identity_policy_observations.jsonl",
                "metamorphic_observations.jsonl",
                "identity_policy_summary.csv",
            )
        )
        result = ClaimResult(
            claim_id=claim_id,
            status=ClaimStatus.PASS if all_passed else ClaimStatus.FAIL,
            summary=summary,
            evidence_files=evidence_files,
            metrics={
                "observation_count": len(rows),
                "passed_count": passed_count,
                "failure_count": len(rows) - passed_count,
            },
            notes=notes,
        )
        results.append(result)
        claim_result_paths.append(
            write_json_atomic(root / f"claim_result_{claim_id.value}.json", result.to_dict())
        )

    summary_payload = {
        "schema": IDENTITY_POLICY_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "identity_algorithm": IDENTITY_ALGORITHM,
        "config": config.to_dict(),
        "selected_claims": [claim.value for claim in selected],
        "claim_results": [result.to_dict() for result in results],
        "observation_count": len(all_rows),
        "passed_count": sum(bool(row["passed"]) for row in all_rows),
        "all_passed": all(bool(row["passed"]) for row in all_rows),
        "identity_policy_observation_count": len(identity_rows),
        "metamorphic_observation_count": len(metamorphic_rows),
        "interpretation": {
            "expected_relations": "hand-declared before production evaluation",
            "identity_equivalence": "diag(P_A,P_B) M U with one common U",
            "primitiveization": "direct saturation of the stacked 4x2 source pair",
            "legacy_suite_modified": False,
        },
        "observations": list(summary_rows),
    }
    summary_path = write_json_atomic(
        root / "identity_policy_summary.json",
        summary_payload,
    )

    artifacts = [
        artifact_record(summary_path, relative_to=root, media_type="application/json"),
        artifact_record(identity_path, relative_to=root, media_type="application/x-ndjson"),
        artifact_record(metamorphic_path, relative_to=root, media_type="application/x-ndjson"),
        artifact_record(summary_csv_path, relative_to=root, media_type="text/csv"),
    ]
    artifacts.extend(
        artifact_record(path, relative_to=root, media_type="application/json")
        for path in claim_result_paths
    )
    fixture_hashes = {
        row["observation_id"]: _observation_spec_hash(row) for row in all_rows
    }
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=selected,
        artifacts=tuple(artifacts),
        fixture_hashes=fixture_hashes,
        policy_settings={
            "identity_algorithm": IDENTITY_ALGORITHM,
            "profiles": list(SUPPORTED_PROFILES),
            "selected_profile": config.profile,
            "expected_relations_are_hand_declared": True,
        },
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return IdentityPolicyArtifacts(
        manifest=manifest_path,
        summary=summary_path,
        identity_observations=identity_path,
        metamorphic_observations=metamorphic_path,
        summary_csv=summary_csv_path,
        claim_result_paths=tuple(claim_result_paths),
        results=tuple(results),
    )


__all__ = [
    "DEFAULT_PROFILE",
    "IDENTITY_ALGORITHM",
    "IDENTITY_CLASSIFICATION_SCHEMA",
    "IDENTITY_POLICY_SUMMARY_SCHEMA",
    "IdentityPolicyArtifacts",
    "IdentityPolicyConfig",
    "classify_source_pair",
    "full_square_group",
    "identity_group",
    "run_identity_policy_qualification",
]
