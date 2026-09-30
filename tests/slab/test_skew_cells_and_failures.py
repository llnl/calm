import numpy as np
import pytest
from calm.slab.oriented._primitive import compute_primitive_surface_basis, primitive_miller_from_conventional


def test_skew_cells_geometric_invariants():
    cells = [
        np.array([[3.0, 0.2, 0.1], [0.0, 2.5, 0.3], [0.0, 0.0, 4.0]]).T,
        np.array([[2.0, 0.9, 0.4], [0.1, 3.5, 0.2], [0.3, 0.7, 5.0]]).T,
        np.array([[1000.0, 0.0, 0.0], [0.0, 0.01, 0.0], [0.2, 0.3, 10.0]]).T,
    ]
    hkl = (2, 1, 3)
    for A_prim in cells:
        A_conv = A_prim.copy()
        u, v, w, m = compute_primitive_surface_basis(*hkl, A_conv, A_prim)
        g = np.linalg.solve(A_prim.T, m)
        assert abs(np.dot(g, A_prim @ u)) < 1e-8 * max(np.linalg.norm(g), np.linalg.norm(A_prim @ u), 1.0)
        assert abs(np.dot(g, A_prim @ v)) < 1e-8 * max(np.linalg.norm(g), np.linalg.norm(A_prim @ v), 1.0)
        lhs = np.linalg.norm(np.cross(A_prim @ u, A_prim @ v))
        rhs = abs(np.linalg.det(A_prim)) * np.linalg.norm(g)
        assert abs(lhs - rhs) < max(1e-8, 1e-8 * rhs)




def test_failure_modes():
    A = np.eye(3)
    with pytest.raises(ValueError, match="Miller indices cannot all be zero|cannot all be zero"):
        primitive_miller_from_conventional(A, A, (0, 0, 0))

    A_sing = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    with pytest.raises(ValueError, match="nonsingular|singular|commensurate"):
        compute_primitive_surface_basis(1, 0, 0, A, A_sing)

    A_conv_bad = np.diag([1.0, np.sqrt(2.0), 1.0])
    with pytest.raises(ValueError, match="Rationalized basis transform does not reproduce|parallel to the conventional"):
        primitive_miller_from_conventional(A_conv_bad, A, (1, 0, 0), max_denominator=1)
