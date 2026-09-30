"""Tests for the current CALM ASE-atoms validation owner."""

from __future__ import annotations

import numpy as np
import pytest
from ase import Atoms

from calm.structure.validation import ValidationError, validate_atoms


class TestValidateAtoms:
    """Validate the structural conditions used by CALM file I/O."""

    def test_valid_bulk(self):
        atoms = Atoms(
            "Al",
            positions=[[0, 0, 0]],
            cell=[4.05, 4.05, 4.05],
            pbc=True,
        )
        validate_atoms(atoms, expected_pbc=[True, True, True])

    def test_valid_slab(self):
        atoms = Atoms(
            "Al",
            positions=[[0, 0, 0]],
            cell=[4.05, 4.05, 10.0],
            pbc=[True, True, False],
        )
        validate_atoms(atoms, expected_pbc=[True, True, False])

    def test_empty_atoms_fails(self):
        with pytest.raises(ValidationError, match="Atoms object is empty"):
            validate_atoms(Atoms())

    def test_empty_atoms_allowed(self):
        validate_atoms(Atoms(), allow_empty=True)

    def test_zero_volume_fails(self):
        atoms = Atoms(
            "H",
            positions=[[0, 0, 0]],
            cell=[[1, 0, 0], [0, 1, 0], [0, 0, 0]],
            pbc=True,
        )
        with pytest.raises(ValidationError, match="Cell volume .* is too small"):
            validate_atoms(atoms)

    def test_small_volume_fails(self):
        atoms = Atoms(
            "H",
            positions=[[0, 0, 0]],
            cell=[0.01, 0.01, 0.01],
            pbc=True,
        )
        with pytest.raises(ValidationError, match="Cell volume .* is too small"):
            validate_atoms(atoms, min_volume=1e-3)

    def test_pbc_mismatch_fails(self):
        atoms = Atoms(
            "Al",
            positions=[[0, 0, 0]],
            cell=[4.05, 4.05, 4.05],
            pbc=[True, True, False],
        )
        with pytest.raises(ValidationError, match="PBC mismatch"):
            validate_atoms(atoms, expected_pbc=[True, True, True])

    def test_nan_positions_fail(self):
        atoms = Atoms(
            "Al",
            positions=[[np.nan, 0, 0]],
            cell=[4.05, 4.05, 4.05],
            pbc=True,
        )
        with pytest.raises(ValidationError, match="Positions contain NaN or infinite"):
            validate_atoms(atoms)

    def test_inf_positions_fail(self):
        atoms = Atoms(
            "Al",
            positions=[[np.inf, 0, 0]],
            cell=[4.05, 4.05, 4.05],
            pbc=True,
        )
        with pytest.raises(ValidationError, match="Positions contain NaN or infinite"):
            validate_atoms(atoms)

    def test_finite_check_can_be_disabled(self):
        atoms = Atoms(
            "Al",
            positions=[[np.nan, 0, 0]],
            cell=[4.05, 4.05, 4.05],
            pbc=True,
        )
        validate_atoms(atoms, check_finite_positions=False)

    def test_context_in_error(self):
        with pytest.raises(ValidationError, match="for bulk structure"):
            validate_atoms(Atoms(), context="bulk structure")

    def test_non_atoms_object_fails(self):
        with pytest.raises(ValidationError, match="Expected ase.Atoms object"):
            validate_atoms("not an atoms object")

    def test_invalid_expected_pbc_length(self):
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)
        with pytest.raises(ValidationError, match="expected_pbc must have length 3"):
            validate_atoms(atoms, expected_pbc=[True, True])
