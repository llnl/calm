"""One-sided lattice-metric projection for retained pymatgen ZSL matches.

This projection intentionally canonicalizes the film and substrate metrics
independently.  It is therefore suitable for geometric overlap and legacy-style
``match_sig`` comparisons, but it is not a coupled A/B scientific identity.
Mechanical diagnostics are computed from the retained ZSL vector pairing before
that independent canonicalization.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from calm.symmetry.reduction import canonical_gauss_reduce_2d

from ...common_metrics import airm_distance_and_strains, zm_diagnostics_extended
from ..schemas import ProjectedMatch, RawExternalMatch


PROJECTION_KIND = "zsl_one_sided_metric_pair_v1"
METRIC_SIGNATURE_VERSION = 1


def _raw_dict(raw: RawExternalMatch | Mapping[str, Any]) -> Mapping[str, Any]:
    return raw.to_dict() if isinstance(raw, RawExternalMatch) else raw


def _payload(raw: RawExternalMatch | Mapping[str, Any]) -> Mapping[str, Any]:
    value = _raw_dict(raw).get("payload")
    return value if isinstance(value, Mapping) else {}


def _fields(raw: RawExternalMatch | Mapping[str, Any]) -> Mapping[str, Any]:
    value = _payload(raw).get("fields")
    return value if isinstance(value, Mapping) else {}


def source_match_id(raw: RawExternalMatch | Mapping[str, Any]) -> str:
    value = _payload(raw).get("source_match_id")
    if isinstance(value, str) and value.strip():
        return value
    record = _raw_dict(raw)
    return (
        f"{record.get('tool', 'external')}:{record.get('fixture_id', 'unknown')}:"
        f"{record.get('raw_index', 'unknown')}"
    )


def fixture_id(raw: RawExternalMatch | Mapping[str, Any]) -> str:
    value = _raw_dict(raw).get("fixture_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("raw external match is missing fixture_id")
    return value


def _row_vectors(value: Any, *, name: str) -> np.ndarray:
    rows = np.asarray(value, dtype=float)
    if rows.ndim != 2 or rows.shape[0] != 2 or rows.shape[1] < 2:
        raise ValueError(
            f"{name} must contain two row vectors embedded in d >= 2; "
            f"got {rows.shape}"
        )
    if not np.isfinite(rows).all():
        raise ValueError(f"{name} must contain only finite values")
    if np.linalg.matrix_rank(rows) != 2:
        raise ValueError(f"{name} must have row rank 2")
    return rows


def gram_from_row_vectors(value: Any, *, name: str) -> np.ndarray:
    """Return the intrinsic 2x2 Gram matrix of two embedded row vectors."""

    rows = _row_vectors(value, name=name)
    gram = rows @ rows.T
    eigenvalues = np.linalg.eigvalsh(0.5 * (gram + gram.T))
    if float(eigenvalues[0]) <= 0.0:
        raise ValueError(f"{name} must define a positive-definite metric")
    return gram


def intrinsic_column_basis(gram: Any, *, name: str = "gram") -> np.ndarray:
    """Construct a 2D column basis with exactly the supplied Gram matrix."""

    matrix = np.asarray(gram, dtype=float)
    if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
        raise ValueError(f"{name} must be a finite 2x2 matrix")
    symmetric = 0.5 * (matrix + matrix.T)
    cholesky = np.linalg.cholesky(symmetric)
    # G = L L.T and A = L.T therefore gives A.T A = G.
    return cholesky.T


def _metric_signature(
    gram: np.ndarray,
    *,
    tolerance: float,
    scale: float,
) -> tuple[tuple[int, int, int], np.ndarray, np.ndarray, np.ndarray]:
    if tolerance < 0:
        raise ValueError("metric signature tolerance must be nonnegative")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("metric signature scale must be finite and positive")
    basis = intrinsic_column_basis(gram)
    reduced, unimodular, rotation = canonical_gauss_reduce_2d(
        basis,
        tol=float(tolerance),
        strict_handedness=False,
    )
    reduced = np.asarray(reduced, dtype=float)
    reduced_gram = 0.5 * (reduced.T @ reduced + (reduced.T @ reduced).T)
    signature = (
        int(np.rint(scale * float(reduced_gram[0, 0]))),
        int(np.rint(scale * float(reduced_gram[0, 1]))),
        int(np.rint(scale * float(reduced_gram[1, 1]))),
    )
    return (
        signature,
        reduced,
        np.asarray(unimodular, dtype=int),
        np.asarray(rotation, dtype=float),
    )


def _signature_text(signature: tuple[int, int, int]) -> str:
    return ",".join(str(value) for value in signature)


def project_zsl_metric_pair(
    raw: RawExternalMatch | Mapping[str, Any],
    *,
    signature_tolerance: float = 1.0e-12,
    signature_scale: float = 1.0e10,
) -> ProjectedMatch:
    """Project one raw ZSL match onto independent one-sided metric identity."""

    match_id = source_match_id(raw)
    fields = _fields(raw)
    try:
        film_gram = gram_from_row_vectors(
            fields["film_sl_vectors"],
            name="film_sl_vectors",
        )
        substrate_gram = gram_from_row_vectors(
            fields["substrate_sl_vectors"],
            name="substrate_sl_vectors",
        )
        (
            film_signature,
            film_reduced,
            film_unimodular,
            film_rotation,
        ) = _metric_signature(
            film_gram,
            tolerance=signature_tolerance,
            scale=signature_scale,
        )
        (
            substrate_signature,
            substrate_reduced,
            substrate_unimodular,
            substrate_rotation,
        ) = _metric_signature(
            substrate_gram,
            tolerance=signature_tolerance,
            scale=signature_scale,
        )

        film_signature_text = _signature_text(film_signature)
        substrate_signature_text = _signature_text(substrate_signature)
        pair_signature = (
            f"A:{film_signature_text}|B:{substrate_signature_text}"
        )

        # These diagnostics use the original ordered ZSL vector pair.  The
        # intrinsic bases have the same Gram tensors and do not independently
        # relabel film and substrate coordinates.
        film_basis = intrinsic_column_basis(film_gram, name="film_gram")
        substrate_basis = intrinsic_column_basis(
            substrate_gram,
            name="substrate_gram",
        )
        d_cell, d_area, d_shape, strains = airm_distance_and_strains(
            film_gram,
            substrate_gram,
        )
        zsl_diagnostics = zm_diagnostics_extended(film_basis, substrate_basis)
        film_area = float(math.sqrt(max(0.0, float(np.linalg.det(film_gram)))))
        substrate_area = float(
            math.sqrt(max(0.0, float(np.linalg.det(substrate_gram))))
        )

        return ProjectedMatch(
            source_match_id=match_id,
            projection_kind=PROJECTION_KIND,
            status="projected",
            identity={
                "metric_signature_version": METRIC_SIGNATURE_VERSION,
                "film_metric_signature": list(film_signature),
                "substrate_metric_signature": list(substrate_signature),
                "metric_pair_signature": pair_signature,
            },
            metrics={
                "film_gram": film_gram.tolist(),
                "substrate_gram": substrate_gram.tolist(),
                "film_area": film_area,
                "substrate_area": substrate_area,
                "log_area_ratio": float(abs(math.log(film_area / substrate_area))),
                "d_cell": float(d_cell),
                "d_area": float(d_area),
                "d_shape": float(d_shape),
                "principal_strains": [float(value) for value in strains],
                "max_abs_principal_strain": float(np.max(np.abs(strains))),
                **zsl_diagnostics,
            },
            diagnostics={
                "fixture_id": fixture_id(raw),
                "signature_tolerance": float(signature_tolerance),
                "signature_scale": float(signature_scale),
                "film_reduced_basis": film_reduced.tolist(),
                "substrate_reduced_basis": substrate_reduced.tolist(),
                "film_independent_unimodular_transform": (
                    film_unimodular.tolist()
                ),
                "substrate_independent_unimodular_transform": (
                    substrate_unimodular.tolist()
                ),
                "film_reduction_rotation": film_rotation.tolist(),
                "substrate_reduction_rotation": substrate_rotation.tolist(),
                "independent_one_sided_canonicalization": True,
                "coupled_identity": False,
                "mechanical_metrics_use_retained_vector_pairing": True,
            },
        )
    except (KeyError, TypeError, ValueError, np.linalg.LinAlgError) as exc:
        return ProjectedMatch(
            source_match_id=match_id,
            projection_kind=PROJECTION_KIND,
            status="failed",
            diagnostics={
                "fixture_id": _raw_dict(raw).get("fixture_id"),
                "error": f"{type(exc).__name__}: {exc}",
                "independent_one_sided_canonicalization": True,
                "coupled_identity": False,
            },
        )


__all__ = [
    "METRIC_SIGNATURE_VERSION",
    "PROJECTION_KIND",
    "fixture_id",
    "gram_from_row_vectors",
    "intrinsic_column_basis",
    "project_zsl_metric_pair",
    "source_match_id",
]
