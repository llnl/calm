import numpy as np
from calm.slab.oriented._primitive import compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_compute_primitive_surface_basis_cubic_110():
    A_prim = simple_cubic_cell(1.0)
    # For simple cubic primitive == conventional
    A_conv = A_prim.copy()

    u, v, w, m = compute_primitive_surface_basis(1, 1, 0, A_conv, A_prim)
    ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
    assert ok, f"Validation failed: {info}"


def test_compute_primitive_surface_basis_various_millers():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()
    millers = [
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
        (1, 1, 0),
        (1, 1, 1),
        (2, 1, 0),
        (2, 1, 1),
        (3, 2, 1),
    ]
    for h, k, l in millers:
        u, v, w, m = compute_primitive_surface_basis(h, k, l, A_conv, A_prim)
        ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
        assert ok, f"Validation failed for {(h,k,l)}: {info}"
