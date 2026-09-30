"""Polar decomposition helpers for 2×2 matrices.

Provides a stable polar decomposition implementation without relying on
SciPy/LAPACK. Useful for small fixed-size linear algebra operations in CALM.
"""

from __future__ import annotations

import numpy as np

from ._core import _as_2x2, sym2
from .sym2x2 import _invsqrt2_psd, _sqrt2_psd


def polar2(
    A: np.ndarray,
    *,
    eps: float = 1e-15,
    reorthonormalize: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Polar decomposition for a real 2×2 matrix A without SciPy/LAPACK.

        A = U @ H
        H = sqrt(A^T A) (PSD)
        U = A @ inv(H)

    The input is normalized before the spectral operations, so ``eps`` is a
    dimensionless relative floor on squared singular values.
    """
    if not np.isfinite(eps) or eps <= 0.0:
        raise ValueError("polar2: eps must be finite and > 0")

    A = _as_2x2(A, dtype=float, name="polar2")
    scale = float(np.max(np.abs(A)))
    if not np.isfinite(scale):
        raise ValueError("polar2: A must contain only finite values")
    if scale == 0.0:
        zeros = np.zeros((2, 2), dtype=float)
        return zeros, zeros

    # Normalize before forming A.T @ A so ``eps`` is a relative floor on the
    # squared singular values rather than an absolute floor tied to input units.
    A_scaled = A / scale
    M_scaled = sym2(A_scaled.T @ A_scaled)
    H_scaled = _sqrt2_psd(M_scaled)
    M_scaled_invsqrt = _invsqrt2_psd(M_scaled, eps=eps)

    U = A_scaled @ M_scaled_invsqrt

    if reorthonormalize:
        C = sym2(U.T @ U)
        U = U @ _invsqrt2_psd(C, eps=eps)

    H = scale * H_scaled
    return U, H


__all__ = ["polar2"]
"""Polar decomposition helpers for 2×2 matrices.

This module provides utilities for stable polar/spectral decompositions in 2D
that are used by reduction and canonicalization routines.
"""
