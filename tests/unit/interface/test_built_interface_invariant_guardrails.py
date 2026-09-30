"""Dependency-light guardrails for built-interface geometry invariants."""

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
        # The build-kernel invariants checked here do not require periodic wrapping.
        return None

    def __iadd__(self, other):
        self.positions = np.vstack([self.positions, other.positions])
        return self


def _install_fake_ase_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_ase_adapter = types.ModuleType("calm.structure.ase_adapter")

    def make_supercell_col(atoms, matrix):
        matrix = np.asarray(matrix, dtype=int)
        if not np.array_equal(matrix, np.eye(3, dtype=int)):
            raise AssertionError("this dependency-light fixture only supports identity supercells")
        return atoms.copy()

    fake_ase_adapter.make_supercell_col = make_supercell_col
    monkeypatch.setitem(sys.modules, "calm.structure.ase_adapter", fake_ase_adapter)


def test_built_interface_geometry_invariants_without_ase(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_ase_adapter(monkeypatch)

    lower = _AtomsLike(
        positions=[[0.1, 0.0, -0.5], [0.4, 0.2, 0.5]],
        cell=[[2.0, 0.0, 0.0], [0.25, 1.5, 0.0], [0.0, 0.0, 4.0]],
    )
    upper = _AtomsLike(
        positions=[[0.2, 0.3, -0.25], [0.6, 0.4, 0.75]],
        cell=[[2.0, 0.0, 0.0], [0.25, 1.5, 0.0], [0.0, 0.0, 4.0]],
    )
    lower_positions = lower.positions.copy()
    upper_positions = upper.positions.copy()

    N = np.eye(3, dtype=int)
    R = np.eye(3, dtype=float)
    F = np.eye(3, dtype=float)

    built = build_interface_atoms(
        slab_A_atoms=lower,
        slab_B_atoms=upper,
        N_A3=N,
        N_B3=N,
        R_A3=R,
        R_B3=R,
        F_A=F,
        F_B=F,
        translation_frac=(0.25, 0.5),
        z_padding=1.25,
        vacuum_padding=2.5,
    )

    atoms = built.atoms
    cell = np.asarray(atoms.cell.array, dtype=float)
    assert np.allclose(cell[0], built.c1)
    assert np.allclose(cell[1], built.c2)
    assert np.allclose(cell[2, :2], [0.0, 0.0])
    assert np.isclose(cell[2, 2], built.Lz)
    assert tuple(bool(x) for x in atoms.pbc) == (True, True, True)

    lower_indices = set(int(i) for i in built.lower_indices)
    upper_indices = set(int(i) for i in built.upper_indices)
    assert lower_indices.isdisjoint(upper_indices)
    assert lower_indices | upper_indices == set(range(len(atoms)))
    assert len(lower_indices) == len(lower)
    assert len(upper_indices) == len(upper)

    z = np.asarray(atoms.positions[:, 2], dtype=float)
    assert np.isclose(
        float(np.min(z[built.upper_indices])) - float(np.max(z[built.lower_indices])),
        1.25,
    )
    assert np.isclose(built.Lz - float(np.max(z[built.upper_indices])), 2.5)

    # Caller-owned slab objects are copied before transformation.
    assert np.allclose(lower.positions, lower_positions)
    assert np.allclose(upper.positions, upper_positions)


def test_built_interface_rejects_negative_vacuum_padding_without_ase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_ase_adapter(monkeypatch)

    atoms = _AtomsLike(
        positions=[[0.0, 0.0, 0.0]],
        cell=np.eye(3),
    )
    N = np.eye(3, dtype=int)
    R = np.eye(3, dtype=float)
    F = np.eye(3, dtype=float)

    with pytest.raises(ValueError, match="vacuum_padding must be non-negative"):
        build_interface_atoms(
            slab_A_atoms=atoms,
            slab_B_atoms=atoms,
            N_A3=N,
            N_B3=N,
            R_A3=R,
            R_B3=R,
            F_A=F,
            F_B=F,
            translation_frac=(0.0, 0.0),
            z_padding=1.0,
            vacuum_padding=-0.1,
        )
