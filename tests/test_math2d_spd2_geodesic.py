import numpy as np

from calm.math2d.spd2x2 import geodesic_spd
from reference.spd_reference import (
    airm_distance_reference,
    is_spd_reference,
)


def _random_spd(rng: np.random.Generator) -> np.ndarray:
    """Generate a random 2x2 SPD matrix."""

    A = rng.normal(size=(2, 2))
    M = A @ A.T
    # Add a small diagonal for numerical safety.
    M = M + 0.5 * np.eye(2)
    return M


def test_geodesic_spd_endpoints_and_spd_property() -> None:
    rng = np.random.default_rng(0)
    A = _random_spd(rng)
    B = _random_spd(rng)

    G0 = geodesic_spd(A, B, 0.0)
    assert np.allclose(G0, A)

    G1 = geodesic_spd(A, B, 1.0)
    assert np.allclose(G1, B)

    for t in (0.25, 0.5, 0.75):
        G = geodesic_spd(A, B, t)
        assert is_spd_reference(G)


def test_affine_invariant_distance_is_linear_along_geodesic() -> None:
    rng = np.random.default_rng(123)
    A = _random_spd(rng)
    B = _random_spd(rng)

    d_AB = airm_distance_reference(A, B)
    assert d_AB > 0.0

    for t in (0.0, 0.2, 0.5, 0.9, 1.0):
        G = geodesic_spd(A, B, t)
        d = airm_distance_reference(A, G)
        assert np.isclose(d, t * d_AB, atol=1e-10, rtol=1e-9)


def test_affine_invariant_distance_is_independent_of_common_metric_scale() -> None:
    A = np.array([[2.0, 0.3], [0.3, 1.0]])
    B = np.array([[1.4, -0.2], [-0.2, 2.2]])
    reference = airm_distance_reference(A, B)

    for scale in (1.0e-12, 1.0e-8, 1.0e8):
        distance = airm_distance_reference(scale * A, scale * B)
        assert np.isclose(distance, reference, atol=1.0e-11, rtol=1.0e-11)


def test_affine_invariant_geodesic_is_covariant_under_common_metric_scale() -> None:
    A = np.array([[2.0, 0.3], [0.3, 1.0]])
    B = np.array([[1.4, -0.2], [-0.2, 2.2]])
    t = 0.37
    reference = geodesic_spd(A, B, t)

    for scale in (1.0e-12, 1.0e-8, 1.0e8):
        scaled = geodesic_spd(scale * A, scale * B, t)
        assert np.allclose(
            scaled,
            scale * reference,
            atol=1.0e-11 * scale,
            rtol=1.0e-11,
        )
