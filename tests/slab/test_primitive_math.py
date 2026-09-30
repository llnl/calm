import numpy as np

from calm.slab.oriented import _primitive as pm


def test_primitive_miller_conventional_identity():
    # For identical primitive and conventional bases, primitive miller == conv miller
    A_conv = np.eye(3) * 4.05
    A_prim = A_conv.copy()
    h_conv = (1, 1, 1)
    m = pm.primitive_miller_from_conventional(A_conv, A_prim, h_conv)
    assert np.array_equal(m, np.array([1, 1, 1], dtype=int))
