import numpy as np
from calm.slab.oriented._primitive import compute_primitive_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def _surface_area(A_prim, u, v):
    return np.linalg.norm(np.cross(A_prim @ u, A_prim @ v))


def test_negative_miller_pairs_equivalent():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()
    pairs = [((1, 1, 0), (-1, -1, 0)), ((1, 1, 1), (-1, -1, -1)), ((2, 1, 3), (-2, -1, -3))]

    for pos, neg in pairs:
        u1, v1, w1, m1 = compute_primitive_surface_basis(*pos, A_conv, A_prim)
        u2, v2, w2, m2 = compute_primitive_surface_basis(*neg, A_conv, A_prim)
        assert abs(_surface_area(A_prim, u1, v1) - _surface_area(A_prim, u2, v2)) < 1e-8
