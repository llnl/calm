"""Stress tests for 2D strain-metric helpers.

These tests focus on numerical stability, invariances, and simple closed-form
cases for the two primary 2D strain summaries used by calm:

- :class:`calm.interface.types.AffineInvariantStrain2D`
- :class:`calm.interface.types.ZMStrain2D`

The intent is to catch regressions in the metric definitions (or the
canonicalization/sorting logic) early.
"""

from __future__ import annotations

import math

import numpy as np

from calm.interface.types import AffineInvariantStrain2D, ZMStrain2D


def _rot(theta: float) -> np.ndarray:
    c = math.cos(theta)
    s = math.sin(theta)
    return np.array([[c, -s], [s, c]], dtype=float)


def _basis(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return a 2x2 basis matrix with vectors as columns."""

    a = np.asarray(a, dtype=float).reshape(2)
    b = np.asarray(b, dtype=float).reshape(2)
    return np.column_stack([a, b])


def test_zmstrain_same_bases_is_zero() -> None:
    A = _basis([2.0, 0.0], [0.0, 3.0])
    zm = ZMStrain2D.from_bases(A, A)

    assert np.isclose(zm.rel_da, 0.0)
    assert np.isclose(zm.rel_db, 0.0)
    assert np.isclose(zm.d_gamma_deg, 0.0)


def test_zmstrain_invariant_under_common_rotation() -> None:
    A = _basis([2.0, 0.0], [0.5, 1.7])
    B = _basis([2.1, 0.0], [0.6, 1.6])

    zm0 = ZMStrain2D.from_bases(A, B)

    R = _rot(theta=0.7)
    zm1 = ZMStrain2D.from_bases(R @ A, R @ B)

    assert np.isclose(zm1.rel_da, zm0.rel_da)
    assert np.isclose(zm1.rel_db, zm0.rel_db)
    assert np.isclose(zm1.d_gamma_deg, zm0.d_gamma_deg)


def test_zmstrain_invariant_under_column_permutation_and_sign() -> None:
    A = _basis([2.0, 0.0], [0.5, 1.7])
    B = _basis([2.1, 0.0], [0.6, 1.6])

    zm0 = ZMStrain2D.from_bases(A, B)

    # Swap columns (basis vectors) and flip sign of one vector.
    A2 = np.column_stack([-A[:, 1], A[:, 0]])
    B2 = np.column_stack([-B[:, 1], B[:, 0]])

    zm1 = ZMStrain2D.from_bases(A2, B2)

    assert np.isclose(zm1.rel_da, zm0.rel_da)
    assert np.isclose(zm1.rel_db, zm0.rel_db)
    assert np.isclose(zm1.d_gamma_deg, zm0.d_gamma_deg)


def test_affine_invariant_diagonal_case_matches_closed_form() -> None:
    # Basis A is diagonal; basis B scales x and y independently.
    A = _basis([2.0, 0.0], [0.0, 3.0])

    sx = 1.05
    sy = 0.97
    B = _basis([2.0 * sx, 0.0], [0.0, 3.0 * sy])

    G_A = A.T @ A
    G_B = B.T @ B

    ai = AffineInvariantStrain2D.from_grams(G_A, G_B)

    # Closed form for diagonal case:
    # principal_strains = [ln(sx), ln(sy)]
    e1 = math.log(sx)
    e2 = math.log(sy)

    d_cell_expected = 2.0 * math.sqrt(e1 * e1 + e2 * e2)
    d_area_expected = math.sqrt(2.0) * abs(e1 + e2)
    d_shape_expected = math.sqrt(2.0) * abs(e1 - e2)

    assert np.isclose(ai.d_cell, d_cell_expected)
    assert np.isclose(ai.d_area, d_area_expected)
    assert np.isclose(ai.d_shape, d_shape_expected)


def test_affine_invariant_shape_distance_is_stable_near_isotropic() -> None:
    eps = np.array([0.05, 0.05 + 1.0e-10])
    G_A = np.eye(2)
    G_B = np.diag(np.exp(2.0 * eps))

    ai = AffineInvariantStrain2D.from_grams(G_A, G_B)
    e1, e2 = ai.principal_strains
    expected = math.sqrt(2.0) * abs(e1 - e2)

    assert expected > 0.0
    assert np.isclose(ai.d_shape, expected, rtol=1.0e-14, atol=0.0)


def test_affine_invariant_invariant_under_common_rotation() -> None:
    A = _basis([2.0, 0.0], [0.5, 1.7])
    B = _basis([2.1, 0.0], [0.6, 1.6])

    G_A = A.T @ A
    G_B = B.T @ B

    ai0 = AffineInvariantStrain2D.from_grams(G_A, G_B)

    R = _rot(theta=1.1)
    A2 = R @ A
    B2 = R @ B

    ai1 = AffineInvariantStrain2D.from_grams(A2.T @ A2, B2.T @ B2)

    assert np.isclose(ai1.d_cell, ai0.d_cell)
    assert np.isclose(ai1.d_area, ai0.d_area)
    assert np.isclose(ai1.d_shape, ai0.d_shape)


def test_ai_and_zm_metrics_are_finite_for_random_invertible_bases() -> None:
    rng = np.random.default_rng(0)

    for _ in range(50):
        # Construct random invertible-ish bases by sampling and rejecting tiny det.
        while True:
            A = rng.normal(size=(2, 2))
            if abs(np.linalg.det(A)) > 0.2:
                break
        while True:
            B = rng.normal(size=(2, 2))
            if abs(np.linalg.det(B)) > 0.2:
                break

        zm = ZMStrain2D.from_bases(A, B)
        ai = AffineInvariantStrain2D.from_grams(A.T @ A, B.T @ B)

        assert np.isfinite(zm.rel_da)
        assert np.isfinite(zm.rel_db)
        assert np.isfinite(zm.d_gamma_deg)

        assert np.isfinite(ai.d_cell)
        assert np.isfinite(ai.d_area)
        assert np.isfinite(ai.d_shape)
