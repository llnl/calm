"""Dependency-light invariants for oriented slab construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from calm.slab.oriented._lattice import (
    _c_orthogonalization_from_cell,
    _c_tilt_reduction_matrix,
    _compute_R_from_ab_to_xy,
    _compute_R_from_normal_and_inplane,
    _reduce_hkl,
)
from calm.slab.oriented.builder import (
    OrientedSlabTransforms,
    _add_vacuum_along_cartesian_z,
    _apply_canonical_sign_fix,
    _normalized_inplane_reduction_frame,
    _orthogonalize_c_by_shear,
    _proper_inplane_reduction_pair,
    _reduce_inplane_by_metric,
)
from oriented_slab_fixtures import current_construction_controls


@dataclass
class _Cell:
    array: np.ndarray


class _Atoms:
    """Small ASE-like object sufficient for dependency-light helper tests."""

    def __init__(self, cell: np.ndarray, positions: np.ndarray) -> None:
        self.cell = _Cell(np.asarray(cell, dtype=float).copy())
        self.positions = np.asarray(positions, dtype=float).copy()

    def __len__(self) -> int:
        return int(self.positions.shape[0])

    def copy(self) -> "_Atoms":
        return _Atoms(self.cell.array, self.positions)

    def get_cell(self) -> np.ndarray:
        return self.cell.array.copy()

    def set_cell(self, cell: np.ndarray, *, scale_atoms: bool) -> None:
        fractional = self.get_scaled_positions(wrap=False)
        self.cell.array = np.asarray(cell, dtype=float).copy()
        if scale_atoms:
            self.set_scaled_positions(fractional)

    def get_positions(self) -> np.ndarray:
        return self.positions.copy()

    def set_positions(self, positions: np.ndarray) -> None:
        self.positions = np.asarray(positions, dtype=float).copy()

    def get_scaled_positions(self, *, wrap: bool) -> np.ndarray:
        fractional = self.positions @ np.linalg.inv(self.cell.array)
        if wrap:
            fractional %= 1.0
        return fractional

    def set_scaled_positions(self, fractional: np.ndarray) -> None:
        self.positions = np.asarray(fractional, dtype=float) @ self.cell.array

    def wrap(self, *, eps: float) -> None:
        del eps
        self.set_scaled_positions(self.get_scaled_positions(wrap=True))


def _transform_bundle(*, deformation: np.ndarray | None) -> OrientedSlabTransforms:
    shear_info = None
    if deformation is not None:
        shear_info = {
            "U_shear_lattice": np.eye(3),
            "F_shear_cart": deformation,
        }
    return OrientedSlabTransforms(
        hkl_reduced=(1, 1, 0),
        layers=3,
        S_conv_to_surface_col=np.eye(3),
        U_inplane_col=None,
        P_supercell_row=np.diag([1, 1, 3]),
        R_conv_to_slab=np.eye(3),
        R_slab_to_conv=np.eye(3),
        R_align=None,
        L_c_tilt_row=None,
        c_tilt_mn=None,
        shear_info=shear_info,
        vacuum_info={"vacuum_per_side": 8.0},
        construction_controls=current_construction_controls(),
        canonical_sign_fix={"L_diag": [[-1, 0, 0], [0, -1, 0], [0, 0, 1]]},
        supercell_reference="primitive",
        miller_primitive=(2, 2, 0),
    )


def test_exact_inputs_reject_nonintegral_miller_indices() -> None:
    assert _reduce_hkl((2, -4, 6)) == (1, -2, 3)
    with pytest.raises(ValueError, match="integers"):
        _reduce_hkl((1.5, 0, 1))  # type: ignore[arg-type]


def test_rotation_construction_is_scale_equivariant_and_proper() -> None:
    vector_a = np.array([2.0, 0.5, -0.25])
    vector_b = np.array([-0.3, 1.7, 0.8])
    reference = _compute_R_from_ab_to_xy(vector_a, vector_b)

    for scale in (1e-150, 1.0, 1e150):
        rotation = _compute_R_from_ab_to_xy(
            scale * vector_a,
            scale * vector_b,
        )
        assert np.allclose(rotation, reference, atol=2e-14, rtol=0.0)
        assert np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-14)
        assert np.isclose(np.linalg.det(rotation), 1.0, atol=2e-14)
        mapped_a = rotation @ vector_a
        mapped_b = rotation @ vector_b
        assert abs(mapped_a[2]) < 2e-14
        assert abs(mapped_b[2]) < 2e-14
        assert mapped_a[0] > 0.0


def test_normal_sign_selects_opposite_slab_normal() -> None:
    normal = np.array([1.0, -2.0, 3.0])
    inplane = np.array([2.0, 1.0, 0.0])
    inplane -= np.dot(inplane, normal) * normal / np.dot(normal, normal)

    positive = _compute_R_from_normal_and_inplane(normal, inplane)
    negative = _compute_R_from_normal_and_inplane(
        normal,
        inplane,
        normal_sign=-1,
    )
    normal_hat = normal / np.linalg.norm(normal)
    assert np.allclose(positive @ normal_hat, [0.0, 0.0, 1.0])
    assert np.allclose(negative @ normal_hat, [0.0, 0.0, -1.0])
    assert np.isclose(np.linalg.det(positive), 1.0)
    assert np.isclose(np.linalg.det(negative), 1.0)


def test_inplane_reduction_pair_repairs_paired_reflections() -> None:
    transform = np.array([[1, 0], [-1, -1]], dtype=int)
    rotation = np.array(
        [
            [8.0 / 17.0, -15.0 / 17.0],
            [-15.0 / 17.0, -8.0 / 17.0],
        ]
    )
    repaired_transform, repaired_rotation = _proper_inplane_reduction_pair(
        transform,
        rotation,
        tolerance=1e-12,
    )

    assert round(np.linalg.det(transform)) == -1
    assert np.isclose(np.linalg.det(rotation), -1.0)
    assert round(np.linalg.det(repaired_transform)) == 1
    assert np.isclose(np.linalg.det(repaired_rotation), 1.0)
    assert np.allclose(
        repaired_rotation.T @ repaired_rotation,
        np.eye(2),
        atol=1e-12,
    )

    basis = np.array([[2.0, 1.2], [0.0, 1.5]])
    original_reduced = rotation @ basis @ transform
    repaired_reduced = repaired_rotation @ basis @ repaired_transform
    assert np.allclose(repaired_reduced[:, 0], original_reduced[:, 0])
    assert np.allclose(
        repaired_reduced[:, 1],
        np.array([-original_reduced[0, 1], original_reduced[1, 1]]),
    )
    assert np.allclose(
        repaired_reduced.T @ repaired_reduced,
        np.diag([-1, 1])
        @ (original_reduced.T @ original_reduced)
        @ np.diag([-1, 1]),
    )


def test_inplane_reduction_frame_is_scale_invariant_before_norms() -> None:
    vector_a = np.array([2.0, 0.0, 0.0])
    vector_b = np.array([1.2, 1.5, 0.0])
    reference = _normalized_inplane_reduction_frame(vector_a, vector_b)

    for scale in (1e-150, 1.0, 1e150):
        scaled = _normalized_inplane_reduction_frame(
            scale * vector_a,
            scale * vector_b,
        )
        for actual, expected in zip(scaled, reference, strict=True):
            assert np.allclose(actual, expected, atol=2e-14, rtol=0.0)


def test_inplane_metric_reduction_has_explicit_basis_and_rotation_roles() -> None:
    pytest.importorskip("spglib")
    cell = np.array(
        [
            [2.0, 0.0, 0.0],
            [1.2, 1.5, 0.0],
            [0.4, -0.3, 4.0],
        ]
    )
    fractional = np.array([[0.1, 0.2, 0.3], [0.7, 0.4, 0.8]])
    atoms = _Atoms(cell, fractional @ cell)

    reduced, transform, rotation = _reduce_inplane_by_metric(atoms)
    expected_cell = transform.T @ cell @ rotation.T

    assert round(np.linalg.det(transform)) == 1
    assert np.allclose(reduced.cell.array, expected_cell, atol=2e-12)
    assert np.allclose(rotation.T @ rotation, np.eye(3), atol=2e-12)
    assert np.isclose(np.linalg.det(rotation), 1.0, atol=2e-12)
    assert np.allclose(reduced.cell.array[:2, 2], 0.0, atol=2e-12)
    assert reduced.cell.array[0, 0] > 0.0

    for scale in (1e-150, 1e150):
        scaled = _Atoms(scale * cell, fractional @ (scale * cell))
        _, scaled_transform, scaled_rotation = _reduce_inplane_by_metric(scaled)
        assert np.array_equal(scaled_transform, transform)
        assert np.allclose(scaled_rotation, rotation, atol=2e-12)


def test_vacuum_boundary_removes_c_tilt_without_shearing_atoms() -> None:
    cell = np.array(
        [
            [3.0, 0.0, 0.0],
            [-1.5, 2.598076211353316, 0.0],
            [-1.5, 0.866025403784439, 8.0],
        ]
    )
    positions = np.array(
        [
            [0.3, 0.4, 1.0],
            [1.2, 1.0, 4.0],
        ]
    )
    atoms = _Atoms(cell, positions)

    slab, provenance = _add_vacuum_along_cartesian_z(
        atoms,
        5.0,
        center=False,
        unwrap_first=False,
    )

    assert np.allclose(slab.cell.array[:2], cell[:2])
    assert np.allclose(slab.cell.array[2, :2], 0.0, atol=0.0, rtol=0.0)
    assert slab.cell.array[2, 2] == pytest.approx(13.0)
    assert np.allclose(slab.positions, positions, atol=2e-14, rtol=0.0)
    assert provenance["c_inplane_before"] == pytest.approx(cell[2, :2])
    assert provenance["c_inplane_after"] == pytest.approx([0.0, 0.0])
    assert provenance["c_xy_norm_before"] == pytest.approx(
        np.linalg.norm(cell[2, :2])
    )
    assert provenance["c_xy_norm_after"] == pytest.approx(0.0)
    assert provenance["orthogonal_vacuum_axis"] is True
    assert provenance["cell_policy"] == "interface_ready_slab_cell"
    assert provenance["cell_policy_version"] == 1
    assert provenance["canonicalization_mode"] == "boundary_reembedding"
    assert provenance["canonicalization_applies_physical_strain"] is False
    assert provenance["interface_ready"] is True


def test_vacuum_cell_policy_cannot_be_weakened_by_algorithmic_z_tolerance() -> None:
    cell = np.array(
        [
            [3.0, 0.0, 1.0e-3],
            [0.0, 3.0, 0.0],
            [0.0, 0.0, 8.0],
        ]
    )
    atoms = _Atoms(cell, np.array([[0.2, 0.3, 1.0]]))

    with pytest.raises(ValueError, match="a vector must lie in the global xy plane"):
        _add_vacuum_along_cartesian_z(
            atoms,
            5.0,
            center=False,
            unwrap_first=False,
            # This tolerance controls construction numerics only. It must not
            # relax the fixed interface-ready cell policy.
            z_tol=0.1,
        )


def test_physical_shear_and_vacuum_boundary_canonicalization_remain_distinct() -> None:
    cell = np.array(
        [
            [3.0, 0.0, 0.0],
            [0.7, 2.4, 0.0],
            [0.8, -0.6, 8.0],
        ]
    )
    fractional = np.array([[0.1, 0.2, 0.3], [0.7, 0.4, 0.8]])
    atoms = _Atoms(cell, fractional @ cell)

    sheared, shear_info = _orthogonalize_c_by_shear(atoms)
    slab, vacuum_info = _add_vacuum_along_cartesian_z(
        sheared,
        5.0,
        center=False,
        unwrap_first=False,
    )

    assert np.linalg.norm(shear_info["F_shear_cart"] - np.eye(3)) > 0.0
    assert np.allclose(sheared.cell.array[2, :2], 0.0, atol=2e-14)
    assert np.allclose(slab.cell.array[2, :2], 0.0, atol=0.0, rtol=0.0)
    assert vacuum_info["canonicalization_mode"] == "already_orthogonal"
    assert vacuum_info["canonicalization_applies_physical_strain"] is False


def test_bounded_c_tilt_gauge_is_scale_invariant_and_locally_optimal() -> None:
    cell = np.array(
        [
            [2.0, 0.0, 0.0],
            [0.4, 1.7, 0.0],
            [3.3, -2.4, 5.0],
        ]
    )
    pair, row_transform = _c_tilt_reduction_matrix(cell, search=3)
    transformed = row_transform @ cell
    selected_objective = float(np.dot(transformed[2, :2], transformed[2, :2]))

    a_xy = cell[0, :2]
    b_xy = cell[1, :2]
    c_xy = cell[2, :2]
    coefficients = np.linalg.solve(np.column_stack([a_xy, b_xy]), c_xy)
    center_m, center_n = np.rint(-coefficients).astype(int)
    alternatives = []
    for m in range(center_m - 3, center_m + 4):
        for n in range(center_n - 3, center_n + 4):
            residual = c_xy + m * a_xy + n * b_xy
            alternatives.append(float(np.dot(residual, residual)))
    assert selected_objective <= min(alternatives) + 1e-12

    for scale in (1e-150, 1e150):
        scaled_pair, scaled_transform = _c_tilt_reduction_matrix(
            scale * cell,
            search=3,
        )
        assert scaled_pair == pair
        assert np.array_equal(scaled_transform, row_transform)


def test_c_orthogonalization_is_volume_preserving_physical_shear() -> None:
    cell = np.array(
        [
            [2.0, 0.0, 0.0],
            [0.4, 1.7, 0.0],
            [0.8, -0.6, 5.0],
        ]
    )
    cell_new, lattice_shear, deformation, alpha, beta = (
        _c_orthogonalization_from_cell(cell)
    )

    assert np.allclose(cell_new[:2], cell[:2])
    assert np.allclose(cell_new[2, :2], 0.0, atol=2e-14)
    assert np.allclose(cell_new, lattice_shear.T @ cell)
    assert np.allclose(cell_new.T, deformation @ cell.T)
    assert np.isclose(np.linalg.det(lattice_shear), 1.0)
    assert np.isclose(np.linalg.det(deformation), 1.0)
    assert np.isfinite(alpha)
    assert np.isfinite(beta)

    for scale in (1e-150, 1e150):
        scaled_new, scaled_lattice, scaled_deformation, _, _ = (
            _c_orthogonalization_from_cell(scale * cell)
        )
        assert np.allclose(scaled_lattice, lattice_shear, atol=2e-14)
        assert np.allclose(scaled_deformation, deformation, atol=2e-14)
        assert np.allclose(scaled_new / scale, cell_new, atol=2e-12)


def test_transform_direction_aliases_and_round_trip_are_consistent() -> None:
    deformation = np.array(
        [
            [1.0, 0.0, -0.2],
            [0.0, 1.0, 0.1],
            [0.0, 0.0, 1.0],
        ]
    )
    transforms = _transform_bundle(deformation=deformation)

    assert np.allclose(transforms.F_ideal_to_slab, deformation)
    assert np.allclose(
        transforms.F_slab_to_ideal,
        np.linalg.inv(deformation),
    )
    assert transforms.supercell_reference == "primitive"
    assert transforms.miller_primitive == (1, 1, 0)
    assert np.allclose(transforms.U_inplane_col, np.eye(3))
    assert np.allclose(transforms.R_align, np.eye(3))

    restored = OrientedSlabTransforms.from_json(transforms.to_json())
    assert restored.supercell_reference == "primitive"
    assert restored.miller_primitive == (1, 1, 0)
    assert restored.canonical_sign_fix == transforms.canonical_sign_fix
    assert np.allclose(restored.F_ideal_to_slab, deformation)


def test_canonical_sign_fix_rejects_left_handed_input() -> None:
    cell = np.diag([2.0, -3.0, 4.0])
    atoms = _Atoms(cell, np.array([[0.1, 0.2, 0.3]]) @ cell)

    with pytest.raises(ValueError, match="right-handed"):
        _apply_canonical_sign_fix(atoms)


def test_canonical_sign_fix_is_an_orientation_preserving_basis_gauge() -> None:
    cell = np.diag([-2.0, 3.0, -4.0])
    fractional = np.array([[0.1, 0.2, 0.3], [0.7, 0.4, 0.8]])
    atoms = _Atoms(cell, fractional @ cell)
    positions_before = atoms.positions.copy()

    payload = _apply_canonical_sign_fix(atoms)

    assert payload is not None
    diagonal = np.asarray(payload["L_diag"], dtype=int)
    assert round(np.linalg.det(diagonal)) == 1
    assert np.array_equal(atoms.cell.array, diagonal @ cell)
    displacement_fractional = (
        (atoms.positions - positions_before) @ np.linalg.inv(atoms.cell.array)
    )
    assert np.allclose(
        displacement_fractional,
        np.rint(displacement_fractional),
        atol=2e-14,
    )
