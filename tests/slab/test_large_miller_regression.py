import numpy as np

from calm.slab.oriented._primitive import compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_large_miller_regression_cases():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()
    cases = [
        (7, 5, 3),
        (11, 7, 5),
        (13, 8, 5),
        (17, 11, 6),
        (19, 13, 7),
        (29, 17, 11),
        (-23, 14, 9),
    ]

    for h, k, l in cases:
        u, v, w, m = compute_primitive_surface_basis(h, k, l, A_conv, A_prim)
        assert np.gcd.reduce(np.abs(m)) == 1
        assert int(np.dot(m, u)) == 0
        assert int(np.dot(m, v)) == 0
        cross_uv = np.cross(u, v)
        assert np.array_equal(cross_uv, m)
        assert int(np.dot(m, w)) == 1
        ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
        assert ok, info
