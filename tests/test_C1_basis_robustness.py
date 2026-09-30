from __future__ import annotations

import numpy as np
import pytest

from calm.symmetry.reduction import canonical_gauss_reduce_2d
from calm.math2d.normal_forms import enumerate_hnf_2d_by_index


def unimodular_generators(max_shear: int = 2):
    U = []
    U.append(np.eye(2, dtype=int))
    U.append(np.array([[0, 1], [1, 0]], dtype=int))
    U.append(np.array([[-1, 0], [0, 1]], dtype=int))
    U.append(np.array([[1, 0], [0, -1]], dtype=int))
    U.append(np.array([[-1, 0], [0, -1]], dtype=int))
    for m in range(-max_shear, max_shear + 1):
        if m == 0:
            continue
        U.append(np.array([[1, m], [0, 1]], dtype=int))
        U.append(np.array([[1, 0], [m, 1]], dtype=int))

    seen = set()
    out = []
    for M in U:
        key = tuple(int(x) for x in M.ravel())
        if key not in seen:
            seen.add(key)
            out.append(M)
    return out


def enforce_right_handed(A: np.ndarray) -> np.ndarray:
    A = np.asarray(A, dtype=float)
    if np.linalg.det(A) < 0:
        A = A.copy()
        A[:, 0] *= -1.0
    return A


def canonical_gram(S_red: np.ndarray) -> np.ndarray:
    G = S_red.T @ S_red
    return 0.5 * (G + G.T)


def gram_signature(G: np.ndarray, *, scale: float = 1e10) -> tuple[int, int, int]:
    """
    Quantized integer signature to avoid float-equality brittleness.
    scale=1e10 implies tolerance ~5e-11 in the raw entry values.
    """
    G = 0.5 * (G + G.T)
    return (
        int(np.rint(G[0, 0] * scale)),
        int(np.rint(G[0, 1] * scale)),
        int(np.rint(G[1, 1] * scale)),
    )


@pytest.mark.parametrize("gauss_tol", [1e-12])
def test_niggli_reduce_invariant_under_unimodular(gauss_tol):
    # A non-degenerate primitive basis kept away from exact reduction boundaries
    A = np.array([[3.1, 0.4],
                  [0.2, 2.3]], dtype=float)
    A = enforce_right_handed(A)

    S0_red, _, _ = canonical_gauss_reduce_2d(A, tol=gauss_tol)
    G0 = canonical_gram(S0_red)

    for U in unimodular_generators(max_shear=2):
        A2 = enforce_right_handed(A @ U)
        S_red, _, _ = canonical_gauss_reduce_2d(A2, tol=gauss_tol)
        G = canonical_gram(S_red)

        assert np.allclose(G, G0, rtol=0.0, atol=1e-10), f"Failed for U=\n{U}"


@pytest.mark.parametrize("k_max", [8, 12])
def test_hnf_enumeration_multiset_invariant_under_unimodular(k_max):
    A = np.array([[3.1, 0.4],
                  [0.2, 2.3]], dtype=float)
    A = enforce_right_handed(A)

    gauss_tol = 1e-12
    scale = 1e10

    def collect(A_in):
        A_in = enforce_right_handed(A_in)
        out = []
        for k in range(1, k_max + 1):
            for H in enumerate_hnf_2d_by_index(k):
                S = A_in @ H
                S = enforce_right_handed(S)
                S_red, _, _ = canonical_gauss_reduce_2d(S, tol=gauss_tol)
                out.append((k, gram_signature(canonical_gram(S_red), scale=scale)))
        out.sort()
        return out

    ref = collect(A)

    for U in unimodular_generators(max_shear=2):
        got = collect(A @ U)
        assert got == ref, f"Enumeration multiset changed under U=\n{U}"