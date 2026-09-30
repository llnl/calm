import numpy as np
from calm.slab.oriented._primitive import compute_primitive_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_miller_transform_conventional_to_primitive_cubic():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()
    # example: (1,1,0)
    u, v, w, m = compute_primitive_surface_basis(1, 1, 0, A_conv, A_prim)
    # In cubic primitive==conventional, so m should equal input (up to sign)
    assert np.gcd.reduce(np.abs(m)) == 1
