"""Stress tests for 2D canonical Gauss reduction.

These tests are intentionally lightweight but cover important invariants:
- right-handed reduced surface cells (positive signed area)
- 2D canonical Gauss inequalities
- determinism under unimodular basis changes

The intent is to catch regressions that could silently corrupt downstream metrics.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from calm.exceptions import SurfaceCellHandednessError, SurfaceCellHandednessWarning
from calm.symmetry.reduction import canonical_gauss_reduce_2d


def _gamma_deg(v1: np.ndarray, v2: np.ndarray) -> float:
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 == 0.0 or n2 == 0.0:
        return float("nan")
    c = float(np.dot(v1, v2) / (n1 * n2))
    # Clamp for numerical safety
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


def _assert_gauss_invariants(B_red: np.ndarray, *, tol: float = 1e-8) -> None:
    assert B_red.shape == (2, 2)

    det = float(np.linalg.det(B_red))
    assert det > 0.0

    v1 = B_red[:, 0]
    v2 = B_red[:, 1]

    a = float(np.dot(v1, v1))
    b = float(2.0 * np.dot(v1, v2))
    c = float(np.dot(v2, v2))

    # 2D canonical Gauss conditions
    assert a <= c + 10.0 * tol
    assert abs(b) <= a + 10.0 * tol

    # Embedded canonical frame: v1 on +x axis, v2 in upper half-plane
    assert B_red[0, 0] > 0.0
    assert abs(B_red[1, 0]) <= 1e-7
    assert B_red[1, 1] > 0.0

    # Angle bounds implied by conditions (gamma in [60, 120])
    gamma = _gamma_deg(v1, v2)
    assert 60.0 - 1e-4 <= gamma <= 120.0 + 1e-4


def test_canonical_gauss_reduce_2d_invariants_random() -> None:
    rng = np.random.default_rng(0)

    n = 200
    got = 0
    while got < n:
        A = rng.normal(size=(2, 2))
        det = float(np.linalg.det(A))
        if not np.isfinite(det) or abs(det) < 5e-2:
            continue

        B_red, U, R = canonical_gauss_reduce_2d(A, tol=1e-12, warn_on_handedness_repair=False)

        _assert_gauss_invariants(B_red)

        assert U.shape == (2, 2)
        assert np.allclose(U, np.rint(U))
        detU = int(round(float(np.linalg.det(U))))
        assert abs(detU) == 1

        assert R.shape == (2, 2)
        assert np.allclose(R.T @ R, np.eye(2), atol=1e-8)

        got += 1


def test_canonical_gauss_reduce_2d_left_handed_guardrails() -> None:
    # A simple left-handed basis (negative determinant)
    A = np.asarray([[1.0, 0.0], [0.0, -2.0]])

    with pytest.warns(SurfaceCellHandednessWarning):
        B_red, _, _ = canonical_gauss_reduce_2d(A, tol=1e-12, strict_handedness=False, warn_on_handedness_repair=True)

    assert float(np.linalg.det(B_red)) > 0.0

    with pytest.raises(SurfaceCellHandednessError):
        canonical_gauss_reduce_2d(A, tol=1e-12, strict_handedness=True)


def test_canonical_gauss_reduce_2d_deterministic_under_unimodular_transforms() -> None:
    rng = np.random.default_rng(1)

    # Pick a generic (non-high-symmetry) basis
    A0 = np.asarray([[1.37, 0.23], [0.11, 0.94]], dtype=float)

    # Generate a handful of small unimodular integer matrices
    U_list: list[np.ndarray] = []
    while len(U_list) < 25:
        M = rng.integers(-3, 4, size=(2, 2))
        det = int(round(float(np.linalg.det(M))))
        if abs(det) != 1:
            continue
        U_list.append(M.astype(int))

    B_ref = None
    for U_int in U_list:
        A = A0 @ U_int
        B_red, _, _ = canonical_gauss_reduce_2d(A, tol=1e-12, warn_on_handedness_repair=False)
        _assert_gauss_invariants(B_red)

        if B_ref is None:
            B_ref = B_red
        else:
            assert np.allclose(B_red, B_ref, atol=1e-7)
