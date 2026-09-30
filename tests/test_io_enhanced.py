"""Tests for enhanced I/O functions in calm.structure.io."""

from __future__ import annotations


import numpy as np
import pytest
from ase import Atoms

from calm.structure.io import (
    load_structure,
    write_structure,
    safe_write_structure,
    write_json,
)
from calm.exceptions import FileIOError, InvalidStructureError


class TestLoadStructure:
    """Test enhanced load_structure function."""

    def test_load_valid_cif(self, tmp_path):
        """Test loading a valid CIF file."""
        # Create a test CIF file
        cif_content = """data_test
_cell_length_a    4.05
_cell_length_b    4.05
_cell_length_c    4.05
_cell_angle_alpha 90
_cell_angle_beta  90
_cell_angle_gamma 90
_symmetry_space_group_name_H-M 'P 1'
loop_
_atom_site_label
_atom_site_fract_x
_atom_site_fract_y
_atom_site_fract_z
Al 0.0 0.0 0.0
"""
        cif_path = tmp_path / "test.cif"
        cif_path.write_text(cif_content)

        # Load with validation
        atoms = load_structure(cif_path, validate=True)

        assert len(atoms) == 1
        assert atoms.get_chemical_symbols()[0] == "Al"

    def test_load_with_expected_pbc(self, tmp_path):
        """Test loading with PBC validation."""
        # Create structure with PBC
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

        poscar_path = tmp_path / "POSCAR"
        atoms.write(str(poscar_path), format="vasp")

        # Should pass with correct PBC expectation
        loaded = load_structure(poscar_path, expected_pbc=[True, True, True])
        assert list(loaded.pbc) == [True, True, True]

        # Should fail with wrong PBC expectation
        with pytest.raises(InvalidStructureError, match="PBC mismatch"):
            load_structure(poscar_path, expected_pbc=[True, True, False])

    def test_load_file_not_found(self, tmp_path):
        """Test error when file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.cif"

        with pytest.raises(FileIOError, match="not found"):
            load_structure(nonexistent)

    def test_load_directory_not_file(self, tmp_path):
        """Test error when path is directory."""
        directory = tmp_path / "test_dir"
        directory.mkdir()

        with pytest.raises(FileIOError, match="not a file"):
            load_structure(directory)

    def test_load_corrupted_file(self, tmp_path):
        """Test error on corrupted file."""
        corrupted = tmp_path / "corrupted.cif"
        corrupted.write_text("This is not a valid CIF file!\n@#$%^&*()")

        with pytest.raises(FileIOError, match="Failed to parse"):
            load_structure(corrupted)

    def test_load_unknown_format(self, tmp_path):
        """Test error on unknown file format."""
        unknown = tmp_path / "test.unknown"
        unknown.write_text("Some random data")

        with pytest.raises(FileIOError, match="Failed to parse"):
            load_structure(unknown)

    def test_load_empty_structure_fails(self, tmp_path):
        """Test that empty structure fails validation."""
        # Create file with empty structure
        empty_atoms = Atoms()
        xyz_path = tmp_path / "empty.xyz"
        empty_atoms.write(str(xyz_path))

        with pytest.raises(InvalidStructureError, match="empty"):
            load_structure(xyz_path, validate=True)

    def test_load_skip_validation(self, tmp_path):
        """Test that validation can be skipped."""
        # Create file with empty structure
        empty_atoms = Atoms()
        xyz_path = tmp_path / "empty.xyz"
        empty_atoms.write(str(xyz_path))

        # Should succeed when validation disabled
        atoms = load_structure(xyz_path, validate=False)
        assert len(atoms) == 0

    def test_load_with_index(self, tmp_path):
        """Test loading specific frame from trajectory."""
        # Create multi-frame XYZ file
        atoms1 = Atoms("H", positions=[[0, 0, 0]], cell=[5, 5, 5])
        atoms2 = Atoms("He", positions=[[1, 1, 1]], cell=[5, 5, 5])

        xyz_path = tmp_path / "trajectory.xyz"
        atoms1.write(str(xyz_path))
        atoms2.write(str(xyz_path), append=True)

        # Load first frame
        loaded1 = load_structure(xyz_path, index=0, validate=False)
        assert loaded1.get_chemical_symbols()[0] == "H"

        # Load last frame
        loaded2 = load_structure(xyz_path, index=-1, validate=False)
        assert loaded2.get_chemical_symbols()[0] == "He"


class TestWriteStructure:
    """Test write_structure function."""

    def test_write_basic(self, tmp_path):
        """Test basic write operation."""
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.xyz"
        write_structure(output_path, atoms)

        assert output_path.exists()

        # Verify by reading back
        loaded = load_structure(output_path, validate=False)
        assert len(loaded) == 1

    def test_write_creates_parent_dir(self, tmp_path):
        """Test that write creates parent directories."""
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4])

        nested_path = tmp_path / "subdir" / "nested" / "output.xyz"
        write_structure(nested_path, atoms)

        assert nested_path.exists()

    def test_write_permission_error(self, tmp_path):
        """Test error on permission denied."""
        import os
        import stat

        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4])

        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, stat.S_IRUSR | stat.S_IXUSR)

        output_path = readonly_dir / "output.xyz"

        try:
            with pytest.raises(FileIOError, match="Permission denied"):
                write_structure(output_path, atoms)
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, stat.S_IRWXU)


class TestSafeWriteStructure:
    """Test safe_write_structure function."""

    def test_safe_write_basic(self, tmp_path):
        """Test basic safe write."""
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.cif"
        safe_write_structure(output_path, atoms)

        assert output_path.exists()

        # Verify structure
        loaded = load_structure(output_path, validate=False)
        assert len(loaded) == 1

    def test_safe_write_creates_backup(self, tmp_path):
        """Test that backup is created when overwriting."""
        atoms1 = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)
        atoms2 = Atoms("Cu", positions=[[0, 0, 0]], cell=[3, 3, 3], pbc=True)

        output_path = tmp_path / "output.cif"
        backup_path = output_path.with_suffix(".cif.bak")

        # First write
        safe_write_structure(output_path, atoms1, backup=True)
        assert output_path.exists()
        assert not backup_path.exists()

        # Second write (should create backup)
        safe_write_structure(output_path, atoms2, backup=True)
        assert output_path.exists()
        assert backup_path.exists()

        # Verify backup contains first structure (need to specify format for .bak)
        backup_loaded = load_structure(backup_path, validate=False, format="cif")
        assert backup_loaded.get_chemical_symbols()[0] == "Al"

        # Verify output contains second structure
        output_loaded = load_structure(output_path, validate=False)
        assert output_loaded.get_chemical_symbols()[0] == "Cu"

    def test_safe_write_no_backup(self, tmp_path):
        """Test safe write without backup."""
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.cif"

        # Write twice without backup
        safe_write_structure(output_path, atoms, backup=False)
        safe_write_structure(output_path, atoms, backup=False)

        # Backup should not exist
        backup_path = output_path.with_suffix(".cif.bak")
        assert not backup_path.exists()

    def test_safe_write_validation_fails(self, tmp_path):
        """Test that invalid structure is rejected."""
        # Create structure with NaN position
        atoms = Atoms("Al", positions=[[np.nan, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.cif"

        with pytest.raises(InvalidStructureError, match="NaN or infinite"):
            safe_write_structure(output_path, atoms, validate=True)

        # File should not be created
        assert not output_path.exists()

    def test_safe_write_skip_validation(self, tmp_path):
        """Test that validation can be skipped."""
        # Create structure with NaN (would normally fail)
        atoms = Atoms("Al", positions=[[np.nan, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.xyz"

        # Should succeed when validation disabled
        safe_write_structure(output_path, atoms, validate=False, verify=False)

        assert output_path.exists()

    def test_safe_write_verification(self, tmp_path):
        """Test write verification."""
        atoms = Atoms("Al2", positions=[[0, 0, 0], [2, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.xyz"

        # Write with verification
        safe_write_structure(output_path, atoms, verify=True)

        assert output_path.exists()

    def test_safe_write_atomic_operation(self, tmp_path):
        """Test that write is atomic (temp file used)."""
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.cif"

        safe_write_structure(output_path, atoms)

        # Temp file should not exist after successful write
        temp_files = list(tmp_path.glob(".tmp_*"))
        assert len(temp_files) == 0




class TestJSON:
    """Test current JSON writing behavior."""

    def test_write_json_basic(self, tmp_path):
        import json

        data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        json_path = tmp_path / "test.json"
        write_json(json_path, data)

        assert json.loads(json_path.read_text(encoding="utf-8")) == data
        assert json_path.read_text(encoding="utf-8").endswith("\n")

    def test_write_json_creates_parent(self, tmp_path):
        nested_path = tmp_path / "subdir" / "test.json"
        write_json(nested_path, {"test": "data"})
        assert nested_path.exists()

    def test_write_json_non_serializable(self, tmp_path):
        json_path = tmp_path / "test.json"
        with pytest.raises(FileIOError, match="not JSON-serializable"):
            write_json(json_path, {"func": lambda x: x})


class TestIntegration:
    """Integration tests combining multiple I/O operations."""

    def test_load_write_safe_round_trip(self, tmp_path):
        """Test loading, modifying, and safely writing back."""
        # Create original structure
        original = Atoms("Al4", positions=[[0, 0, 0], [2, 0, 0], [0, 2, 0], [2, 2, 0]], cell=[4, 4, 10], pbc=True)

        input_path = tmp_path / "POSCAR"
        original.write(str(input_path), format="vasp")

        # Load (don't check PBC since some formats don't preserve it)
        atoms = load_structure(input_path, validate=True)

        # Modify
        atoms.positions[:, 2] += 1.0  # Shift all atoms in z

        # Safe write back
        output_path = tmp_path / "POSCAR_out"
        safe_write_structure(output_path, atoms, backup=False, verify=True, format="vasp")

        # Verify final structure
        final = load_structure(output_path, validate=True)
        assert len(final) == 4
        assert np.allclose(final.positions[:, 2], 1.0)

    def test_safe_write_with_failure_recovery(self, tmp_path):
        """Test that safe write recovers from failures."""
        atoms = Atoms("Al", positions=[[0, 0, 0]], cell=[4, 4, 4], pbc=True)

        output_path = tmp_path / "output.cif"

        # First write succeeds
        safe_write_structure(output_path, atoms, backup=True)
        assert output_path.exists()

        # Second write with invalid structure should preserve backup
        bad_atoms = Atoms()  # Empty

        with pytest.raises(InvalidStructureError):
            safe_write_structure(output_path, bad_atoms, backup=True, validate=True)

        # Original file should still exist and be valid
        assert output_path.exists()
        loaded = load_structure(output_path, validate=False)
        assert len(loaded) == 1
