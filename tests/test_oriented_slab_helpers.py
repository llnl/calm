import numpy as np
from ase import Atoms

from calm.slab.oriented.builder import (
    _apply_canonical_sign_fix,
    _orient_block_to_slab_frame,
    _finalize_wrap_and_clamp,
    _construct_transforms,
    OrientedSlabTransforms,
)
from oriented_slab_fixtures import current_construction_controls


def test_apply_canonical_sign_fix_flips_negative_axes():
    # Create an atoms cell with negative a_x and negative b_y to force flips
    cell = np.array([[-4.0, 0.0, 0.0], [0.0, -4.0, 0.0], [0.0, 0.0, 4.0]])
    atoms = Atoms(symbols=["Al"], positions=[[0.0, 0.0, 0.0]], cell=cell, pbc=True)

    # scaled positions before
    s_before = atoms.get_scaled_positions().copy()

    prov = _apply_canonical_sign_fix(atoms)
    # Should have returned a provenance dict
    assert prov is not None and isinstance(prov, dict)
    assert "L_diag" in prov
    L_diag = prov["L_diag"]
    assert isinstance(L_diag, list) and len(L_diag) == 3

    # After fix, cell diagonal entries should be non-negative
    C = np.asarray(atoms.cell.array)
    assert C[0, 0] >= 0
    assert C[1, 1] >= 0
    assert C[2, 2] >= 0

    # Scaled positions should have been transformed (best-effort check)
    s_after = atoms.get_scaled_positions()
    # scaled positions may flip sign but still be numerically equal (e.g. -0 -> 0),
    # so test that the provenance indicates an actual transformation matrix
    assert prov["L_diag"] != [1, 1, 1]


def test_orient_block_to_slab_frame_aligns_normal():
    # Build a simple pre_oriented block whose a and b are not in xy-plane
    a = np.array([1.0, 0.1, 0.2])
    b = np.array([0.0, 1.0, -0.1])
    c = np.array([0.0, 0.0, 3.0])
    cell = np.vstack([a, b, c])
    atoms = Atoms(symbols=["Al", "Al"], positions=[[0, 0, 0], [0.5, 0.5, 0.5]], cell=cell, pbc=True)

    oriented, R = _orient_block_to_slab_frame(atoms, normal_sign=+1, ortho_tol=1e-8)
    # After orientation, a_z and b_z should be near zero
    a2, b2, _ = oriented.cell.array
    assert abs(float(a2[2])) < 1e-8
    assert abs(float(b2[2])) < 1e-8

    # R should be orthogonal and det ~ +1
    assert np.allclose(R.T @ R, np.eye(3), atol=1e-8)
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-8)


def test_finalize_wrap_and_clamp_clamps_fractional():
    atoms = Atoms(symbols=["Li", "Li"], positions=[[0.0, 0.0, 0.0], [1.0000000001, 0.0, 0.0]], cell=np.diag([3.0, 3.0, 3.0]), pbc=True)
    # Force slightly out-of-bound scaled positions
    # ASE Atoms expects fractional positions in absolute coordinates; assign via positions
    frac = np.array([[ -1e-12, 0.0, 0.0 ], [1.0 + 1e-12, 0.0, 0.0]])
    atoms.set_positions(frac @ atoms.get_cell())

    block, slab = _finalize_wrap_and_clamp(atoms, atoms, wrap=True)
    frac = block.get_scaled_positions(wrap=False)
    assert np.all(frac >= 0.0 - 1e-12)
    assert np.all(frac < 1.0)


def test_construct_transforms_includes_canonical_fix():
    # Minimal identity inputs
    hkl_red = (1, 0, 0)
    layers = 2
    S_layers = np.eye(3)
    U_inplane = np.eye(3)
    P_row_used = np.eye(3)
    R_conv_to_slab_total = np.eye(3)
    R_align = np.eye(3)
    L_c_tilt_row = None
    mn = None
    shear_info = None
    vacuum_info = None
    canonical_fix = {"L_diag": [1, -1, 1]}

    transforms = _construct_transforms(
        hkl_red=hkl_red,
        layers=layers,
        S_layers=S_layers,
        U_inplane=U_inplane,
        P_row_used=P_row_used,
        R_conv_to_slab_total=R_conv_to_slab_total,
        R_align=R_align,
        L_c_tilt_row=L_c_tilt_row,
        mn=mn,
        shear_info=shear_info,
        vacuum_info=vacuum_info,
        canonical_fix=canonical_fix,
        construction_controls=current_construction_controls(),
    )
    assert isinstance(transforms, OrientedSlabTransforms)
    assert transforms.canonical_sign_fix == canonical_fix
