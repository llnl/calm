import numpy as np

from calm.slab.oriented._primitive import compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def _assert_exact_primitive_surface_certificates(A_conv, A_prim, hkl, layers_values):
    u, v, w, m = compute_primitive_surface_basis(*hkl, A_conv, A_prim, max_denominator=256)

    assert np.gcd.reduce(np.abs(m)) == 1
    assert int(np.dot(m, u)) == 0
    assert int(np.dot(m, v)) == 0
    assert int(np.dot(m, w)) == 1

    cross_uv = np.cross(u, v)
    assert np.array_equal(cross_uv, m)

    for layers in layers_values:
        T = np.column_stack([u, v, layers * w]).astype(int)
        det_t = int(round(np.linalg.det(T)))
        assert det_t == layers

        ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=layers)
        assert ok, info
        assert info["det_T"] == layers
        assert info["expected_det"] == layers


def test_primitive_surface_basis_layer_count_certificate_simple_cubic():
    A_conv = np.eye(3)
    A_prim = np.eye(3)

    for hkl in [(1, 0, 0), (1, 1, 0), (1, 1, 1), (3, 2, 1)]:
        _assert_exact_primitive_surface_certificates(A_conv, A_prim, hkl, [1, 2, 5])


def test_primitive_surface_basis_layer_count_certificate_centered_lattices():
    A_conv = np.eye(3)
    A_fcc_prim = np.array([
        [0.0, 0.5, 0.5],
        [0.5, 0.0, 0.5],
        [0.5, 0.5, 0.0],
    ])
    A_bcc_prim = np.array([
        [0.5, 0.5, -0.5],
        [0.5, -0.5, 0.5],
        [-0.5, 0.5, 0.5],
    ])

    for A_prim, hkl_cases in [
        (A_fcc_prim, [(1, 0, 0), (1, 1, 0), (3, 2, 1)]),
        (A_bcc_prim, [(1, 0, 0), (1, 1, 0), (2, 1, 3)]),
    ]:
        for hkl in hkl_cases:
            _assert_exact_primitive_surface_certificates(A_conv, A_prim, hkl, [1, 3, 4])
