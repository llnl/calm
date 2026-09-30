"""benchmarks.common_metrics

Shared geometry/metric utilities for cross-method comparisons.

Key design rule
---------------
All derived metrics in the benchmark CSVs are computed *in this harness* so that
slabgen and pymatgen outputs can be compared on an identical basis:

- d_cell, d_area, d_shape are computed from the affine-invariant SPD metric
  on Gram tensors (AIRM).
- principal Hencky strains are derived from the relative metric eigenvalues.
- ZM/ZSL-style diagnostics (rel_da, rel_db, rel_dgamma) are computed from the
  reduced bases used in each match record.

This means:

- The **accept/reject** decisions in pymatgen and slabgen are still different
  (different gates).
- But once a match exists, the **reported metrics** are directly comparable.

"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable, Mapping, Tuple

import numpy as np


def _sym(A: np.ndarray) -> np.ndarray:
    A = np.asarray(A, dtype=float)
    return 0.5 * (A + A.T)


def _spd_eigh(G: np.ndarray, *, floor: float = 1e-18) -> Tuple[np.ndarray, np.ndarray]:
    """Eigen-decomposition with small-eigenvalue clipping."""

    w, V = np.linalg.eigh(_sym(G))
    w = np.maximum(w, float(floor))
    return w, V


def _inv_sqrt_spd(G: np.ndarray) -> np.ndarray:
    w, V = _spd_eigh(G)
    return V @ np.diag(1.0 / np.sqrt(w)) @ V.T


def airm_distance_and_strains(GA: np.ndarray, GB: np.ndarray) -> Tuple[float, float, float, np.ndarray]:
    """Return (d_cell, d_area, d_shape, principal_hencky_strains).

    Definitions follow the PyIntExp manuscript/SI:
      M = GA^{-1/2} GB GA^{-1/2}
      d_cell = || log(M) ||_F
      principal Hencky strains: eps_i = 0.5 * log(mu_i), where mu_i are eig(M)
    """

    GA = _sym(np.asarray(GA, float))
    GB = _sym(np.asarray(GB, float))

    GA_inv_sqrt = _inv_sqrt_spd(GA)
    M = GA_inv_sqrt @ GB @ GA_inv_sqrt
    mu = np.linalg.eigvalsh(_sym(M))
    mu = np.maximum(mu, 1e-18)

    log_mu = np.log(mu)
    d_cell = float(np.sqrt(np.sum(log_mu ** 2)))

    eps = 0.5 * log_mu
    # 2D area/shape split in principal coords:
    # d_area = sqrt(2) * |eps1 + eps2|
    # d_shape = sqrt(2) * |eps1 - eps2|
    eps1, eps2 = float(eps[0]), float(eps[1])
    d_area = float(np.sqrt(2.0) * abs(eps1 + eps2))
    d_shape = float(np.sqrt(2.0) * abs(eps1 - eps2))
    return d_cell, d_area, d_shape, np.array([eps1, eps2], dtype=float)


def basis_params(S2: np.ndarray) -> Tuple[float, float, float]:
    """Return (a, b, gamma_deg) for a (2,2) column basis."""

    S2 = np.asarray(S2, float)
    v1 = S2[:, 0]
    v2 = S2[:, 1]
    a = float(np.linalg.norm(v1))
    b = float(np.linalg.norm(v2))
    cosg = float(np.dot(v1, v2) / (a * b))
    cosg = max(-1.0, min(1.0, cosg))
    gamma = float(np.degrees(np.arccos(cosg)))
    return a, b, gamma


def zm_diagnostics(SA2: np.ndarray, SB2: np.ndarray):
    """Return ZM/ZSL-style mismatch diagnostics based on (a,b,gamma).

    Output
    ------
    rel_da, rel_db, rel_dgamma, d_gamma_deg

    where rel_dgamma = |Δγ| / mean(γ_A, γ_B).

    Notes
    -----
    These are *basis-dependent* diagnostics, but are useful for comparing against
    implementations that gate on length/angle thresholds (e.g., pymatgen ZSL).
    """

    aA, bA, gA = basis_params(SA2)
    aB, bB, gB = basis_params(SB2)

    rel_da = abs(aA - aB) / max(1e-18, aA)
    rel_db = abs(bA - bB) / max(1e-18, bA)

    d_gamma = abs(gA - gB)
    mean_gamma = 0.5 * (gA + gB)
    rel_dgamma = d_gamma / max(1e-18, mean_gamma)
    return float(rel_da), float(rel_db), float(rel_dgamma), float(d_gamma)



def zm_diagnostics_extended(SA2: np.ndarray, SB2: np.ndarray):
    """Extended ZM-style diagnostics with strain-like approximations.

    Returns a dict with:
      - aA, bA, gammaA_deg, aB, bB, gammaB_deg
      - rel_da, rel_db, rel_dgamma, d_gamma_deg, d_gamma_rad
      - eps_a_log, eps_b_log  (Hencky-like log length mismatches)
      - eps_shear_approx      (~ 0.5 * d_gamma_rad, valid for small mismatches near orthogonal cells)

    Notes
    -----
    For small strains, log length mismatches are a better additive proxy than
    fractional length mismatches, and the included-angle difference maps onto a
    shear-like component. The exact, basis-invariant strain interpretation should
    be taken from the AIRM/Hencky principal strains computed from Gram tensors.
    """
    aA, bA, gA = basis_params(SA2)
    aB, bB, gB = basis_params(SB2)

    rel_da = abs(aA - aB) / max(1e-18, aA)
    rel_db = abs(bA - bB) / max(1e-18, bA)

    d_gamma_deg = abs(gA - gB)
    mean_gamma = 0.5 * (gA + gB)
    rel_dgamma = d_gamma_deg / max(1e-18, mean_gamma)

    # Hencky-like log length mismatches (coordinate-dependent, but additive)
    eps_a_log = abs(np.log(max(1e-18, aB) / max(1e-18, aA)))
    eps_b_log = abs(np.log(max(1e-18, bB) / max(1e-18, bA)))

    # Angle change in radians
    d_gamma_rad = float(np.radians(d_gamma_deg))

    # Small-angle approximation: for near-orthogonal bases, angle change ~ engineering shear
    # and principal shear strain magnitude ~ 0.5 * d_gamma_rad.
    eps_shear_approx = 0.5 * d_gamma_rad

    return {
        "aA": float(aA),
        "bA": float(bA),
        "gammaA_deg": float(gA),
        "aB": float(aB),
        "bB": float(bB),
        "gammaB_deg": float(gB),
        "rel_da": float(rel_da),
        "rel_db": float(rel_db),
        "rel_dgamma": float(rel_dgamma),
        "d_gamma_deg": float(d_gamma_deg),
        "d_gamma_rad": float(d_gamma_rad),
        "eps_a_log": float(eps_a_log),
        "eps_b_log": float(eps_b_log),
        "eps_shear_approx": float(eps_shear_approx),
        "gamma_mean_deg": float(mean_gamma),
        "gamma_mean_rad": float(np.radians(mean_gamma)),
    }


def size_proxy_d_size(*, kA: int, kB: int, nA_prim: int, nB_prim: int) -> float:
    """Log size proxy: max(0, ln(N_int / (N_A + N_B)))."""

    N_int = float(kA * nA_prim + kB * nB_prim)
    N0 = float(nA_prim + nB_prim)
    return float(max(0.0, np.log(N_int / max(1e-18, N0))))


def scalar_score(
    *,
    d_cell: float,
    d_size: float,
    eps_principal_max: float,
    nA_prim: int,
    nB_prim: int,
    N_at_max: int,
    w_match: float,
) -> float:
    """Normalize d_cell and d_size to [0,1] and compute convex score.

    This is only for optional scalarized ranking; the Pareto front is the
    primary object of interest.
    """

    # From SI: d_cell_max = 2*sqrt(2)*eps_max (when both principal strains saturate).
    d_cell_max = float(2.0 * np.sqrt(2.0) * abs(eps_principal_max))
    d_cell_norm = min(1.0, float(d_cell) / max(1e-18, d_cell_max))

    N0 = float(nA_prim + nB_prim)
    d_size_max = max(0.0, float(np.log(float(N_at_max) / max(1e-18, N0))))
    d_size_norm = 0.0 if d_size_max == 0.0 else min(1.0, float(d_size) / d_size_max)

    return float(w_match * d_cell_norm + (1.0 - w_match) * d_size_norm)


def load_csv(path: str | Path) -> list[dict[str, str]]:
    """Load a benchmark CSV as a list of string-keyed rows."""

    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def filter_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    pair: str,
    max_area: float,
    area_tolerance: float = 1.0e-9,
) -> list[dict[str, object]]:
    """Return rows for one named pair and numerical maximum-area value."""

    target_area = float(max_area)
    result: list[dict[str, object]] = []
    for row in rows:
        if str(row.get("pair", "")) != str(pair):
            continue
        try:
            row_area = float(row.get("max_area", "nan"))
        except (TypeError, ValueError):
            continue
        if math.isclose(
            row_area,
            target_area,
            rel_tol=0.0,
            abs_tol=float(area_tolerance),
        ):
            result.append(dict(row))
    return result
