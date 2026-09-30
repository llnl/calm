"""calm.interface.refinement.strain

Strain-splitting utilities for interface construction.

Conventions
-----------
- Lattice vectors are stored as **columns**.
- 2D operations act on the in-plane (x,y) block of the 3D lattice.
- The returned affine transforms are 3x3 matrices in Cartesian coordinates.

This module is intentionally dependency-light and does not import the Interface
model to avoid circular imports.
"""

from __future__ import annotations

import numpy as np

from calm.exceptions import InterfaceBuilderError

from calm.math2d._core import sym2
from calm.math2d.polar2x2 import polar2
from calm.math2d.spd2x2 import log_spd
from calm.interface.refinement._math import (
    DEFAULT_COMMON_TARGET_RELATIVE_TOLERANCE,
    geodesic_strain_partition_2d,
)
from calm.interface.types import StrainState


INCREMENTAL_INTERFACE_MATCHING_SCOPE = "incremental_interface_matching"


def _extract_inplane_cols(S_3D: np.ndarray) -> np.ndarray:
    """Extract a right-handed xy-plane basis from a 3x3 column lattice."""
    lattice = np.asarray(S_3D, dtype=float)
    if lattice.shape != (3, 3):
        raise ValueError("Expected S_3D to be shape (3, 3).")
    if not np.all(np.isfinite(lattice)):
        raise ValueError("S_3D must contain only finite values.")

    scale = float(np.max(np.abs(lattice[:2, :2])))
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError("The in-plane lattice block must have nonzero finite scale.")
    out_of_plane = float(np.max(np.abs(lattice[2, :2])))
    if out_of_plane > 1e-10 * scale:
        raise ValueError(
            "The first two lattice vectors must lie in CALM's global xy plane."
        )
    return lattice[:2, :2].copy()


def _finite_nonnegative_float(name: str, value: object) -> float:
    result = float(value)
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative.")
    return result


def compute_strain_2d(
    S_A_3D: np.ndarray,
    S_B_3D: np.ndarray,
    *,
    alpha: float = 0.5,
    eps_spd: float = 1e-14,
    check_common: bool = True,
    common_tol: float = DEFAULT_COMMON_TARGET_RELATIVE_TOLERANCE,
) -> StrainState:
    """Compute a robust 2D strain split between two in-plane lattices.

    Parameters
    ----------
    S_A_3D, S_B_3D
        3x3 lattice matrices with **columns** as lattice vectors. The first two
        vectors must lie in CALM's global xy plane.
    alpha
        Split parameter on the SPD(2) geodesic from slab A to slab B. ``alpha=0``
        uses A's target metric, so A has zero stretch and B carries the metric
        mismatch. ``alpha=1`` reverses those roles. A zero-stretch endpoint can
        still include the deterministic common-gauge rotation.
    eps_spd
        Positive, dimensionless conditioning floor applied after the two input
        bases have been normalized by a common length scale.
    check_common
        If True, verify that both deformation gradients reach the same normalized
        target basis within ``common_tol``.
    common_tol
        Finite nonnegative relative Frobenius tolerance for the common-target check.

    Returns
    -------
    StrainState
        Embedded 3x3 affine transforms and Hencky-strain diagnostics.
    """
    if not isinstance(check_common, (bool, np.bool_)):
        raise TypeError("check_common must be a bool.")
    common_tol_f = _finite_nonnegative_float("common_tol", common_tol)

    S2 = _extract_inplane_cols(S_A_3D)
    T2 = _extract_inplane_cols(S_B_3D)

    try:
        partition = geodesic_strain_partition_2d(
            S2,
            T2,
            alpha=alpha,
            eps_spd=eps_spd,
        )
    except Exception as exc:
        raise InterfaceBuilderError(
            f"Failed to compute geodesic strain partition: {exc}"
        ) from exc

    if check_common and partition.common_relative_error > common_tol_f:
        raise InterfaceBuilderError(
            "Common-lattice check failed: relative Frobenius error "
            f"{partition.common_relative_error:.3e} > {common_tol_f:.3e}"
        )

    F_A2 = np.asarray(partition.F_A, dtype=float)
    F_B2 = np.asarray(partition.F_B, dtype=float)

    try:
        R_A2, U_A2 = polar2(F_A2, eps=float(eps_spd), reorthonormalize=True)
        R_B2, U_B2 = polar2(F_B2, eps=float(eps_spd), reorthonormalize=True)
        U_A2 = sym2(U_A2)
        U_B2 = sym2(U_B2)
        E_A2 = log_spd(U_A2, eps=float(eps_spd))
        E_B2 = log_spd(U_B2, eps=float(eps_spd))
    except Exception as exc:
        raise InterfaceBuilderError(
            f"Failed to compute polar/Hencky strain diagnostics: {exc}"
        ) from exc

    # RMS of principal Hencky strains in 2D:
    # sqrt((e1^2 + e2^2)/2) = ||E||_F / sqrt(2).
    E_A_rms = float(np.sqrt(0.5) * np.linalg.norm(E_A2, ord="fro"))
    E_B_rms = float(np.sqrt(0.5) * np.linalg.norm(E_B2, ord="fro"))

    def embed_2x2_to_3x3(A2: np.ndarray) -> np.ndarray:
        A3 = np.eye(3, dtype=float)
        A3[:2, :2] = np.asarray(A2, dtype=float)
        return A3

    return StrainState(
        alpha=partition.alpha,
        F_tot=embed_2x2_to_3x3(partition.F_total),
        F_A=embed_2x2_to_3x3(F_A2),
        R_A=embed_2x2_to_3x3(R_A2),
        U_A=embed_2x2_to_3x3(U_A2),
        E_A=embed_2x2_to_3x3(E_A2),
        E_A_rms=E_A_rms,
        F_B=embed_2x2_to_3x3(F_B2),
        R_B=embed_2x2_to_3x3(R_B2),
        U_B=embed_2x2_to_3x3(U_B2),
        E_B=embed_2x2_to_3x3(E_B2),
        E_B_rms=E_B_rms,
    )
