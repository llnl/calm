"""Symmetric positive-definite 2×2 matrix utilities.

Helpers for SPD-specific operations such as matrix logarithm/exponential and
metric-aware transforms.
"""

from __future__ import annotations

import numpy as np

from ._core import _as_2x2, det2, sym2
from .sym2x2 import _eigh2_psd_clamp, eigh2_sym, eigvals2_spd


def _affine_combo_sym2(G: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    """Return alpha*I + beta*G for 2×2 matrices, enforcing symmetry.

    This is a tiny-matrix hot helper designed to minimize temporary allocations.
    """
    a00 = float(G[0, 0])
    a01 = float(G[0, 1])
    a10 = float(G[1, 0])
    a11 = float(G[1, 1])

    M = np.array(
        [[alpha + beta * a00, beta * a01], [beta * a10, alpha + beta * a11]],
        dtype=float,
    )
    return sym2(M)


def check_spd2(
    G: np.ndarray,
    *,
    tol: float = 0.0,
    symmetrize: bool = True,
) -> np.ndarray:
    """
    Validate that G is 2×2 SPD using Sylvester's criterion (for symmetric matrices):
        a11 > 0 and det(G) > 0

    tol enforces strict positivity margins:
        a11 > tol and det(G) > tol
    """
    G = _as_2x2(G, dtype=float, name="check_spd2")
    if symmetrize:
        G = sym2(G)

    a11 = float(G[0, 0])
    d = float(det2(G, mode="float"))

    if not (a11 > tol):
        raise ValueError(f"check_spd2: not SPD (a11={a11} <= {tol})")
    if not (d > tol):
        raise ValueError(f"check_spd2: not SPD (det={d} <= {tol})")

    return G


def cholesky2_spd(
    G: np.ndarray,
    *,
    upper: bool = True,
    tol: float = 0.0,
) -> np.ndarray:
    """
    Closed-form Cholesky for 2×2 SPD matrices.

    Returns upper-triangular R by default such that G = R^T R.

    Parameters
    ----------
    G
        2×2 SPD matrix.
    upper
        If True (default), return an upper-triangular factor R such that ``G = R^T R``.
        If False, return a lower-triangular factor L such that ``G = L L^T``.
    tol
        Positivity tolerance used by Sylvester checks and for clamping a tiny
        negative second pivot in ``[-tol, 0)`` to ``0``.
    Notes
    -----
    The same tolerance is used both for Sylvester checks (a11, det) and for
    allowing a small negative second pivot to be clamped to 0. If you want
    independent control, split this into two tolerances.
    """
    G = check_spd2(G, tol=tol, symmetrize=True)

    a = float(G[0, 0])
    b = float(G[0, 1])
    d = float(G[1, 1])

    l11 = np.sqrt(a)
    l21 = b / l11
    pivot = d - l21 * l21

    if tol > 0.0 and pivot < 0.0 and pivot >= -tol:
        pivot = 0.0
    if pivot <= 0.0:
        raise ValueError("cholesky2_spd: G must be SPD (second pivot <= 0)")

    l22 = np.sqrt(pivot)

    L = np.array([[l11, 0.0], [l21, l22]], dtype=float)

    return L.T if upper else L


# --------- Convenience helpers used by the interface strain-partition kernels ---------


def gram_2d(S: np.ndarray) -> np.ndarray:
    """Return the 2×2 Gram tensor ``G = Sᵀ S`` for a 2D basis.

    Parameters
    ----------
    S
        2×2 in-plane basis (columns are basis vectors in a common Cartesian frame).

    Returns
    -------
    G
        2×2 symmetric Gram tensor. For an invertible basis ``S`` this is SPD.
    """

    S2 = _as_2x2(S, dtype=float, name="gram_2d.S")
    return S2.T @ S2


def chol_upper(
    G: np.ndarray,
    *,
    tol: float = 0.0,
) -> np.ndarray:
    """Upper-triangular Cholesky factor ``R`` such that ``G = Rᵀ R``.

    Notes
    -----
    This is a thin wrapper around :func:`cholesky2_spd` that exists to make the
    "Cholesky lift" step in the affine-invariant strain partitioning kernel
    explicit and stable for callers/tests.
    """

    return cholesky2_spd(G, upper=True, tol=tol)


def inv2_spd(G: np.ndarray, *, upper: bool = True, tol: float = 0.0) -> np.ndarray:
    """Inverse of a 2×2 SPD matrix using closed-form Cholesky (no LAPACK)."""
    R = cholesky2_spd(G, upper=upper, tol=tol)

    if upper:
        r11 = float(R[0, 0])
        r12 = float(R[0, 1])
        r22 = float(R[1, 1])

        invr11 = 1.0 / r11
        invr22 = 1.0 / r22
        invR = np.array([[invr11, -r12 * invr11 * invr22], [0.0, invr22]], dtype=float)

        Gi = invR @ invR.T
        return sym2(Gi)

    L = R
    l11 = float(L[0, 0])
    l21 = float(L[1, 0])
    l22 = float(L[1, 1])

    invl11 = 1.0 / l11
    invl22 = 1.0 / l22
    invL = np.array([[invl11, 0.0], [-l21 * invl11 * invl22, invl22]], dtype=float)

    Gi = invL.T @ invL
    return sym2(Gi)


def log_spd(G: np.ndarray, *, eps: float | None = None) -> np.ndarray:
    """Principal matrix log for 2×2 SPD (eigenvalue-only in the common case).

    Implementation detail
    ---------------------
    For a 2×2 diagonalizable matrix A with eigenvalues (λ0, λ1), any matrix
    function f(A) can be written as an affine combination of I and A:

        f(A) = α I + β A,

    where α,β are determined by enforcing f(λi) on the spectrum. For symmetric
    2×2 matrices this avoids explicit eigenvectors and small dense matmuls.

    Numerical equivalence
    ---------------------
    This implementation is mathematically equivalent to the previous
    eigendecomposition-based formulation, but will generally differ at the
    level of floating-point rounding (operation order changes). It preserves
    the same validation and error contracts.
    """
    G = check_spd2(G, tol=0.0, symmetrize=True)

    w = eigvals2_spd(G)

    if eps is None:
        if np.any(w <= 0.0):
            # Keep identical error contract to the prior implementation.
            raise ValueError(f"log_spd: G must be SPD; eigenvalues={w}")
        w0c = float(w[0])
        w1c = float(w[1])
    else:
        if eps <= 0.0:
            raise ValueError("log_spd: eps must be > 0 when provided")

        # Match prior behavior: when eps is supplied we *clamp* eigenvalues,
        # even if the closed-form eigenvalues hit 0 due to cancellation.
        # If flooring is actually needed, fall back to the previous
        # eigendecomposition path to preserve edge-case behavior exactly.
        if float(w[0]) < float(eps) or float(w[1]) < float(eps):
            wf, Q = eigh2_sym(G, symmetrize=False)
            wf = np.maximum(wf, eps)
            return sym2((Q * np.log(wf)) @ Q.T)

        w0c = float(w[0])
        w1c = float(w[1])

    w0 = float(w[0])
    w1 = float(w[1])
    delta = w1 - w0

    y0 = float(np.log(w0c))
    y1 = float(np.log(w1c))

    if delta == 0.0:
        beta = 1.0 / w0
    else:
        # Improve accuracy for close eigenvalues with log1p when no flooring
        # occurred (avoid catastrophic cancellation in log(w1)-log(w0)).
        if abs(delta) <= 1e-8 * max(abs(w0), abs(w1), 1.0):
            ydiff = float(np.log1p(delta / w0))
            beta = ydiff / delta
        else:
            beta = (y1 - y0) / delta

    alpha = y0 - beta * w0
    return _affine_combo_sym2(G, alpha, beta)


def sqrt_spd(G: np.ndarray) -> np.ndarray:
    """Principal matrix square root for 2×2 SPD (eigenvalue-only, no matmul)."""
    G = check_spd2(G, tol=0.0, symmetrize=True)

    w = eigvals2_spd(G)
    if np.any(w <= 0.0):
        raise ValueError(f"sqrt_spd: G must be SPD; eigenvalues={w}")

    w0 = float(w[0])
    w1 = float(w[1])

    s0 = float(np.sqrt(w0))
    s1 = float(np.sqrt(w1))

    # Stable divided difference for sqrt: (s1 - s0)/(w1 - w0) = 1/(s0 + s1)
    beta = 1.0 / (s0 + s1)
    alpha = s0 - beta * w0
    return _affine_combo_sym2(G, alpha, beta)


def invsqrt_spd(G: np.ndarray) -> np.ndarray:
    """Inverse principal square root for 2×2 SPD (eigenvalue-only, no matmul)."""
    G = check_spd2(G, tol=0.0, symmetrize=True)

    w = eigvals2_spd(G)
    if np.any(w <= 0.0):
        raise ValueError(f"invsqrt_spd: G must be SPD; eigenvalues={w}")

    w0 = float(w[0])
    w1 = float(w[1])

    s0 = float(np.sqrt(w0))
    s1 = float(np.sqrt(w1))
    invs0 = 1.0 / s0

    # Stable divided difference for invsqrt:
    # (1/s1 - 1/s0)/(w1 - w0) = -1 / ((s0+s1)*s0*s1)
    beta = -1.0 / ((s0 + s1) * s0 * s1)
    alpha = invs0 - beta * w0
    return _affine_combo_sym2(G, alpha, beta)


def _power_spd_from_spectrum(
    G: np.ndarray,
    *,
    w0: float,
    w1: float,
    power: float,
) -> np.ndarray:
    """Evaluate a real matrix power from an unchanged two-value spectrum."""
    y0 = float(w0**power)
    y1 = float(w1**power)
    delta = w1 - w0

    if delta == 0.0:
        return _affine_combo_sym2(G, alpha=y0, beta=0.0)

    beta = (y1 - y0) / delta
    if w0 > 0.0:
        relative_gap = delta / w0
        if abs(relative_gap) <= 1e-8:
            exponent_gap = power * float(np.log1p(relative_gap))
            beta = (w0 ** (power - 1.0)) * float(np.expm1(exponent_gap)) / relative_gap

    alpha = y0 - beta * w0
    return _affine_combo_sym2(G, alpha, beta)


def _power_spd_negative(
    G: np.ndarray,
    *,
    w0: float,
    w1: float,
    power: float,
    eps: float | None,
) -> np.ndarray:
    """Evaluate a negative power, flooring eigenvalues only when required."""
    if eps is None or eps <= 0.0:
        raise ValueError("power_spd: negative powers require eps > 0 (e.g., 1e-15).")

    if w0 < float(eps) or w1 < float(eps):
        eigenvalues, eigenvectors = eigh2_sym(G, symmetrize=False)
        eigenvalues = np.maximum(eigenvalues, eps)
        return sym2((eigenvectors * (eigenvalues**power)) @ eigenvectors.T)

    return _power_spd_from_spectrum(
        G,
        w0=w0,
        w1=w1,
        power=power,
    )


def _power_spd_nonnegative(
    G: np.ndarray,
    *,
    eigenvalues: np.ndarray,
    power: float,
    clamp_tol: float,
) -> np.ndarray:
    """Evaluate a nonnegative power with the established PSD hygiene."""
    if clamp_tol > 0.0 and np.any((eigenvalues < 0.0) & (eigenvalues >= -clamp_tol)):
        clamped, eigenvectors = _eigh2_psd_clamp(
            G,
            symmetrize=False,
            clamp_tol=clamp_tol,
        )
        return sym2((eigenvectors * (clamped**power)) @ eigenvectors.T)

    if np.any(eigenvalues < 0.0):
        raise ValueError(
            f"Matrix expected PSD but has negative eigenvalues: {eigenvalues}"
        )

    return _power_spd_from_spectrum(
        G,
        w0=float(eigenvalues[0]),
        w1=float(eigenvalues[1]),
        power=power,
    )


def power_spd(
    G: np.ndarray,
    power: float,
    *,
    eps: float | None = None,
    clamp_tol: float = 1e-15,
) -> np.ndarray:
    """Return a real power of a symmetric positive-semidefinite matrix.

    For nonnegative powers, eigenvalues in ``[-clamp_tol, 0)`` are clamped to
    zero. Materially negative eigenvalues raise ``ValueError``. Negative powers
    require ``eps > 0`` and floor eigenvalues to that value when necessary.
    """
    G = sym2(_as_2x2(G, dtype=float, name="power_spd"))

    if power == 0.0:
        return np.eye(2, dtype=float)

    eigenvalues = eigvals2_spd(G)
    if power < 0.0:
        return _power_spd_negative(
            G,
            w0=float(eigenvalues[0]),
            w1=float(eigenvalues[1]),
            power=power,
            eps=eps,
        )

    return _power_spd_nonnegative(
        G,
        eigenvalues=eigenvalues,
        power=power,
        clamp_tol=clamp_tol,
    )


def _check_spd2_scale_aware(
    G: np.ndarray,
    *,
    tol: float,
    name: str,
) -> np.ndarray:
    """Validate SPD after removing the matrix's absolute scale.

    ``check_spd2`` interprets ``tol`` as an absolute margin on the first
    principal minor and determinant.  AIRM operations should not reject two
    geometrically identical metrics merely because both are expressed at a
    small absolute scale, so these entry points validate a normalized matrix
    and return the original symmetrized metric.
    """
    tol_f = float(tol)
    if not np.isfinite(tol_f) or tol_f < 0.0:
        raise ValueError(f"{name}: tol must be finite and nonnegative")

    A = _as_2x2(G, dtype=float, name=name)
    A = sym2(A)
    scale = float(np.max(np.abs(A)))
    if not np.isfinite(scale) or scale <= 0.0:
        raise ValueError(f"{name}: matrix scale must be finite and positive")
    check_spd2(A / scale, tol=tol_f, symmetrize=False)
    return A


def geodesic_spd(
    G_A: np.ndarray,
    G_B: np.ndarray,
    t: float,
    *,
    clamp_tol: float = 1e-14,
    eps: float = 1e-16,
) -> np.ndarray:
    """Affine-invariant geodesic interpolation on SPD(2).

    Implements:
        G(t) = G_A^{1/2} (G_A^{-1/2} G_B G_A^{-1/2})^t G_A^{1/2}

    Parameters
    ----------
    G_A, G_B
        SPD Gram tensors, array-like shape ``(2,2)``.
    t
        Geodesic parameter. Typical range is ``0 <= t <= 1``.
    clamp_tol
        Dimensionless positivity margin applied to normalized input metrics and
        the PSD clamp tolerance used for the relative-metric matrix power.
    eps
        Positive eigenvalue floor used by :func:`power_spd` when required.

    Returns
    -------
    np.ndarray
        Interpolated SPD matrix of shape ``(2,2)``.
    """
    A = _check_spd2_scale_aware(G_A, tol=float(clamp_tol), name="geodesic_spd.G_A")
    B = _check_spd2_scale_aware(G_B, tol=float(clamp_tol), name="geodesic_spd.G_B")

    t_f = float(t)

    # sqrt_spd / invsqrt_spd are exact SPD(2) primitives; `eps` is handled
    # by power_spd (and by the caller's own regularization policy).
    A_sqrt = sqrt_spd(A)
    A_inv_sqrt = invsqrt_spd(A)
    M = sym2(A_inv_sqrt @ B @ A_inv_sqrt)
    M_t = power_spd(M, power=t_f, clamp_tol=float(clamp_tol), eps=float(eps))
    return sym2(A_sqrt @ M_t @ A_sqrt)


__all__ = [
    "check_spd2",
    "cholesky2_spd",
    "chol_upper",
    "inv2_spd",
    "log_spd",
    "sqrt_spd",
    "invsqrt_spd",
    "power_spd",
    "gram_2d",
    "geodesic_spd",
]
