import numpy as np
from calm.slab.oriented._primitive import compute_primitive_surface_basis
from surface_basis_oracle import validate_surface_basis


def simple_cubic_cell(a=1.0):
    return np.array([[a, 0, 0], [0, a, 0], [0, 0, a]]).T


def test_cubic_110_normal_formula_and_determinant():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()

    # Compute basis
    u, v, w, m = compute_primitive_surface_basis(1, 1, 0, A_conv, A_prim)

    # Verify primitive in-plane kernel
    ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=1)
    assert ok, f"Validation failed: {info}"

    # Verify oriented normal computed via m_oriented is parallel to B_prim @ m
    T = np.column_stack([u, v, 1 * w]).astype(int)
    A_oriented = A_prim @ T
    B_prim = 2 * np.pi * np.linalg.inv(A_prim.T)
    B_oriented = 2 * np.pi * np.linalg.inv(A_oriented.T)

    m_oriented = T.T @ m
    g_prim = B_prim @ m
    g_oriented = B_oriented @ m_oriented

    # They must be parallel (cross ~ 0)
    assert np.linalg.norm(np.cross(g_prim, g_oriented)) < 1e-8

    # If naive g = B_oriented @ m were used it would generally not be parallel
    g_wrong = B_oriented @ m
    assert np.linalg.norm(np.cross(g_prim, g_wrong)) > 1e-8


def test_stacking_vector_determinant_semantics():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()

    u, v, w, m = compute_primitive_surface_basis(1, 1, 1, A_conv, A_prim)
    T = np.column_stack([u, v, w]).astype(int)
    det_T = int(round(np.linalg.det(T)))

    # The oriented Bezout basis must lie in SL(3,Z).
    assert det_T == 1


def test_minimize_shear_rotation_invariance():
    """Shear minimization should be invariant under global rotations of A_prim."""
    from calm.slab.oriented._primitive import minimize_shear

    rng = np.random.default_rng(0)

    # Build a random but well-conditioned A_prim
    A_prim = np.eye(3)

    # Choose simple integer u, v, w
    u = np.array([1, 0, 0], dtype=int)
    v = np.array([0, 1, 0], dtype=int)
    w = np.array([1, 1, 1], dtype=int)

    # Random orthogonal rotation matrix Q
    X = rng.normal(size=(3, 3))
    Q, _ = np.linalg.qr(X)
    if np.linalg.det(Q) < 0:
        Q[:, 0] = -Q[:, 0]

    A_rot = Q @ A_prim

    w_min = minimize_shear(w.copy(), u, v, A_prim)
    w_min_rot = minimize_shear(w.copy(), u, v, A_rot)

    assert np.array_equal(w_min, w_min_rot)


def test_ase_row_column_supercell_convention():
    """ASE adapter should produce row-major cell equal to (A_col @ T).T."""
    from ase import Atoms

    from calm.structure.ase_adapter import make_supercell_col

    atoms = Atoms("H", positions=[[0, 0, 0]], cell=np.eye(3), pbc=True)
    A_col = atoms.cell.array.T
    T = np.array([[1, 1, 0], [0, 1, 0], [0, 0, 2]], dtype=int)
    sc = make_supercell_col(atoms, T)
    expected_row = (A_col @ T).T
    assert np.allclose(sc.cell.array, expected_row)
    assert len(sc) == int(round(abs(np.linalg.det(T)))) * len(atoms)


def test_validate_surface_basis_exact_cross_and_triple_product():
    A_prim = simple_cubic_cell(1.0)
    A_conv = A_prim.copy()
    u, v, w, m = compute_primitive_surface_basis(1, 1, 1, A_conv, A_prim)
    ok, info = validate_surface_basis(A_prim, m, u, v, w, layers=2)
    assert ok, info
    cross_uv = np.cross(u, v)
    assert np.array_equal(cross_uv, m)
    det_signed = int(np.dot(np.cross(u, v), 2 * w))
    expected_signed = int(2 * np.dot(m, w))
    assert det_signed == expected_signed == 2
