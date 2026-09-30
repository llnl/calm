"""Symmetric 2×2 linear algebra helpers.

Utilities for working with symmetric 2×2 matrices, used by the 2D metric and
reduction code.
"""

from __future__ import annotations

import numpy as np

from ._core import _as_2x2, sym2


def eigvals2_spd(A: np.ndarray) -> np.ndarray:
    """
    Eigenvalues of a 2×2 real symmetric matrix via closed form.
    Returns ascending eigenvalues (2,).
    """
    A = _as_2x2(A, dtype=float, name="eigvals2_spd")
    A = sym2(A)

    a = float(A[0, 0])
    b = float(A[0, 1])
    d = float(A[1, 1])

    tr2 = 0.5 * (a + d)
    diff2 = 0.5 * (a - d)
    delta = np.hypot(diff2, b)

    return np.array([tr2 - delta, tr2 + delta], dtype=float)


def eigh2_sym(
    A: np.ndarray,
    *,
    symmetrize: bool = True,
    b_tol: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Closed-form eigendecomposition for a 2×2 real symmetric matrix.

    Returns eigenvalues w (ascending) and orthonormal eigenvectors Q (columns).
    No LAPACK; does not call np.linalg.eigh.

    Parameters
    ----------
    symmetrize
        If True (default) apply (A + A^T)/2 first.
    b_tol
        Optional absolute near-diagonal threshold. If ``None``, use the
        scale-relative default

        ``1e-15 * max(|a|, |b|, |d|)``.

        If ``abs(b) <= b_tol``, the matrix is treated as diagonal for
        eigenvector construction.
    """
    A = _as_2x2(A, dtype=float, name="eigh2_sym")
    if symmetrize:
        A = sym2(A)

    a = float(A[0, 0])
    b = float(A[0, 1])
    d = float(A[1, 1])

    tr2 = 0.5 * (a + d)
    diff2 = 0.5 * (a - d)
    delta = np.hypot(diff2, b)

    w0 = tr2 - delta
    w1 = tr2 + delta
    w = np.array([w0, w1], dtype=float)

    if b_tol is None:
        scale = max(abs(a), abs(b), abs(d))
        b_tol = 1e-15 * scale
    else:
        b_tol = float(b_tol)
        if not np.isfinite(b_tol) or b_tol < 0.0:
            raise ValueError("eigh2_sym: b_tol must be finite and nonnegative")

    if abs(b) <= b_tol:
        if a <= d:
            Q = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=float)
        else:
            Q = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=float)
        return w, Q

    # Solve (A - w0 I) v = 0 robustly.
    x1, y1 = b, (w0 - a)
    x2, y2 = (w0 - d), b

    n1 = np.hypot(x1, y1)
    n2 = np.hypot(x2, y2)

    if n2 > n1:
        x, y, n = x2, y2, n2
    else:
        x, y, n = x1, y1, n1

    if n == 0.0:
        v0 = np.array([1.0, 0.0], dtype=float)
    else:
        v0 = np.array([x / n, y / n], dtype=float)

    v1 = np.array([-v0[1], v0[0]], dtype=float)
    Q = np.column_stack([v0, v1])
    return w, Q


# -----------------------------
# Internal PSD helpers (2×2)
# -----------------------------


def _eigh2_psd_clamp(
    S: np.ndarray,
    *,
    symmetrize: bool = True,
    clamp_tol: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Internal: eigendecomposition of symmetric 2×2 with eigenvalues clamped to >= 0.

    clamp_tol:
        If > 0, eigenvalues in [-clamp_tol, 0) are clamped to 0.
        If materially negative eigenvalues remain, raises ValueError.
    """
    w, Q = eigh2_sym(S, symmetrize=symmetrize)

    if clamp_tol > 0.0:
        w = np.where((w < 0.0) & (w >= -clamp_tol), 0.0, w)

    if np.any(w < 0.0):
        raise ValueError(f"Matrix expected PSD but has negative eigenvalues: {w}")

    return w, Q


def _sqrt2_psd(S: np.ndarray, *, clamp_tol: float = 1e-15) -> np.ndarray:
    """Internal: symmetric PSD square root for 2×2 (allows zero eigenvalues)."""
    S = _as_2x2(S, dtype=float, name="_sqrt2_psd")
    w, Q = _eigh2_psd_clamp(S, symmetrize=True, clamp_tol=clamp_tol)
    return sym2((Q * np.sqrt(w)) @ Q.T)


def _invsqrt2_psd(
    S: np.ndarray,
    *,
    eps: float = 1e-15,
    clamp_tol: float = 1e-15,
) -> np.ndarray:
    """Internal: symmetric inverse square root for 2×2 PSD using eigenvalue flooring."""
    if eps <= 0.0:
        raise ValueError("_invsqrt2_psd: eps must be > 0")
    S = _as_2x2(S, dtype=float, name="_invsqrt2_psd")
    w, Q = _eigh2_psd_clamp(S, symmetrize=True, clamp_tol=clamp_tol)
    w = np.maximum(w, eps)
    return sym2((Q * (1.0 / np.sqrt(w))) @ Q.T)


__all__ = [
    "eigvals2_spd",
    "eigh2_sym",
]
"""Symmetric 2×2 linear algebra helpers.

Utilities for working with symmetric 2×2 matrices, used by the 2D metric and
reduction code.
"""
