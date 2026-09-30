"""Project reconstructed ZSL source pairs onto CALM coupled identity."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from calm.interface.matching._pair_identity import canonicalize_primitive_pair_2d
from calm.interface.matching._types import PairIdentityPolicy2D
from calm.interface.model import PairIdentity2D
from calm.math2d.paired_lattice import primitiveize_pair_matrix_2d
from calm.symmetry.surface_group import (
    metric_preservation_residual,
    validate_surface_symmetry_group_2d,
)

from ..manifest import canonical_json_bytes, sha256_bytes
from ..schemas import ProjectedMatch, RawExternalMatch
from .metric_projection import fixture_id, gram_from_row_vectors, source_match_id


PROJECTION_KIND = "zsl_primitive_coupled_pair_v1"
IDENTITY_ALGORITHM = "primitive_coupled_pair_v2"


def identity_point_group() -> tuple[np.ndarray, ...]:
    return (np.eye(2, dtype=int),)


def _projection_dict(
    reconstruction: ProjectedMatch | Mapping[str, Any],
) -> Mapping[str, Any]:
    return (
        reconstruction.to_dict()
        if isinstance(reconstruction, ProjectedMatch)
        else reconstruction
    )


def _exact_matrix(value: Any, *, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2)")
    if array.dtype.kind not in {"i", "u", "O"}:
        raise TypeError(f"{name} must contain exact integers")
    output = np.empty((2, 2), dtype=object)
    for index, entry in np.ndenumerate(array):
        if isinstance(entry, (bool, np.bool_)) or not isinstance(
            entry,
            (int, np.integer),
        ):
            raise TypeError(f"{name} must contain exact integers")
        output[index] = int(entry)
    return output


def _determinant(matrix: np.ndarray) -> int:
    return int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(
        matrix[1, 0]
    )


def _digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _raw_fields(raw: RawExternalMatch | Mapping[str, Any]) -> Mapping[str, Any]:
    record = raw.to_dict() if isinstance(raw, RawExternalMatch) else raw
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        return {}
    fields = payload.get("fields")
    return fields if isinstance(fields, Mapping) else {}


def _policy_dict(policy: PairIdentityPolicy2D) -> dict[str, Any]:
    return {
        "key_version": int(policy.key_version),
        "pair_symmetry_policy": policy.pair_symmetry,
        "correspondence_orientation": policy.correspondence_orientation,
        "material_exchange_identified": bool(
            policy.identify_material_exchange
        ),
    }


def _validated_group(
    operations: Sequence[np.ndarray] | None,
    *,
    metric: np.ndarray,
    metric_tolerance: float,
) -> tuple[np.ndarray, ...]:
    selected = identity_point_group() if operations is None else tuple(operations)
    return validate_surface_symmetry_group_2d(
        selected,
        metric=metric,
        metric_tolerance=metric_tolerance,
    )


def _group_diagnostics(
    group: Sequence[np.ndarray],
    *,
    metric: np.ndarray,
) -> dict[str, Any]:
    residuals = [
        float(metric_preservation_residual(operation, metric))
        for operation in group
    ]
    return {
        "operations": [
            np.asarray(operation, dtype=int).tolist() for operation in group
        ],
        "operation_count": len(group),
        "max_metric_residual": max(residuals, default=0.0),
    }


def project_zsl_coupled_pair(
    raw: RawExternalMatch | Mapping[str, Any],
    reconstruction: ProjectedMatch | Mapping[str, Any],
    *,
    policy: PairIdentityPolicy2D,
    point_group_A: Sequence[np.ndarray] | None = None,
    point_group_B: Sequence[np.ndarray] | None = None,
    surface_metric_tolerance: float = 1.0e-8,
) -> ProjectedMatch:
    """Classify one reconstructed ZSL source pair under CALM identity.

    The returned key is a CALM projection of external output.  It does not imply
    that pymatgen itself implements primitiveization or CALM's equivalence
    relation.
    """

    if not isinstance(policy, PairIdentityPolicy2D):
        raise TypeError("policy must be a PairIdentityPolicy2D")
    if surface_metric_tolerance <= 0:
        raise ValueError("surface_metric_tolerance must be positive")

    match_id = source_match_id(raw)
    reconstruction_record = _projection_dict(reconstruction)
    if reconstruction_record.get("source_match_id") != match_id:
        raise ValueError("raw and reconstruction source_match_id values differ")

    status = reconstruction_record.get("status")
    if status != "reconstructed":
        return ProjectedMatch(
            source_match_id=match_id,
            projection_kind=PROJECTION_KIND,
            status="source_reconstruction_failed",
            diagnostics={
                "fixture_id": fixture_id(raw),
                "source_reconstruction_status": status,
                "source_reconstruction_diagnostics": reconstruction_record.get(
                    "diagnostics",
                    {},
                ),
                "policy": _policy_dict(policy),
            },
        )

    try:
        reconstruction_identity = reconstruction_record.get("identity")
        if not isinstance(reconstruction_identity, Mapping):
            raise ValueError("reconstruction identity must be a mapping")
        source_a = _exact_matrix(
            reconstruction_identity["film_integer_matrix"],
            name="film_integer_matrix",
        )
        source_b = _exact_matrix(
            reconstruction_identity["substrate_integer_matrix"],
            name="substrate_integer_matrix",
        )
        determinant_a = _determinant(source_a)
        determinant_b = _determinant(source_b)
        if determinant_a == 0 or determinant_b == 0:
            raise ValueError("source transformations must be nonsingular")
        relative_orientation_sign = 1 if determinant_a * determinant_b > 0 else -1
        source_pair = np.vstack([source_a, source_b])
        source_pair_digest = _digest(source_pair.tolist())

        if (
            policy.correspondence_orientation == "proper"
            and relative_orientation_sign < 0
        ):
            return ProjectedMatch(
                source_match_id=match_id,
                projection_kind=PROJECTION_KIND,
                status="orientation_rejected",
                identity={
                    "source_pair_matrix": source_pair.tolist(),
                    "source_pair_sha256": source_pair_digest,
                    "film_source_index": abs(determinant_a),
                    "substrate_source_index": abs(determinant_b),
                    "relative_orientation_sign": relative_orientation_sign,
                },
                diagnostics={
                    "fixture_id": fixture_id(raw),
                    "policy": _policy_dict(policy),
                    "orientation_definition": (
                        "sign(det(N_B) / det(N_A)) = sign(det(N_A) * det(N_B))"
                    ),
                },
            )

        fields = _raw_fields(raw)
        metric_a = gram_from_row_vectors(
            fields["film_vectors"],
            name="film_vectors",
        )
        metric_b = gram_from_row_vectors(
            fields["substrate_vectors"],
            name="substrate_vectors",
        )
        group_a = _validated_group(
            point_group_A,
            metric=metric_a,
            metric_tolerance=surface_metric_tolerance,
        )
        group_b = _validated_group(
            point_group_B,
            metric=metric_b,
            metric_tolerance=surface_metric_tolerance,
        )

        factorization = primitiveize_pair_matrix_2d(source_pair)
        primitive_matrix = np.asarray(factorization.primitive_matrix, dtype=int)
        canonicalization = canonicalize_primitive_pair_2d(
            primitive_matrix,
            point_group_A=group_a,
            point_group_B=group_b,
            policy=policy,
        )
        pair_identity = PairIdentity2D(
            key_version=policy.key_version,
            primitive_pair_key=canonicalization.key,
            pair_symmetry_policy=policy.pair_symmetry,
            correspondence_orientation=policy.correspondence_orientation,
            material_exchange_identified=policy.identify_material_exchange,
        ).to_dict()
        pair_key = list(canonicalization.key)
        pair_identity_digest = _digest(pair_identity)

        identity = {
            "identity_algorithm": IDENTITY_ALGORITHM,
            **pair_identity,
            "primitive_pair_key_sha256": _digest(pair_key),
            "pair_identity_sha256": pair_identity_digest,
            "source_pair_matrix": source_pair.tolist(),
            "source_pair_sha256": source_pair_digest,
            "film_source_index": abs(determinant_a),
            "substrate_source_index": abs(determinant_b),
            "relative_orientation_sign": relative_orientation_sign,
            "primitive_matrix": primitive_matrix.tolist(),
            "source_right_factor": np.asarray(
                factorization.source_right_factor,
                dtype=int,
            ).tolist(),
            "repeat_index": int(factorization.repeat_index),
            "canonical_matrix": np.asarray(
                canonicalization.canonical_matrix,
                dtype=int,
            ).tolist(),
        }
        diagnostics = {
            "fixture_id": fixture_id(raw),
            "projection_owner": "CALM",
            "external_tool_implements_this_identity": False,
            "orientation_definition": (
                "sign(det(N_B) / det(N_A)) = sign(det(N_A) * det(N_B))"
            ),
            "policy": _policy_dict(policy),
            "surface_metric_tolerance": float(surface_metric_tolerance),
            "point_group_A": _group_diagnostics(group_a, metric=metric_a),
            "point_group_B": _group_diagnostics(group_b, metric=metric_b),
            "canonicalization_witness": {
                "point_operation_A": np.asarray(
                    canonicalization.point_operation_A,
                    dtype=int,
                ).tolist(),
                "point_operation_B": np.asarray(
                    canonicalization.point_operation_B,
                    dtype=int,
                ).tolist(),
                "common_right_transform": np.asarray(
                    canonicalization.common_right_transform,
                    dtype=int,
                ).tolist(),
                "pivot_rows": list(canonicalization.pivot_rows),
                "material_exchange_applied": bool(
                    canonicalization.material_exchange_applied
                ),
            },
            "primitiveization_witness": {
                "maximal_minors": [
                    int(value) for value in factorization.maximal_minors
                ],
                "reconstruction_verified": bool(
                    np.array_equal(
                        primitive_matrix
                        @ np.asarray(factorization.source_right_factor, dtype=int),
                        source_pair,
                    )
                ),
            },
        }
        return ProjectedMatch(
            source_match_id=match_id,
            projection_kind=PROJECTION_KIND,
            status="projected",
            identity=identity,
            diagnostics=diagnostics,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        np.linalg.LinAlgError,
    ) as exc:
        return ProjectedMatch(
            source_match_id=match_id,
            projection_kind=PROJECTION_KIND,
            status="failed",
            diagnostics={
                "fixture_id": fixture_id(raw),
                "policy": _policy_dict(policy),
                "error": f"{type(exc).__name__}: {exc}",
            },
        )


__all__ = [
    "IDENTITY_ALGORITHM",
    "PROJECTION_KIND",
    "identity_point_group",
    "project_zsl_coupled_pair",
]
