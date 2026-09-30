"""Behavioral tests for shared Cartesian transform helpers."""

from __future__ import annotations

import numpy as np

import calm.interface.building._geometry as _build_geometry


class _Cell:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=float)


class _AtomsLike:
    def __init__(self):
        self.positions = np.eye(3, dtype=float)
        self.cell = _Cell(np.eye(3, dtype=float))
        self.set_cell_calls: list[tuple[np.ndarray, bool]] = []

    def set_cell(self, cell, *, scale_atoms=True):
        self.set_cell_calls.append((np.asarray(cell, dtype=float), bool(scale_atoms)))
        self.cell = _Cell(cell)


def test_shared_deformation_helper_preserves_no_scale_cell_update() -> None:
    atoms = _AtomsLike()
    deformation = np.diag([2.0, 3.0, 4.0])

    _build_geometry._apply_deformation_gradient(atoms, deformation)

    np.testing.assert_allclose(atoms.positions, np.eye(3) @ deformation.T)
    assert len(atoms.set_cell_calls) == 1
    cell, scale_atoms = atoms.set_cell_calls[0]
    np.testing.assert_allclose(cell, deformation.T)
    assert scale_atoms is False


def test_shared_rotation_helper_preserves_no_scale_cell_update() -> None:
    atoms = _AtomsLike()
    rotation = np.array(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )

    _build_geometry._rotate_atoms_cartesian(atoms, rotation)

    np.testing.assert_allclose(atoms.positions, np.eye(3) @ rotation.T)
    assert len(atoms.set_cell_calls) == 1
    cell, scale_atoms = atoms.set_cell_calls[0]
    np.testing.assert_allclose(cell, rotation.T)
    assert scale_atoms is False
