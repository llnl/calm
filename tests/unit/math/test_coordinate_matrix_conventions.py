"""Dependency-light mathematical guardrails for CALM representation conventions."""

from __future__ import annotations

import numpy as np

from calm.structure.ase_adapter import supercell_matrix_ase_from_col
from calm.interface.building._geometry import _apply_deformation_gradient


class _Cell:
    def __init__(self, array: np.ndarray) -> None:
        self.array = np.asarray(array, dtype=float)


class _AtomsLike:
    def __init__(self, positions: np.ndarray, cell: np.ndarray) -> None:
        self.positions = np.asarray(positions, dtype=float)
        self.cell = _Cell(cell)

    def set_cell(self, cell: np.ndarray, *, scale_atoms: bool) -> None:
        assert scale_atoms is False
        self.cell = _Cell(cell)


def test_fractional_cartesian_mapping_agrees_in_row_and_column_layouts() -> None:
    cell_col = np.array(
        [
            [2.0, 0.4, -0.2],
            [0.1, 3.0, 0.5],
            [0.0, 0.2, 4.0],
        ]
    )
    frac_col = np.array([0.25, -0.5, 0.75])

    cart_col = cell_col @ frac_col
    cell_row = cell_col.T
    cart_row = frac_col.reshape(1, 3) @ cell_row

    np.testing.assert_allclose(cell_row.T, cell_col)
    np.testing.assert_allclose(cart_row.reshape(3), cart_col)


def test_column_basis_change_preserves_cartesian_point_with_inverse_coordinates() -> None:
    cell_col = np.array(
        [
            [2.0, 0.3, 0.0],
            [0.0, 1.7, 0.2],
            [0.1, 0.0, 3.1],
        ]
    )
    basis_change = np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=int)
    frac_new = np.array([0.2, 0.3, 0.4])
    frac_old = basis_change @ frac_new

    cart_old = cell_col @ frac_old
    cart_new = (cell_col @ basis_change) @ frac_new

    np.testing.assert_allclose(cart_new, cart_old)


def test_column_supercell_and_ase_row_supercell_cells_are_transposes() -> None:
    cell_col = np.array(
        [
            [2.0, 0.2, 0.0],
            [0.0, 2.5, 0.1],
            [0.0, 0.0, 3.0],
        ]
    )
    supercell_col = np.array([[2, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=int)

    expected_col = cell_col @ supercell_col
    cell_row = cell_col.T
    supercell_row = supercell_matrix_ase_from_col(supercell_col)
    expected_row = supercell_row @ cell_row

    np.testing.assert_allclose(expected_row, expected_col.T)


def test_cartesian_map_agrees_for_column_vectors_and_row_arrays() -> None:
    deformation = np.array(
        [
            [1.1, 0.2, 0.0],
            [0.0, 0.9, -0.1],
            [0.0, 0.0, 1.05],
        ]
    )
    positions_row = np.array([[1.0, 2.0, 3.0], [-0.5, 0.25, 1.5]])
    cell_row = np.array(
        [[2.0, 0.0, 0.0], [0.2, 3.0, 0.0], [0.0, 0.1, 4.0]]
    )
    atoms = _AtomsLike(positions_row.copy(), cell_row.copy())

    _apply_deformation_gradient(atoms, deformation)

    expected_positions = np.vstack(
        [(deformation @ vector.reshape(3, 1)).reshape(3) for vector in positions_row]
    )
    expected_cell_col = deformation @ cell_row.T

    np.testing.assert_allclose(atoms.positions, expected_positions)
    np.testing.assert_allclose(atoms.cell.array, expected_cell_col.T)


def test_linear_operator_frame_mapping_round_trips_for_nonorthogonal_map() -> None:
    frame_map = np.array(
        [
            [1.0, 0.0, -0.25],
            [0.0, 1.0, 0.4],
            [0.0, 0.0, 1.0],
        ]
    )
    operator_conv = np.array(
        [
            [1.1, 0.2, 0.0],
            [0.05, 0.9, 0.1],
            [0.0, -0.1, 1.0],
        ]
    )

    operator_slab = frame_map @ operator_conv @ np.linalg.inv(frame_map)
    reconstructed = np.linalg.inv(frame_map) @ operator_slab @ frame_map

    np.testing.assert_allclose(reconstructed, operator_conv, atol=1.0e-12, rtol=0.0)
    assert not np.allclose(np.linalg.inv(frame_map), frame_map.T)
