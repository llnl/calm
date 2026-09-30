"""Standardized bulk structures backed by ASE and spglib."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ase import Atoms as ase_atoms_type
from ase.formula import Formula

from calm.structure.standardization import exact_bool, positive_finite_float
from calm.symmetry.spglib_adapter import (
    get_spacegroup,
    get_standardized_cell_data,
)

from .provenance import stamp_bulk_canonicalization_transforms


@dataclass(frozen=True)
class Bulk:
    """A standardized bulk structure.

    Parameters
    ----------
    atoms
        Input bulk structure.
    symprec
        spglib symmetry tolerance.
    no_idealize
        Passed through to spglib cell standardization.

    Attributes
    ----------
    conv
        Standardized conventional cell (ASE Atoms).
    prim
        Standardized primitive cell (ASE Atoms).
    spacegroup
        Space group string (as reported by spglib).
    formula
        Reduced chemical formula string.
    uid
        Optional stable identifier provided by the caller.
    label
        Optional human-readable label (e.g. "Al", "LiF").
    """

    conv: ase_atoms_type
    prim: ase_atoms_type
    spacegroup: str
    formula: str
    uid: str | None = None
    label: str | None = None
    symprec: float = 1e-5
    no_idealize: bool = False

    def __init__(
        self,
        atoms: ase_atoms_type,
        *,
        # Optional façade metadata.
        uid: str | None = None,
        label: str | None = None,
        symprec: float = 1e-5,
        no_idealize: bool = False,
    ):
        if not isinstance(atoms, ase_atoms_type):
            raise TypeError("Bulk: atoms must be an ASE Atoms object.")

        symprec_f = positive_finite_float("symprec", symprec)
        no_idealize_b = exact_bool("no_idealize", no_idealize)

        standardized = get_standardized_cell_data(
            atoms,
            symprec=symprec_f,
            no_idealize=no_idealize_b,
        )
        conv = standardized.conventional
        prim = standardized.primitive

        # Provenance: record the (column-basis) lattice transforms implied by
        # spglib standardization. We store this in `Atoms.info` so it round-trips
        # through CALM's structure payloads.
        stamp_bulk_canonicalization_transforms(
            atoms_input=atoms,
            atoms_conventional=conv,
            atoms_primitive=prim,
            symprec=symprec_f,
            no_idealize=no_idealize_b,
            dataset=standardized.dataset,
            angle_tolerance=standardized.angle_tolerance,
            spglib_version=standardized.spglib_version,
        )
        spacegroup = get_spacegroup(atoms, symprec=symprec_f)

        f = Formula(conv.get_chemical_formula(mode="metal"))
        formula, _ = f.reduce()

        object.__setattr__(self, "conv", conv)
        object.__setattr__(self, "prim", prim)
        object.__setattr__(self, "spacegroup", str(spacegroup))
        object.__setattr__(self, "formula", str(formula))
        object.__setattr__(self, "uid", str(uid) if uid is not None else None)
        object.__setattr__(self, "label", str(label) if label is not None else None)
        object.__setattr__(self, "symprec", symprec_f)
        object.__setattr__(self, "no_idealize", no_idealize_b)

    def __repr__(self) -> str:
        return (
            f"Bulk(formula='{self.formula}', spacegroup='{self.spacegroup}', "
            f"symprec={self.symprec}, no_idealize={self.no_idealize})"
        )

    @property
    def atoms(self) -> ase_atoms_type:
        """Alias for the standardized conventional cell (ASE Atoms)."""
        return self.conv

    @property
    def conv_cell(self) -> np.ndarray:
        """Return the standardized conventional cell matrix (3x3)."""
        return self.conv.cell.array.copy()

    @property
    def prim_cell(self) -> np.ndarray:
        """Return the standardized primitive cell matrix (3x3)."""
        return self.prim.cell.array.copy()
