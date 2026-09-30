import numpy as np

from calm.slab.oriented._primitive import compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_validate_surface_basis_scale_aware_small_and_large_cells():
    for a in [1e-4, 1.0, 1e4]:
        A_prim = simple_cubic_cell(a)
        A_conv = A_prim.copy()
        u, v, w, m = compute_primitive_surface_basis(2, 1, 3, A_conv, A_prim)
        ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=3, atol=1e-8, rtol=1e-10)
        assert ok, info
