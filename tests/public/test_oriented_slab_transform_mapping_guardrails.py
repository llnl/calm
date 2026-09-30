from __future__ import annotations

import numpy as np
import pytest

from calm.slab.oriented.builder import OrientedSlabTransforms
from oriented_slab_fixtures import current_construction_controls


def _proper_rotation_z(theta: float) -> np.ndarray:
    c = float(np.cos(theta))
    s = float(np.sin(theta))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _transforms(*, shear: np.ndarray | None = None) -> OrientedSlabTransforms:
    R = _proper_rotation_z(0.37)
    shear_info = None
    if shear is not None:
        shear_info = {
            "F_shear_cart": shear,
            "U_shear_lattice": np.eye(3, dtype=int),
        }
    return OrientedSlabTransforms(
        hkl_reduced=(1, 1, 0),
        layers=3,
        S_conv_to_surface_col=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 3]], dtype=int),
        U_inplane_col=np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=int),
        P_supercell_row=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 3]], dtype=int),
        R_conv_to_slab=R,
        R_slab_to_conv=R.T,
        R_align=np.eye(3),
        L_c_tilt_row=np.array([[1, 0, 0], [0, 1, 0], [1, -1, 1]], dtype=int),
        c_tilt_mn=(1, -1),
        shear_info=shear_info,
        vacuum_info={"vacuum_added": 12.0},
        construction_controls=current_construction_controls(),
    )


def test_cartesian_mapping_excludes_integer_and_vacuum_representation_steps() -> None:
    """Only Cartesian rotation/shear enter vector mappings, not lattice bookkeeping."""
    transforms = _transforms()

    assert transforms.F_orthogonalize_c_slab is None
    assert transforms.M_conv_to_slab_cart() == pytest.approx(transforms.R_conv_to_slab, abs=1.0e-12)
    assert transforms.M_slab_to_conv_cart() == pytest.approx(transforms.R_slab_to_conv, abs=1.0e-12)
    assert transforms.M_slab_to_conv_cart() @ transforms.M_conv_to_slab_cart() == pytest.approx(
        np.eye(3), abs=1.0e-12
    )


def test_cartesian_mapping_includes_physical_shear_and_remains_invertible() -> None:
    """Physical c-orthogonalization shear composes after rotation in slab coordinates."""
    F_shear = np.array([[1.0, 0.0, -0.25], [0.0, 1.0, 0.4], [0.0, 0.0, 1.0]])
    transforms = _transforms(shear=F_shear)

    expected_forward = F_shear @ transforms.R_conv_to_slab
    expected_inverse = transforms.R_slab_to_conv @ np.linalg.inv(F_shear)

    assert transforms.M_conv_to_slab_cart() == pytest.approx(expected_forward, abs=1.0e-12)
    assert transforms.M_slab_to_conv_cart() == pytest.approx(expected_inverse, abs=1.0e-12)
    assert transforms.M_slab_to_conv_cart() @ transforms.M_conv_to_slab_cart() == pytest.approx(
        np.eye(3), abs=1.0e-12
    )
    assert np.linalg.det(transforms.M_conv_to_slab_cart()) == pytest.approx(1.0, abs=1.0e-12)
