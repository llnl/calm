import numpy as np
import pytest

from calm.slab.oriented._primitive import compute_primitive_surface_basis, primitive_miller_from_conventional
from surface_basis_oracle import validate_surface_basis


def _area_identity(A_prim: np.ndarray, m: np.ndarray, u: np.ndarray, v: np.ndarray) -> None:
    lhs = np.linalg.norm(np.cross(A_prim @ u, A_prim @ v))
    rhs = abs(np.linalg.det(A_prim)) * np.linalg.norm(np.linalg.solve(A_prim.T, m))
    assert abs(lhs - rhs) < max(1e-10, 1e-8 * rhs)


def _assert_parallel(a: np.ndarray, b: np.ndarray, atol: float = 1e-8) -> None:
    assert np.linalg.norm(np.cross(a, b)) < atol


def test_fcc_conventional_to_primitive_millers():
    # Column convention, a = 1
    A_conv = np.eye(3)
    A_prim = np.array([
        [0.0, 0.5, 0.5],
        [0.5, 0.0, 0.5],
        [0.5, 0.5, 0.0],
    ])

    cases = {
        (1, 0, 0): np.array([0, 1, 1]),
        (1, 1, 0): np.array([1, 1, 2]),
        (1, 1, 1): np.array([1, 1, 1]),
        (3, 2, 1): np.array([3, 4, 5]),
    }

    P = np.linalg.solve(A_prim, A_conv)
    for hkl, expected in cases.items():
        u, v, w, m = compute_primitive_surface_basis(*hkl, A_conv, A_prim)
        assert np.gcd.reduce(np.abs(m)) == 1
        _assert_parallel(P.T @ m, np.array(hkl, dtype=float))
        _assert_parallel(m.astype(float), expected.astype(float))
        ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
        assert ok, info
        _area_identity(A_prim, m, u, v)


def test_bcc_conventional_to_primitive_millers():
    A_conv = np.eye(3)
    A_prim = np.array([
        [0.5, 0.5, -0.5],
        [0.5, -0.5, 0.5],
        [-0.5, 0.5, 0.5],
    ])

    cases = {
        (1, 0, 0): np.array([1, 1, -1]),
        (1, 1, 0): np.array([1, 0, 0]),
        (1, 1, 1): np.array([1, 1, 1]),
        (2, 1, 3): np.array([0, 2, 1]),
    }

    P = np.linalg.solve(A_prim, A_conv)
    for hkl, expected in cases.items():
        u, v, w, m = compute_primitive_surface_basis(*hkl, A_conv, A_prim)
        assert np.gcd.reduce(np.abs(m)) == 1
        _assert_parallel(P.T @ m, np.array(hkl, dtype=float))
        _assert_parallel(m.astype(float), expected.astype(float))
        ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
        assert ok, info
        _area_identity(A_prim, m, u, v)


def test_rational_transform_failure_mode_max_denominator_too_small():
    A_prim = np.eye(3)
    A_conv = np.diag([1.0, np.sqrt(2.0), 1.0])
    with pytest.raises(ValueError, match="Rationalized basis transform does not reproduce|parallel to the conventional"):
        primitive_miller_from_conventional(A_conv, A_prim, (1, 0, 0), max_denominator=1)
