"""Stress tests for 2D canonical Gauss reduction and canonicalization.

These tests provide additional coverage beyond ``tests/test_canonical_gauss_reduction_2d.py``.

They focus on:

- **Right-handedness**: the reduced basis should always have positive signed area.
- **Area preservation**: a unimodular change of basis must not change the lattice area.
- **Boundary stability**: reduction should remain valid near the (a == c) and |b| == a/2
  boundaries that define the canonical 2D Gauss fundamental domain.
- **Metric invariance after canonicalization**: when we canonicalize each lattice via
  reduction, downstream mismatch metrics should be invariant under independent
  unimodular relabelings of each lattice's basis.

The tests here are designed to be deterministic and fast; they use small randomized
suites with a fixed seed.
"""

from __future__ import annotations

import numpy as np


def _rand_full_rank_2x2(rng: np.random.Generator, *, det_min: float = 0.2) -> np.ndarray:
    """Generate a random full-rank 2x2 basis with |det| >= det_min."""

    for _ in range(10_000):
        A = rng.normal(size=(2, 2))
        # Keep values in a reasonable scale to avoid extreme conditioning.
        A *= rng.uniform(0.5, 3.0)
        if abs(np.linalg.det(A)) >= det_min:
            return A
    raise RuntimeError("Failed to generate a full-rank 2x2 basis")


def _rotation_matrix(theta: float) -> np.ndarray:
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    return np.asarray([[c, -s], [s, c]], dtype=float)


def _unimodular_samples() -> list[np.ndarray]:
    """A small, deterministic set of 2x2 unimodular matrices (det=±1)."""

    return [
        np.asarray([[1, 0], [0, 1]], dtype=int),
        np.asarray([[-1, 0], [0, 1]], dtype=int),
        np.asarray([[1, 0], [0, -1]], dtype=int),
        np.asarray([[0, 1], [1, 0]], dtype=int),
        np.asarray([[0, -1], [1, 0]], dtype=int),
        np.asarray([[1, 1], [0, 1]], dtype=int),
        np.asarray([[1, 0], [1, 1]], dtype=int),
        np.asarray([[1, -1], [0, 1]], dtype=int),
        np.asarray([[1, 0], [-1, 1]], dtype=int),
    ]


def _check_gauss_conditions(B: np.ndarray, *, tol: float = 1e-10) -> None:
    """Check the canonical 2D Gauss inequalities on the basis B."""

    a1 = B[:, 0]
    a2 = B[:, 1]

    la2 = float(a1 @ a1)
    lb2 = float(a2 @ a2)
    dot = float(a1 @ a2)

    assert la2 <= lb2 + tol
    assert abs(dot) <= 0.5 * la2 + tol

    # Explicit angle check (redundant but intuitive): 60° <= gamma <= 120°.
    gamma = float(np.degrees(np.arccos(np.clip(dot / np.sqrt(la2 * lb2), -1.0, 1.0))))
    assert 60.0 - 1e-6 <= gamma <= 120.0 + 1e-6


def test_canonical_gauss_reduce_2d_preserves_area_and_handedness() -> None:
    """Reduced basis should be right-handed and preserve area (up to FP tolerance)."""

    from calm.symmetry.reduction import canonical_gauss_reduce_2d

    rng = np.random.default_rng(0)

    for _ in range(100):
        A = _rand_full_rank_2x2(rng)

        # Randomly flip handedness on input.
        if rng.random() < 0.5:
            A = A @ np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=float)

        det_in = float(np.linalg.det(A))

        B, _U, _R = canonical_gauss_reduce_2d(
            A,
            tol=1e-12,
            strict_handedness=False,
            warn_on_handedness_repair=False,
        )

        det_out = float(np.linalg.det(B))
        assert det_out > 0.0

        # Area preservation: |det| should be invariant under unimodular transforms.
        assert np.isclose(abs(det_out), abs(det_in), rtol=1e-10, atol=1e-10)

        _check_gauss_conditions(B, tol=1e-9)


def test_canonical_gauss_reduce_2d_invariant_under_rotation_and_reflection() -> None:
    """Canonicalization should ignore global rotation/reflection of the input basis."""

    from calm.symmetry.reduction import canonical_gauss_reduce_2d

    rng = np.random.default_rng(1)

    for _ in range(25):
        A = _rand_full_rank_2x2(rng)

        B0, _U0, _R0 = canonical_gauss_reduce_2d(
            A,
            tol=1e-12,
            strict_handedness=False,
            warn_on_handedness_repair=False,
        )
        G0 = B0.T @ B0

        # Random rotation
        theta = float(rng.uniform(0.0, 2.0 * np.pi))
        Q = _rotation_matrix(theta)

        B1, _U1, _R1 = canonical_gauss_reduce_2d(
            Q @ A,
            tol=1e-12,
            strict_handedness=False,
            warn_on_handedness_repair=False,
        )
        G1 = B1.T @ B1

        assert np.allclose(G1, G0, atol=1e-9, rtol=1e-9)

        # Reflection (det=-1 orthogonal); Gram invariants should still match.
        F = np.asarray([[1.0, 0.0], [0.0, -1.0]], dtype=float)
        B2, _U2, _R2 = canonical_gauss_reduce_2d(
            F @ A,
            tol=1e-12,
            strict_handedness=False,
            warn_on_handedness_repair=False,
        )
        G2 = B2.T @ B2
        assert np.allclose(G2, G0, atol=1e-9, rtol=1e-9)


def test_canonical_gauss_reduce_2d_boundary_stability_near_square_lattice() -> None:
    """Near the square lattice (a≈c, b≈0), reduction should remain stable and valid."""

    from calm.symmetry.reduction import canonical_gauss_reduce_2d

    # Start from an exact square lattice basis.
    A0 = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=float)

    # Small perturbations should not break validation.
    rng = np.random.default_rng(2)

    for eps in [0.0, 1e-14, 1e-12, 1e-10, 1e-8]:
        for _ in range(25):
            noise = rng.normal(scale=eps, size=(2, 2))
            A = A0 + noise

            # Ensure not singular.
            if abs(np.linalg.det(A)) < 1e-12:
                continue

            B, _U, _R = canonical_gauss_reduce_2d(
                A,
                tol=1e-12,
                strict_handedness=False,
                warn_on_handedness_repair=False,
                )

            _check_gauss_conditions(B, tol=1e-8)


def test_canonicalized_metrics_are_invariant_under_independent_unimodular_relabelings() -> None:
    """After canonicalization, mismatch metrics should be invariant under basis relabeling.

    This test encodes the practical invariance requirement:

    - Start with two in-plane bases A and B.
    - Canonicalize each via 2D canonical Gauss reduction.
    - Compute mismatch metrics using the canonicalized representations.
    - Apply independent unimodular basis changes A->A U_A and B->B U_B.
    - Re-canonicalize and re-compute metrics.

    The metrics must agree.
    """

    from calm.symmetry.reduction import canonical_gauss_reduce_2d
    from calm.interface.types import AffineInvariantStrain2D, ZMStrain2D

    rng = np.random.default_rng(3)

    # Use a small set of samples to keep runtime low while still exercising the logic.
    for _ in range(20):
        A = _rand_full_rank_2x2(rng)
        B = _rand_full_rank_2x2(rng)

        A_can, _UA, _RA = canonical_gauss_reduce_2d(A, tol=1e-12, strict_handedness=False, warn_on_handedness_repair=False)
        B_can, _UB, _RB = canonical_gauss_reduce_2d(B, tol=1e-12, strict_handedness=False, warn_on_handedness_repair=False)

        G_A = A_can.T @ A_can
        G_B = B_can.T @ B_can

        ai0 = AffineInvariantStrain2D.from_grams(G_A, G_B)
        zm0 = ZMStrain2D.from_bases(A_can, B_can)

        for U_A in _unimodular_samples():
            for U_B in _unimodular_samples():
                A2_can, _UA2, _ = canonical_gauss_reduce_2d(A @ U_A, tol=1e-12, strict_handedness=False, warn_on_handedness_repair=False)
                B2_can, _UB2, _ = canonical_gauss_reduce_2d(B @ U_B, tol=1e-12, strict_handedness=False, warn_on_handedness_repair=False)

                G_A2 = A2_can.T @ A2_can
                G_B2 = B2_can.T @ B2_can

                ai1 = AffineInvariantStrain2D.from_grams(G_A2, G_B2)
                zm1 = ZMStrain2D.from_bases(A2_can, B2_can)

                assert np.isclose(ai1.d_cell, ai0.d_cell, atol=1e-10, rtol=1e-10)
                assert np.isclose(
                    ai1.max_abs_principal_strain,
                    ai0.max_abs_principal_strain,
                    atol=1e-10,
                    rtol=1e-10,
                )

                assert np.isclose(zm1.rel_da, zm0.rel_da, atol=1e-10, rtol=1e-10)
                assert np.isclose(zm1.rel_db, zm0.rel_db, atol=1e-10, rtol=1e-10)
                assert np.isclose(zm1.d_gamma_deg, zm0.d_gamma_deg, atol=1e-10, rtol=1e-10)
                assert np.isclose(zm1.rel_dgamma, zm0.rel_dgamma, atol=1e-10, rtol=1e-10)
