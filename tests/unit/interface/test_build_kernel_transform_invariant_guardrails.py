"""Dependency-light guardrails for build-kernel transform invariants."""

from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from calm.interface.building._kernel import build_interface_atoms


class _Cell:
    def __init__(self, array):
        self.array = np.asarray(array, dtype=float)


class _AtomsLike:
    def __init__(self, positions, cell):
        self.positions = np.asarray(positions, dtype=float)
        self.cell = _Cell(cell)
        self.pbc = (False, False, False)

    def copy(self):
        copied = _AtomsLike(self.positions.copy(), self.cell.array.copy())
        copied.pbc = tuple(self.pbc)
        return copied

    def __len__(self):
        return int(self.positions.shape[0])

    def set_cell(self, cell, scale_atoms=False):
        assert scale_atoms is False
        self.cell = _Cell(cell)

    def translate(self, vector):
        self.positions = self.positions + np.asarray(vector, dtype=float)

    def wrap(self):
        return None

    def __iadd__(self, other):
        self.positions = np.vstack([self.positions, other.positions])
        return self


def _install_fake_ase_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ase_adapter = types.ModuleType("calm.structure.ase_adapter")

    def make_supercell_col(atoms, matrix):
        matrix = np.asarray(matrix, dtype=int)
        if not np.array_equal(matrix, np.eye(3, dtype=int)):
            raise AssertionError(
                "this dependency-light fixture only supports identity supercells"
            )
        return atoms.copy()

    fake_ase_adapter.make_supercell_col = make_supercell_col
    monkeypatch.setitem(sys.modules, "calm.structure.ase_adapter", fake_ase_adapter)


def test_build_kernel_translation_uses_post_strain_in_plane_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)

    lower = _AtomsLike(
        positions=[[0.0, 0.0, 0.0]],
        cell=[[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 5.0]],
    )
    upper = _AtomsLike(
        positions=[[0.0, 0.0, 0.0]],
        cell=[[2.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 5.0]],
    )

    N = np.eye(3, dtype=int)
    R = np.eye(3, dtype=float)
    F_A = np.diag([2.0, 1.0, 1.0])
    F_B = np.diag([2.0, 1.0, 1.0])

    built = build_interface_atoms(
        slab_A_atoms=lower,
        slab_B_atoms=upper,
        N_A3=N,
        N_B3=N,
        R_A3=R,
        R_B3=R,
        F_A=F_A,
        F_B=F_B,
        translation_frac=(0.25, 1.0 / 3.0),
        z_padding=1.0,
        vacuum_padding=0.0,
    )

    assert np.allclose(built.c1, [4.0, 0.0, 0.0])
    assert np.allclose(built.c2, [0.0, 3.0, 0.0])
    upper_position = np.asarray(
        built.atoms.positions[built.upper_indices[0]],
        dtype=float,
    )
    assert np.allclose(upper_position[:2], [1.0, 1.0])


def test_build_kernel_rejects_non_3x3_transform_matrices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)

    atoms = _AtomsLike(positions=[[0.0, 0.0, 0.0]], cell=np.eye(3))
    N = np.eye(3, dtype=int)
    R = np.eye(3, dtype=float)
    F = np.eye(3, dtype=float)

    with pytest.raises(ValueError, match="Expected 3x3 R matrices"):
        build_interface_atoms(
            slab_A_atoms=atoms,
            slab_B_atoms=atoms,
            N_A3=N,
            N_B3=N,
            R_A3=np.eye(2),
            R_B3=R,
            F_A=F,
            F_B=F,
            translation_frac=(0.0, 0.0),
            z_padding=0.0,
        )

    with pytest.raises(ValueError, match="Expected 3x3 deformation-gradient matrices"):
        build_interface_atoms(
            slab_A_atoms=atoms,
            slab_B_atoms=atoms,
            N_A3=N,
            N_B3=N,
            R_A3=R,
            R_B3=R,
            F_A=np.eye(2),
            F_B=F,
            translation_frac=(0.0, 0.0),
            z_padding=0.0,
        )
