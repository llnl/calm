
"""Bridge between ZM/ZSL-style tolerances and SlabGen (AIRM/Hencky) metrics.

This module is intended for *comparative benchmarking* and for helping users
translate familiar Zur--McGill (length/angle) mismatch diagnostics into the
principal-strain language used by SlabGen.

Key ideas
---------
1) Both metric families can be computed from the *same* 2D metric tensor
   (Gram matrix) once a deterministic reduced basis is fixed.
2) ZSL-style gates (max_length_tol, max_angle_tol) implicitly constrain
   coordinate-dependent components of a strain-like mismatch.
3) SlabGen's gate (eps_principal_max) constrains the *coordinate-invariant*
   principal Hencky strains, which relate directly to elastic strain energy in
   coherent epitaxy (up to material-dependent stiffness weighting).

The conversion formulas here are intentionally conservative and are most accurate
for small mismatches (a few percent) and near-orthogonal reduced cells.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
from typing import Dict, Tuple


@dataclass(frozen=True)
class ZSLTols:
    max_length_tol: float  # fractional (e.g. 0.03)
    max_angle_tol: float   # *relative* (e.g. 0.01 means |Δγ|/γ̄ <= 0.01)


@dataclass(frozen=True)
class SlabGenTols:
    eps_principal_max: float  # max |Hencky principal strain| (e.g. 0.03)


def airm_dcell_upper_bound(eps_principal_max: float) -> float:
    """Upper bound on d_cell given a principal-strain bound.

    If |ε1|,|ε2| <= eps_principal_max, then:
        d_cell = ||log M||_F = 2*sqrt(ε1^2 + ε2^2) <= 2*sqrt(2)*eps_principal_max
    """
    return float(2.0 * math.sqrt(2.0) * eps_principal_max)


def approx_eps_from_zsl_tols(tols: ZSLTols, gamma_ref_rad: float) -> float:
    """Approximate an 'effective' principal strain bound implied by ZSL tolerances.

    - Length tol: treat as |ln(aB/aA)| <= ln(1+tol) ≈ tol (small mismatch).
    - Angle tol: if max_angle_tol is relative, absolute |Δγ| <= max_angle_tol * gamma_ref_rad.
      For near-orthogonal reduced cells and small shear, |Δγ| (rad) ≈ engineering shear,
      and max |principal| ≈ |Δγ|/2.

    Returns max(eps_len, eps_shear).
    """
    eps_len = abs(math.log(1.0 + float(tols.max_length_tol)))
    dgamma_abs = float(tols.max_angle_tol) * float(gamma_ref_rad)
    eps_shear = 0.5 * abs(dgamma_abs)
    return float(max(eps_len, eps_shear))


def approx_zsl_angle_tol_from_eps(eps_principal_max: float, gamma_ref_rad: float) -> float:
    """Suggest a *relative* ZSL max_angle_tol that is roughly commensurate with eps_principal_max.

    Using the small-mismatch approximation |Δγ| (rad) ≈ 2*eps_principal_max, we set
        max_angle_tol_rel ≈ (2*eps_principal_max) / gamma_ref_rad.

    If gamma_ref_rad is not known a priori, a practical default is to take the mean reduced-cell
    angle (in radians) for the candidate set, or use ~pi/2 for near-rectangular surfaces.
    """
    gamma_ref_rad = max(1e-12, float(gamma_ref_rad))
    return float((2.0 * float(eps_principal_max)) / gamma_ref_rad)


def approx_zsl_length_tol_from_eps(eps_principal_max: float) -> float:
    """Suggest ZSL max_length_tol commensurate with eps_principal_max.

    For small mismatch, fractional length change ≈ Hencky strain.
    We invert ln(1+tol) ≈ eps to give:
        tol ≈ exp(eps) - 1
    """
    return float(math.exp(float(eps_principal_max)) - 1.0)


# -----------------------------------------------------------------------------
# Exact metric conversion (basis/Gram ↔ AIRM / Hencky strains)
# -----------------------------------------------------------------------------

def gram_from_lattice_params(a: float, b: float, gamma_rad: float) -> np.ndarray:
    """Construct the 2×2 Gram matrix from (a, b, gamma).

    The Gram matrix encodes the intrinsic 2D metric:
        G = [[a^2, a b cos(gamma)],
             [a b cos(gamma), b^2]]

    For a reduced 2D lattice, (a, b, gamma) are Zur–McGill invariants, so this
    conversion is one-to-one (up to floating point rounding).
    """
    a = float(a)
    b = float(b)
    gamma = float(gamma_rad)
    c = math.cos(gamma)
    return np.array([[a * a, a * b * c], [a * b * c, b * b]], dtype=float)


def lattice_params_from_gram(G: np.ndarray) -> Tuple[float, float, float]:
    """Recover (a, b, gamma_rad) from a 2×2 Gram matrix."""
    G = np.asarray(G, dtype=float)
    a = math.sqrt(max(G[0, 0], 0.0))
    b = math.sqrt(max(G[1, 1], 0.0))
    if a == 0.0 or b == 0.0:
        return a, b, 0.0
    cosg = float(G[0, 1]) / (a * b)
    cosg = max(-1.0, min(1.0, cosg))
    gamma = math.acos(cosg)
    return a, b, gamma


def airm_from_gram(GA: np.ndarray, GB: np.ndarray) -> Dict[str, float]:
    """Compute SlabGen-style mismatch metrics from two Gram matrices.

    Returns a dict compatible with benchmarks.common_metrics.airm_distance_and_strains:
      - d_cell, d_area, d_shape
      - eps1, eps2 (principal Hencky strains)
      - eps_principal_max
    """
    from .common_metrics import airm_distance_and_strains

    return airm_distance_and_strains(GA, GB)


def airm_from_zm_lattice_params(
    aA: float, bA: float, gammaA_rad: float,
    aB: float, bB: float, gammaB_rad: float,
) -> Dict[str, float]:
    """Exact (ZM params → Gram → AIRM metrics) conversion."""
    GA = gram_from_lattice_params(aA, bA, gammaA_rad)
    GB = gram_from_lattice_params(aB, bB, gammaB_rad)
    return airm_from_gram(GA, GB)

