"""Cartesian geometry helpers used by the internal build kernel.

These helpers are pure numeric / ASE-adapter helpers extracted from
calm.interface.building._kernel so they can be tested and reasoned about
in isolation.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _set_atoms_cell_no_scale(atoms: Any, cell: np.ndarray) -> None:
    """Set an atoms-like cell without scaling positions when supported."""

    if hasattr(atoms, "set_cell"):
        atoms.set_cell(cell, scale_atoms=False)
    else:
        atoms.cell = cell


def _cell_array(atoms: Any) -> np.ndarray:
    """Return an atoms-like cell as a numeric 3x3 array."""

    cell = atoms.cell
    if hasattr(cell, "array"):
        cell = cell.array
    return np.asarray(cell, dtype=float)


def _apply_deformation_gradient(atoms: Any, deformation_gradient: np.ndarray) -> None:
    """Apply a Cartesian deformation gradient in-place."""

    Fm = np.asarray(deformation_gradient, dtype=float)
    if Fm.shape != (3, 3):
        raise ValueError(
            f"Expected 3x3 deformation-gradient matrix; got shape {Fm.shape}"
        )

    atoms.positions = np.asarray(atoms.positions, dtype=float) @ Fm.T
    _set_atoms_cell_no_scale(atoms, _cell_array(atoms) @ Fm.T)


def _rotate_atoms_cartesian(atoms: Any, R: np.ndarray) -> None:
    """Rotate atoms (positions + cell) in Cartesian coordinates, in-place."""

    Rm = np.asarray(R, dtype=float)
    if Rm.shape != (3, 3):
        raise ValueError(f"Expected 3x3 rotation matrix; got shape {Rm.shape}")

    atoms.positions = np.asarray(atoms.positions, dtype=float) @ Rm.T
    _set_atoms_cell_no_scale(atoms, _cell_array(atoms) @ Rm.T)


def _zmin_zmax(atoms: Any) -> tuple[float, float]:
    pos = np.asarray(atoms.positions, dtype=float)
    if pos.size == 0:
        return 0.0, 0.0
    z = pos[:, 2]
    return float(np.min(z)), float(np.max(z))
