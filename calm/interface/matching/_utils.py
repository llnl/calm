"""Small numeric helpers used by the matching pipeline.

These helpers are pure numeric/NumPy and are safe to import without heavy
optional dependencies.
"""

from __future__ import annotations

import math
from numbers import Integral
from typing import Tuple

import numpy as np


def _positive_integer(name: str, value: object) -> int:
    """Return a strict positive integer without accepting truncating coercions."""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be a positive integer.")
    result = int(value)
    if result < 1:
        raise ValueError(f"{name} must be at least 1.")
    return result


def _finite_positive_float(name: str, value: object) -> float:
    """Return a finite positive floating-point value."""
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return result


def _finite_nonnegative_float(name: str, value: object) -> float:
    """Return a finite nonnegative floating-point value."""
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative.")
    return result


def _unit_interval_float(name: str, value: object) -> float:
    """Return a finite floating-point value in the closed unit interval."""
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1.")
    return result


def _normalize_nonnegative(value: float, maximum: float) -> float:
    """Normalize a nonnegative diagnostic, including an exact zero maximum."""
    value_f = float(value)
    maximum_f = float(maximum)
    if value_f < 0.0 or maximum_f < 0.0:
        raise ValueError("Normalized diagnostics and maxima must be nonnegative.")
    if maximum_f > 0.0:
        return float(value_f / maximum_f)
    if value_f == 0.0:
        return 0.0
    return float("inf")


def _normalize_d_cell(d_cell: float, d_cell_max: float) -> float:
    """Normalize cell distance against its admissible maximum.

    When the principal-strain tolerance is exactly zero, the admissible maximum
    is also zero. In that case only an exact zero-distance match has normalized
    distance zero; a positive distance remains infinite.
    """
    return _normalize_nonnegative(d_cell, d_cell_max)


def _normalize_d_size(d_size: float, d_size_max: float) -> float:
    """Normalize the logarithmic size penalty against the declared atom cap."""
    return _normalize_nonnegative(d_size, d_size_max)


def _compute_d_size(N_at: float, N_A: int, N_B: int) -> float:
    """Return the logarithmic paired-supercell size penalty."""
    denom = float(N_A + N_B)
    if denom <= 0.0 or not math.isfinite(denom):
        return float("inf")
    N_at_f = float(N_at)
    if N_at_f <= 0.0 or not math.isfinite(N_at_f):
        return float("inf")
    return float(max(0.0, math.log(N_at_f / denom)))


def _compute_match_score(
    d_cell_norm: float,
    d_size_norm: float,
    w_match: float,
) -> float:
    """Return the weighted deterministic match score (smaller is better).

    Endpoint weights are handled explicitly so an inactive term cannot create
    ``0 * inf -> nan`` when its normalization maximum is exactly zero.
    """
    w = _unit_interval_float("w_match", w_match)
    cell = float(d_cell_norm)
    size = float(d_size_norm)
    if w == 1.0:
        return cell
    if w == 0.0:
        return size
    return float(w * cell + (1.0 - w) * size)


def _prim_inplane_basis_2d(slab: object) -> Tuple[np.ndarray, float]:
    """Return the physical in-plane column basis and area for an oriented slab.

    CALM oriented slabs store the first two ASE row-cell vectors in the global
    Cartesian ``xy`` plane. This helper converts that row representation to a
    2x2 column basis. It does not rotate an arbitrary tilted external cell into
    the matching frame.
    """
    cell = np.asarray(slab.atoms.cell.array, dtype=float)
    if cell.shape != (3, 3):
        raise ValueError("Slab cell must be 3x3.")
    if not np.all(np.isfinite(cell)):
        raise ValueError("Slab cell entries must be finite.")

    plane_scale = float(np.max(np.abs(cell[:2, :])))
    if plane_scale <= 0.0:
        raise ValueError("Degenerate primitive in-plane basis.")
    if float(np.max(np.abs(cell[:2, 2]))) > 1.0e-10 * plane_scale:
        raise ValueError(
            "Matching requires the first two slab vectors to lie in the "
            "global Cartesian xy plane."
        )

    A2 = cell[:2, :2].T.copy()
    scale = float(np.max(np.abs(A2)))
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("Degenerate primitive in-plane basis.")

    area_scaled = abs(float(np.linalg.det(A2 / scale)))
    area = float(area_scaled * scale * scale)
    if not math.isfinite(area) or area <= 0.0:
        raise ValueError("Degenerate primitive in-plane basis (area <= 0).")
    return A2, area


def compute_valid_hnf_index_pairs(
    areaA_prim: float,
    areaB_prim: float,
    k_max_A: int,
    k_max_B: int,
    eps_principal_max_f: float,
    rtol: float = 1e-15,
) -> np.ndarray:
    """Return HNF index pairs satisfying the necessary log-area band.

    The calculation is performed in log space to avoid overflow and underflow
    for broad but finite area and strain scales.
    """
    kA_max = _positive_integer("k_max_A", k_max_A)
    kB_max = _positive_integer("k_max_B", k_max_B)
    areaA = _finite_positive_float("areaA_prim", areaA_prim)
    areaB = _finite_positive_float("areaB_prim", areaB_prim)
    eps = _finite_nonnegative_float(
        "eps_principal_max_f",
        eps_principal_max_f,
    )
    rtol_f = _finite_nonnegative_float("rtol", rtol)
    if rtol_f >= 1.0:
        raise ValueError("rtol must be smaller than 1.")

    kA = np.arange(1, kA_max + 1, dtype=np.float64)[:, None]
    kB = np.arange(1, kB_max + 1, dtype=np.float64)[None, :]
    log_ratio = np.log(kA) + math.log(areaA) - np.log(kB) - math.log(areaB)

    eps_area = 2.0 * eps
    lower = -eps_area + math.log1p(-rtol_f)
    upper = eps_area + math.log1p(rtol_f)
    mask = (log_ratio >= lower) & (log_ratio <= upper)
    iA, iB = np.where(mask)
    return np.column_stack((iA + 1, iB + 1)).astype(int, copy=False)
