"""benchmarks.signature

Canonical, cross-tool match signatures for benchmarking.

Why signatures?
---------------
Raw match lists are *not* directly comparable across tools because they can differ
in (i) duplicate handling, (ii) reduction conventions, and (iii) near-boundary
tie-breaking. To compare outputs robustly, we compute a compact "signature" for
each supercell lattice based on a canonicalized Gram tensor.

The signature is designed for:
- de-duplication ("unique match counts")
- set intersections across tools ("which matches are truly missing?")

This module is intentionally lightweight and **does not** depend on spglib.

Implementation
--------------
We compute a deterministic reduced 2D basis and then quantize the reduced Gram
tensor G = S_red^T S_red into an integer triple (g11, g12, g22) using a scale.

When CALM is importable, we reuse its deterministic 2D reduction. Otherwise,
we fall back to a small deterministic 2D Gauss reduction. External matching
packages never define CALM benchmark canonicalization.

"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def _sym(G: np.ndarray) -> np.ndarray:
    return 0.5 * (G + G.T)


def _gauss_reduce_2d(A: np.ndarray, *, max_iter: int = 100) -> np.ndarray:
    """A minimal 2D Gauss reduction for fallback signature canonicalization.

    Notes
    -----
    - This is *not* a full Niggli reduction in higher dimensions, but in 2D it
      produces a standard reduced basis for generic metrics.
    - Near-degenerate cases (square/hex boundaries) are handled heuristically.
    """

    A = np.asarray(A, float)
    if A.shape != (2, 2):
        raise ValueError("A must be (2,2)")
    a = A[:, 0].copy()
    b = A[:, 1].copy()

    def norm2(v):  # squared norm
        return float(np.dot(v, v))

    # Handedness: force det>0 by flipping b if needed.
    if float(np.linalg.det(np.column_stack([a, b]))) < 0.0:
        b = -b

    for _ in range(int(max_iter)):
        if norm2(b) < norm2(a) - 1e-18:
            a, b = b, a

        mu = float(np.dot(a, b) / max(1e-18, norm2(a)))
        m = int(np.round(mu))
        b_new = b - m * a

        if norm2(b_new) < norm2(b) - 1e-18:
            b = b_new
            continue

        # Finalize: enforce non-obtuse angle.
        if float(np.dot(a, b)) < 0.0:
            b = -b
        break

    return np.column_stack([a, b])


def canonical_reduced_basis_2d(
    S2: np.ndarray,
    *,
    tol: float = 1e-12,
    strict: bool = False,
) -> np.ndarray:
    """Return a deterministic reduced 2D basis for signature computation."""

    S2 = np.asarray(S2, float)
    if S2.shape != (2, 2):
        raise ValueError("S2 must be (2,2)")

    # Preferred: CALM's deterministic canonical reducer.
    try:
        from calm.symmetry.reduction import canonical_gauss_reduce_2d

        S_red, _, _ = canonical_gauss_reduce_2d(
            S2,
            tol=float(tol),
            strict_handedness=bool(strict),
        )
        S_red = np.asarray(S_red, float)
        if S_red.shape != (2, 2):
            raise ValueError(
                "canonical_gauss_reduce_2d returned unexpected shape"
            )
        return S_red
    except Exception:
        # Fallback: minimal Gauss reduction.
        return _gauss_reduce_2d(S2)

def canonicalize_2d(
    S2: np.ndarray,
    *,
    tol: float = 1e-12,
    strict: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Canonicalize a 2D basis and return (S_red, U_sup, R_sup).

    This helper exists for the benchmark harness only.

    If CALM is importable, we delegate to
    ``calm.symmetry.reduction.canonical_gauss_reduce_2d`` so benchmark
    canonicalization matches the production implementation.

    Otherwise, we fall back to a small deterministic Gauss-like reduction
    and return identity transforms for (U_sup, R_sup).
    """
    S2 = np.asarray(S2, dtype=float)

    # Prefer CALM's canonicalization if available.
    try:
        from calm.symmetry.reduction import canonical_gauss_reduce_2d

        S_red, U_sup, R_sup = canonical_gauss_reduce_2d(
            S2,
            tol=tol,
            strict_handedness=strict,
        )
        return (
            np.asarray(S_red, dtype=float),
            np.asarray(U_sup, dtype=int),
            np.asarray(R_sup, dtype=float),
        )
    except Exception:
        # Fallback: basic Gauss reduction (deterministic) with identity transforms.
        S_red = _gauss_reduce_2d(S2)
        U_sup = np.eye(2, dtype=int)
        R_sup = np.eye(2, dtype=float)
        return S_red, U_sup, R_sup



def gram_signature(
    S2: np.ndarray,
    *,
    tol: float = 1e-12,
    scale: float = 1e10,
    strict: bool = False,
) -> Tuple[int, int, int]:
    """Return an integer triple (g11, g12, g22) for the reduced Gram tensor."""

    S_red = canonical_reduced_basis_2d(S2, tol=tol, strict=strict)
    G = _sym(S_red.T @ S_red)

    g11 = int(np.round(float(scale) * float(G[0, 0])))
    g12 = int(np.round(float(scale) * float(G[0, 1])))
    g22 = int(np.round(float(scale) * float(G[1, 1])))
    return g11, g12, g22


def gram_signature_str(sig: Tuple[int, int, int]) -> str:
    return f"{sig[0]},{sig[1]},{sig[2]}"


def match_signature(
    SA2: np.ndarray,
    SB2: np.ndarray,
    *,
    tol: float = 1e-12,
    scale: float = 1e10,
    strict: bool = False,
) -> Tuple[str, str, str]:
    """Return (sigA_str, sigB_str, pair_sig_str)."""

    sigA = gram_signature(SA2, tol=tol, scale=scale, strict=strict)
    sigB = gram_signature(SB2, tol=tol, scale=scale, strict=strict)

    sA = gram_signature_str(sigA)
    sB = gram_signature_str(sigB)
    pair = f"A:{sA}|B:{sB}"
    return sA, sB, pair
