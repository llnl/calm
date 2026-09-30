import numpy as np

from calm.slab.oriented._primitive import _primitive_surface_triplet_from_m, compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_primitive_basis_change_invariance():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()
    m = np.array([2, 1, 3], dtype=int)
    m = m // np.gcd.reduce(np.abs(m))

    S_list = [
        np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=int),
        np.array([[0, 1, 0], [1, 0, 0], [0, 0, -1]], dtype=int),
        np.array([[1, 0, 0], [0, 1, 1], [0, 0, 1]], dtype=int),
    ]

    u, v, w, m0 = compute_primitive_surface_basis(*m.tolist(), A_conv, A_prim)
    ok, info = validate_surface_basis(A_prim, m0, u, v, w, layers=1)
    assert ok, info
    area0 = np.linalg.norm(np.cross(A_prim @ u, A_prim @ v))
    g0 = np.linalg.solve(A_prim.T, m0)

    for S in S_list:
        assert int(round(np.linalg.det(S))) in (-1, 1)
        A_prim_new = A_prim @ S
        m_new = S.T @ m0
        u_new, v_new, w_new = _primitive_surface_triplet_from_m(m_new)

        # Map new integer vectors back to old primitive coordinates
        u_old_coords = S @ u_new
        v_old_coords = S @ v_new
        cross_old = np.cross(u_old_coords, v_old_coords)
        assert np.array_equal(cross_old, int(round(np.linalg.det(S))) * m0) or np.array_equal(cross_old, -int(round(np.linalg.det(S))) * m0)

        area_new = np.linalg.norm(np.cross(A_prim_new @ u_new, A_prim_new @ v_new))
        assert abs(area_new - area0) < max(1e-10, 1e-8 * area0)
        g_new = np.linalg.solve(A_prim_new.T, m_new)
        assert np.linalg.norm(np.cross(g0, g_new)) < 1e-8
