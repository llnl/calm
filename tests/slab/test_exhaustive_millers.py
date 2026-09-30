import numpy as np
from calm.slab.oriented._primitive import compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_exhaustive_small_millers():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()

    rng = range(-3, 4)  # [-3,3]
    for h in rng:
        for k in rng:
            for l in rng:
                if h == 0 and k == 0 and l == 0:
                    continue
                try:
                    u, v, w, m = compute_primitive_surface_basis(h, k, l, A_conv, A_prim)
                except ValueError:
                    # Some pathological cases may raise; treat as failure
                    raise

                ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
                assert ok, f"Failed for {(h,k,l)}: {info}"
