"""Validated spglib operations used by current CALM workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import spglib
from ase import Atoms

from calm.structure.standardization import (
    DEFAULT_SPGLIB_ANGLE_TOLERANCE,
    exact_bool,
    exact_integer_matrix3,
    exact_type_numbers,
    finite_cell_rows,
    finite_fractional_positions,
    nonnegative_finite_float,
    positive_finite_float,
    spglib_angle_tolerance,
    validate_crystal_arrays,
    wrap_fractional_positions,
)
from calm.symmetry.surface_group import (
    surface_metric_from_cell_rows,
    validate_surface_symmetry_group_2d,
)


@dataclass(frozen=True)
class StandardizedCellData:
    """Conventional and primitive cells plus the defining spglib dataset."""

    conventional: Atoms
    primitive: Atoms
    dataset: Any
    symprec: float
    angle_tolerance: float
    no_idealize: bool
    spglib_version: str


def _ase_to_spglib_cell(atoms: Atoms) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Return CALM's validated nonmagnetic three-dimensional spglib cell."""

    if not isinstance(atoms, Atoms):
        raise TypeError("atoms must be an ASE Atoms object.")

    lattice, positions, numbers, _pbc = validate_crystal_arrays(
        lattice=atoms.cell.array,
        scaled_positions=atoms.get_scaled_positions(wrap=False),
        numbers=atoms.get_atomic_numbers(),
        pbc=atoms.get_pbc(),
        require_3d_pbc=True,
        require_positive_numbers=True,
    )
    return lattice, wrap_fractional_positions(positions), numbers.tolist()


def _spglib_cell_to_ase_atoms(spglib_cell: object) -> Atoms:
    """Convert one standardized three-field spglib cell to ASE atoms."""

    if not isinstance(spglib_cell, (tuple, list)) or len(spglib_cell) != 3:
        raise ValueError("spglib_cell must be a tuple or list of length 3.")

    lattice = finite_cell_rows(spglib_cell[0])
    positions = finite_fractional_positions(spglib_cell[1])
    numbers = exact_type_numbers(
        spglib_cell[2],
        n_atoms=positions.shape[0],
        require_positive=True,
    )
    return Atoms(
        numbers=numbers,
        cell=lattice,
        scaled_positions=wrap_fractional_positions(positions),
        pbc=True,
    )


def _validated_symprec(symprec: object) -> float:
    return positive_finite_float("symprec", symprec)


def _fixed_angle_tolerance() -> float:
    return spglib_angle_tolerance(DEFAULT_SPGLIB_ANGLE_TOLERANCE)


def get_spacegroup(atoms: Atoms, *, symprec: float = 1e-5) -> str:
    """Return spglib's setting-dependent human-readable space-group label."""

    tolerance = _validated_symprec(symprec)
    result = spglib.get_spacegroup(
        _ase_to_spglib_cell(atoms),
        symprec=tolerance,
        angle_tolerance=_fixed_angle_tolerance(),
    )
    if result is None:
        raise ValueError("spglib could not determine a space group.")
    return str(result)


def _pointgroup_rotations(
    atoms: Atoms,
    *,
    symprec: float,
) -> list[np.ndarray]:
    """Return unique validated fractional point-group rotations."""

    tolerance = _validated_symprec(symprec)
    symmetry = spglib.get_symmetry(
        _ase_to_spglib_cell(atoms),
        symprec=tolerance,
        angle_tolerance=_fixed_angle_tolerance(),
    )
    if symmetry is None:
        raise ValueError("spglib could not determine symmetry operations.")

    rotations_raw = np.asarray(symmetry["rotations"], dtype=object)
    if rotations_raw.ndim != 3 or rotations_raw.shape[1:] != (3, 3):
        raise ValueError("spglib returned malformed rotation operations.")

    seen: set[tuple[int, ...]] = set()
    rotations: list[np.ndarray] = []
    for raw_rotation in rotations_raw:
        rotation = exact_integer_matrix3("symmetry rotation", raw_rotation)
        key = tuple(int(value) for value in rotation.ravel())
        if key in seen:
            continue
        seen.add(key)
        rotations.append(rotation)
    return rotations


def get_surface_pointgroup_ops(
    atoms: Atoms,
    *,
    symprec: float = 1e-5,
    angle_tol: float = 1e-8,
    metric_tol: float = 1e-5,
) -> list[np.ndarray]:
    """Return the validated 2D point group preserving Cartesian +z."""

    tolerance = nonnegative_finite_float("angle_tol", angle_tol)
    metric_tolerance = positive_finite_float("metric_tol", metric_tol)

    selected: list[np.ndarray] = []
    for rotation in _pointgroup_rotations(atoms, symprec=symprec):
        if not _preserves_cartesian_positive_z(
            atoms,
            rotation,
            angle_tol=tolerance,
        ):
            continue
        if not _preserves_fractional_ab_plane(rotation):
            continue
        selected.append(rotation[:2, :2].copy())

    metric = surface_metric_from_cell_rows(atoms.cell.array)
    return list(
        validate_surface_symmetry_group_2d(
            selected,
            metric=metric,
            metric_tolerance=metric_tolerance,
        )
    )


def _preserves_cartesian_positive_z(
    atoms: Atoms,
    rotation_fractional: np.ndarray,
    *,
    angle_tol: float,
) -> bool:
    zprime = _fractional_rotation_to_cartesian(atoms, rotation_fractional) @ np.array(
        [0.0, 0.0, 1.0]
    )
    norm = float(np.linalg.norm(zprime))
    if not np.isfinite(norm) or norm <= np.finfo(float).tiny:
        return False
    cosine = float(zprime[2] / norm)
    return 1.0 - cosine <= angle_tol


def _preserves_fractional_ab_plane(rotation: np.ndarray) -> bool:
    return bool(
        rotation[2, 0] == 0
        and rotation[2, 1] == 0
        and rotation[0, 2] == 0
        and rotation[1, 2] == 0
    )


def get_standardized_cell_data(
    atoms: Atoms,
    *,
    symprec: float = 1e-5,
    no_idealize: bool = False,
) -> StandardizedCellData:
    """Return standardized cells and the dataset defining their relation."""

    tolerance = _validated_symprec(symprec)
    preserve_metric = exact_bool("no_idealize", no_idealize)
    cell = _ase_to_spglib_cell(atoms)

    angle_tolerance = _fixed_angle_tolerance()
    dataset = spglib.get_symmetry_dataset(
        cell,
        symprec=tolerance,
        angle_tolerance=angle_tolerance,
    )
    if dataset is None:
        raise ValueError("spglib could not determine a symmetry dataset.")

    conventional_cell = spglib.standardize_cell(
        cell,
        to_primitive=False,
        no_idealize=preserve_metric,
        symprec=tolerance,
        angle_tolerance=angle_tolerance,
    )
    primitive_cell = spglib.standardize_cell(
        cell,
        to_primitive=True,
        no_idealize=preserve_metric,
        symprec=tolerance,
        angle_tolerance=angle_tolerance,
    )
    if conventional_cell is None or primitive_cell is None:
        raise ValueError(
            "spglib.standardize_cell returned None; the input may be "
            "pathological at the requested symprec."
        )

    return StandardizedCellData(
        conventional=_spglib_cell_to_ase_atoms(conventional_cell),
        primitive=_spglib_cell_to_ase_atoms(primitive_cell),
        dataset=dataset,
        symprec=tolerance,
        angle_tolerance=angle_tolerance,
        no_idealize=preserve_metric,
        spglib_version=str(getattr(spglib, "__version__", "unknown")),
    )


def _fractional_rotation_to_cartesian(
    atoms: Atoms,
    rotation_fractional: np.ndarray,
) -> np.ndarray:
    """Convert a fractional rotation to the ASE-compatible Cartesian map."""

    cell = finite_cell_rows(atoms.cell.array)
    rotation = np.asarray(rotation_fractional, dtype=float)
    if rotation.shape != (3, 3):
        raise ValueError("rotation_fractional must have shape (3, 3).")
    if not np.isfinite(rotation).all():
        raise ValueError("rotation_fractional must contain only finite values.")
    basis_columns = cell.T
    return basis_columns @ rotation @ np.linalg.inv(basis_columns)
