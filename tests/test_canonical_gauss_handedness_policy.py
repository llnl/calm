"""Focused tests for calm's 2D handedness normalization policy.

These tests are intentionally small and deterministic:

- If the input basis is left-handed, calm repairs it using a deterministic
  det=-1 unimodular right-multiplication.
- The repair is reflected in the returned unimodular mapping.

This turns the (otherwise easy-to-miss) warning into a stable, unit-tested
canonicalization contract.
"""

from __future__ import annotations

import numpy as np

from calm.symmetry.reduction import canonical_gauss_reduce_2d


_HANDEDNESS_REPAIR = np.asarray([[1, 0], [0, -1]], dtype=int)


def _inv_unimodular_2x2(U: np.ndarray) -> np.ndarray:
    """Exact inverse of a 2x2 unimodular integer matrix."""

    Ui = np.asarray(U, dtype=int)
    det = int(round(float(np.linalg.det(Ui))))
    assert det in (+1, -1)

    # Adjugate for 2x2
    adj = np.asarray([[Ui[1, 1], -Ui[0, 1]], [-Ui[1, 0], Ui[0, 0]]], dtype=int)
    return adj // det


def test_left_handed_input_is_repaired_deterministically_and_reflected_in_U() -> None:
    """A left-handed basis should canonicalize identically to its repaired form.

    Additionally, the returned unimodular mapping should differ by exactly the
    deterministic handedness repair matrix.
    """

    A_left = np.asarray([[2.0, 0.7], [0.1, -1.9]], dtype=float)
    assert np.linalg.det(A_left) < 0.0

    B0, U0, R0 = canonical_gauss_reduce_2d(
        A_left,
        tol=1e-12,
        strict_handedness=False,
        warn_on_handedness_repair=False,
    )
    assert np.linalg.det(B0) > 0.0

    # Apply the deterministic unimodular handedness repair explicitly.
    A_rep = A_left @ _HANDEDNESS_REPAIR
    assert np.linalg.det(A_rep) > 0.0

    B1, U1, R1 = canonical_gauss_reduce_2d(
        A_rep,
        tol=1e-12,
        strict_handedness=False,
        warn_on_handedness_repair=False,
    )
    assert np.linalg.det(B1) > 0.0

    # Canonicalized reduced basis should be identical (up to tight float tolerance).
    assert np.allclose(B1, B0, atol=1e-12, rtol=1e-12)

    # The mapping difference must be exactly the handedness repair matrix.
    #
    # Intuition: reduction(A_left) performs A_left -> A_left @ _HANDEDNESS_REPAIR
    # first, then executes the same integer reduction steps as reduction(A_rep).
    # Therefore: U0 == _HANDEDNESS_REPAIR @ U1.
    invU1 = _inv_unimodular_2x2(U1)
    delta = U0 @ invU1
    assert np.array_equal(delta, _HANDEDNESS_REPAIR)

    # Consistency relation: B_red = R @ (A @ U).
    assert np.allclose(B0, R0 @ (A_left @ U0), atol=1e-10, rtol=1e-10)
    assert np.allclose(B1, R1 @ (A_rep @ U1), atol=1e-10, rtol=1e-10)
