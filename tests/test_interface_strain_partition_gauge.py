from __future__ import annotations

import numpy as np

from calm.interface.refinement.partition import strain_partition_inplane
from calm.math2d.spd2x2 import geodesic_spd


def _random_spd_2(rng: np.random.Generator) -> np.ndarray:
    """Generate a well-conditioned random 2x2 SPD matrix."""
    A = rng.normal(size=(2, 2))
    return A.T @ A + np.eye(2) * 0.5


def test_strain_partition_inplane_cholesky_gauge_roundtrip() -> None:
    """The Cholesky lift must define a deterministic, right-handed gauge.

    We test that:
      - X is upper-triangular with positive diagonal (deterministic gauge)
      - X^T X reproduces the affine-invariant target Gram G(t)
      - deformation gradients map each basis to the common target X
    """
    rng = np.random.default_rng(0)
    G_A = _random_spd_2(rng)
    G_B = _random_spd_2(rng)

    # Deterministic bases for each Gram (upper-triangular Cholesky lift)
    # Convention: columns are basis vectors, Gram = S^T S.
    S_A = np.linalg.cholesky(G_A).T
    S_B = np.linalg.cholesky(G_B).T

    alpha = 0.35
    res = strain_partition_inplane(S_A, S_B, alpha=alpha)

    X = res.X
    assert X.shape == (2, 2)

    # Gauge: Cholesky lift -> upper triangular with positive diagonal
    assert np.allclose(X, np.triu(X), atol=1e-12)
    assert np.all(np.diag(X) > 0)

    # X^T X must equal the geodesic target Gram (within numerical tolerance)
    G_t = geodesic_spd(G_A, G_B, alpha)
    assert np.min(np.linalg.eigvalsh(G_t)) > 0.0
    assert np.allclose(X.T @ X, G_t, atol=1e-10)

    # Deformation gradients map each slab basis to X
    assert np.allclose(res.F_A @ S_A, X, atol=1e-10)
    assert np.allclose(res.F_B @ S_B, X, atol=1e-10)


def test_strain_partition_inplane_explicit_gauge_axis_alignment_and_order_invariance() -> None:
    """Assert explicit gauge properties implied by the Cholesky lift.

    The 'upper-triangular + positive diagonal' convention implies:
      - first basis vector lies on the +x axis (y-component = 0, x-component > 0)
      - second basis vector lies in the upper half-plane (y-component > 0)
      - right-handed orientation (det > 0)

    Also, because X is a deterministic function of the target Gram,
    swapping endpoints and mapping alpha -> 1-alpha must yield the same X.
    """
    rng = np.random.default_rng(1)
    G_A = _random_spd_2(rng)
    G_B = _random_spd_2(rng)

    S_A = np.linalg.cholesky(G_A).T
    S_B = np.linalg.cholesky(G_B).T

    alpha = 0.35

    res_ab = strain_partition_inplane(S_A, S_B, alpha=alpha)
    res_ba = strain_partition_inplane(S_B, S_A, alpha=1.0 - alpha)

    X = res_ab.X
    X_swap = res_ba.X

    # Determinism / order invariance at the level of the chosen gauge
    assert np.allclose(X, X_swap, atol=1e-10)

    # Explicit axis-alignment gauge checks.
    # For an upper-triangular basis with columns as vectors:
    #   a1 = (X[0,0], X[1,0]) must lie on +x axis
    #   a2 = (X[0,1], X[1,1]) must have positive y (upper half-plane)
    assert abs(float(X[1, 0])) < 1e-12
    assert float(X[0, 0]) > 0.0
    assert float(X[1, 1]) > 0.0
    assert float(np.linalg.det(X)) > 0.0
