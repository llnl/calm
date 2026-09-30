"""Dependency-light mathematics for geodesic in-plane strain partitioning.

This module is the single implementation owner for converting two right-handed
2D column bases into a common target along the affine-invariant geodesic on
SPD(2).  Higher-level interfaces add diagnostics, scanning, persistence, and
atomistic construction around this kernel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from calm.math2d._core import det2, inv2
from calm.math2d.spd2x2 import chol_upper, geodesic_spd, gram_2d

TARGET_BASIS_GAUGE = "upper_cholesky_positive_diagonal"
TARGET_BASIS_GAUGE_VERSION = 1
DEFAULT_TARGET_GAUGE_RELATIVE_TOLERANCE = 1e-10
DEFAULT_COMMON_TARGET_RELATIVE_TOLERANCE = 1e-8


@dataclass(frozen=True)
class GeodesicStrainPartition2D:
    """Scale-normalized geodesic partition of two in-plane bases."""

    alpha: float
    common_scale: float
    basis_a_normalized: np.ndarray
    basis_b_normalized: np.ndarray
    target_metric_normalized: np.ndarray
    target_metric: np.ndarray
    target_basis_normalized: np.ndarray
    target_basis: np.ndarray
    target_basis_gauge: str
    target_basis_gauge_version: int
    target_metric_reconstruction_relative_error: float
    target_lower_triangle_relative_error: float
    F_total: np.ndarray
    F_A: np.ndarray
    F_B: np.ndarray
    common_relative_error: float


def _finite_positive_float(name: str, value: object) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return result


def _alpha(value: object) -> float:
    result = float(value)
    if not np.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"alpha must be finite and lie in [0, 1]; got {value!r}.")
    return result


def _basis_2d(name: str, value: object) -> np.ndarray:
    basis = np.asarray(value, dtype=float)
    if basis.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2); got {basis.shape}.")
    if not np.all(np.isfinite(basis)):
        raise ValueError(f"{name} must contain only finite values.")
    return basis


def _right_handed_determinant(
    name: str,
    basis_normalized: np.ndarray,
    *,
    eps: float,
) -> float:
    determinant = float(det2(basis_normalized, mode="float"))
    if not np.isfinite(determinant) or determinant <= eps:
        raise ValueError(
            f"{name} must be a right-handed, nonsingular in-plane basis; "
            f"normalized determinant={determinant!r}."
        )
    return determinant


def geodesic_strain_partition_2d(
    basis_a: object,
    basis_b: object,
    *,
    alpha: object,
    eps_spd: object = 1e-14,
    gauge_relative_tolerance: object = DEFAULT_TARGET_GAUGE_RELATIVE_TOLERANCE,
) -> GeodesicStrainPartition2D:
    """Return the affine-invariant common target for two 2D column bases.

    A common positive scale is removed before Gram tensors, inverses, and
    spectral operations are evaluated.  The returned deformation gradients are
    therefore dimensionless and invariant under a common change of length
    units.  ``target_basis`` and ``target_metric`` are restored to the physical
    input scale for callers that need an explicit target cell.
    """

    alpha_f = _alpha(alpha)
    eps_f = _finite_positive_float("eps_spd", eps_spd)
    gauge_tol = _finite_positive_float(
        "gauge_relative_tolerance",
        gauge_relative_tolerance,
    )
    basis_a_raw = _basis_2d("basis_a", basis_a)
    basis_b_raw = _basis_2d("basis_b", basis_b)

    common_scale = float(max(np.max(np.abs(basis_a_raw)), np.max(np.abs(basis_b_raw))))
    if not np.isfinite(common_scale) or common_scale <= 0.0:
        raise ValueError("The two in-plane bases must have a finite, nonzero scale.")

    basis_a_n = basis_a_raw / common_scale
    basis_b_n = basis_b_raw / common_scale
    _right_handed_determinant("basis_a", basis_a_n, eps=eps_f)
    _right_handed_determinant("basis_b", basis_b_n, eps=eps_f)

    metric_a_n = gram_2d(basis_a_n)
    metric_b_n = gram_2d(basis_b_n)
    target_metric_n = geodesic_spd(
        metric_a_n,
        metric_b_n,
        alpha_f,
        clamp_tol=eps_f,
        eps=eps_f,
    )
    target_basis_n = chol_upper(target_metric_n)
    metric_denominator = max(
        float(np.linalg.norm(target_metric_n, ord="fro")),
        np.finfo(float).tiny,
    )
    target_metric_reconstruction_error = float(
        np.linalg.norm(
            target_basis_n.T @ target_basis_n - target_metric_n,
            ord="fro",
        )
        / metric_denominator
    )
    basis_denominator = max(
        float(np.linalg.norm(target_basis_n, ord="fro")),
        np.finfo(float).tiny,
    )
    target_lower_triangle_error = float(
        np.linalg.norm(np.tril(target_basis_n, k=-1), ord="fro") / basis_denominator
    )
    if (
        target_metric_reconstruction_error > gauge_tol
        or target_lower_triangle_error > gauge_tol
        or np.any(np.diag(target_basis_n) <= 0.0)
        or float(np.linalg.det(target_basis_n)) <= 0.0
    ):
        raise ValueError(
            "The upper-Cholesky target-basis gauge failed verification: "
            f"metric residual={target_metric_reconstruction_error:.3e}, "
            f"lower-triangle residual={target_lower_triangle_error:.3e}, "
            f"tolerance={gauge_tol:.3e}."
        )

    inverse_a_n = inv2(basis_a_n)
    inverse_b_n = inv2(basis_b_n)
    F_A = target_basis_n @ inverse_a_n
    F_B = target_basis_n @ inverse_b_n
    F_total = basis_b_n @ inverse_a_n

    common_a = F_A @ basis_a_n
    common_b = F_B @ basis_b_n
    denominator = max(
        float(np.linalg.norm(target_basis_n, ord="fro")),
        np.finfo(float).tiny,
    )
    common_error = (
        max(
            float(np.linalg.norm(common_a - target_basis_n, ord="fro")),
            float(np.linalg.norm(common_b - target_basis_n, ord="fro")),
            float(np.linalg.norm(common_a - common_b, ord="fro")),
        )
        / denominator
    )

    target_basis = common_scale * target_basis_n
    with np.errstate(over="ignore", under="ignore", invalid="ignore"):
        target_metric = target_basis.T @ target_basis
    target_metric_scale = float(np.max(np.abs(target_metric)))
    if (
        not np.all(np.isfinite(target_basis))
        or not np.all(np.isfinite(target_metric))
        or target_metric_scale <= 0.0
    ):
        raise ValueError(
            "The common target basis or metric is outside the finite, "
            "nonzero floating-point representation range."
        )

    return GeodesicStrainPartition2D(
        alpha=alpha_f,
        common_scale=common_scale,
        basis_a_normalized=basis_a_n,
        basis_b_normalized=basis_b_n,
        target_metric_normalized=target_metric_n,
        target_metric=target_metric,
        target_basis_normalized=target_basis_n,
        target_basis=target_basis,
        target_basis_gauge=TARGET_BASIS_GAUGE,
        target_basis_gauge_version=TARGET_BASIS_GAUGE_VERSION,
        target_metric_reconstruction_relative_error=(
            target_metric_reconstruction_error
        ),
        target_lower_triangle_relative_error=target_lower_triangle_error,
        F_total=F_total,
        F_A=F_A,
        F_B=F_B,
        common_relative_error=common_error,
    )


__all__ = [
    "DEFAULT_COMMON_TARGET_RELATIVE_TOLERANCE",
    "DEFAULT_TARGET_GAUGE_RELATIVE_TOLERANCE",
    "GeodesicStrainPartition2D",
    "TARGET_BASIS_GAUGE",
    "TARGET_BASIS_GAUGE_VERSION",
    "geodesic_strain_partition_2d",
]
