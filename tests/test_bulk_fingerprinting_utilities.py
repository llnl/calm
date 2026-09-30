"""Unit tests for bulk fingerprinting utilities.

Tests core fingerprinting and UID generation functions in isolation.
These utilities are critical for deterministic bulk identification.
"""

from __future__ import annotations

import pytest


def test_canonical_json_bytes_determinism():
    """Test that canonical_json_bytes produces identical output for identical inputs."""
    from calm.bulk.fingerprinting import canonical_json_bytes

    obj = {"a": 1, "b": [2, 3], "c": {"d": 4}}

    # Same object should produce same bytes
    bytes1 = canonical_json_bytes(obj)
    bytes2 = canonical_json_bytes(obj)

    assert bytes1 == bytes2
    assert isinstance(bytes1, bytes)


def test_canonical_json_bytes_key_order_invariance():
    """Test that key order doesn't affect canonical JSON."""
    from calm.bulk.fingerprinting import canonical_json_bytes

    obj1 = {"z": 1, "a": 2, "m": 3}
    obj2 = {"a": 2, "m": 3, "z": 1}

    # Different key order should produce same bytes
    bytes1 = canonical_json_bytes(obj1)
    bytes2 = canonical_json_bytes(obj2)

    assert bytes1 == bytes2


def test_atoms_fingerprint_to_dict_determinism():
    """Test that atoms_fingerprint_to_dict is deterministic."""
    from calm.bulk.fingerprinting import atoms_fingerprint_to_dict

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    # Create a simple structure
    atoms = Atoms("Al4", positions=[(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)],
                  cell=[4.05, 4.05, 4.05], pbc=True)

    # Compute fingerprint twice
    fp1, meta1 = atoms_fingerprint_to_dict(atoms, decimals=12)
    fp2, meta2 = atoms_fingerprint_to_dict(atoms, decimals=12)

    # Should be identical
    assert fp1 == fp2
    assert meta1 == meta2


def test_atoms_fingerprint_order_invariance():
    """Test that atom order doesn't affect fingerprint."""
    from calm.bulk.fingerprinting import atoms_fingerprint_to_dict

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    # Create structures with same atoms in different order
    atoms1 = Atoms("AlCu", positions=[(0, 0, 0), (0.5, 0.5, 0.5)],
                   cell=[4.0, 4.0, 4.0], pbc=True)

    atoms2 = Atoms("CuAl", positions=[(0.5, 0.5, 0.5), (0, 0, 0)],
                   cell=[4.0, 4.0, 4.0], pbc=True)

    # Compute fingerprints
    fp1, _ = atoms_fingerprint_to_dict(atoms1, decimals=12)
    fp2, _ = atoms_fingerprint_to_dict(atoms2, decimals=12)

    # Should be identical (sorted by atomic number then position)
    assert fp1 == fp2


def test_bulk_uid_full_from_payload_is_deterministic():
    """Metadata-only bulk identities use one exact payload path."""
    from calm.bulk.fingerprinting import bulk_uid_full_from_payload

    payload_a = {"material": "Al", "source": "test"}
    payload_b = {"source": "test", "material": "Al"}

    uid_a = bulk_uid_full_from_payload(payload_a)
    uid_b = bulk_uid_full_from_payload(payload_b)

    assert uid_a == uid_b
    assert len(uid_a) == 64


def test_bulk_uid_full_from_atoms_dict():
    """Test UID generation from fingerprint dict."""
    from calm.bulk.fingerprinting import bulk_uid_full_from_atoms_dict

    atoms_dict = {
        "numbers": [13, 13],  # Al
        "scaled_positions": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        "cell": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        "pbc": [True, True, True]
    }

    # Generate UID
    uid = bulk_uid_full_from_atoms_dict(atoms_dict)

    # Should have bulk: prefix
    assert uid.startswith("bulk:")
    assert len(uid) > 10


def test_atoms_formula_extraction():
    """Test chemical formula extraction from fingerprint."""
    from calm.bulk.fingerprinting import atoms_formula

    fingerprint = {
        "numbers": [13, 13, 29],  # Al, Al, Cu
    }

    formula = atoms_formula(fingerprint)

    # Should extract formula
    assert "Al" in formula
    assert "Cu" in formula


def test_atoms_natoms_extraction():
    """Test atom count extraction from fingerprint."""
    from calm.bulk.fingerprinting import atoms_natoms

    fingerprint = {
        "numbers": [13, 13, 29, 29, 29],
    }

    natoms = atoms_natoms(fingerprint)

    assert natoms == 5


def test_atoms_lattice_extraction():
    """Test lattice parameter extraction from fingerprint."""
    from calm.bulk.fingerprinting import atoms_lattice

    fingerprint = {
        "cell": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
    }

    lattice = atoms_lattice(fingerprint)

    # Should extract a, b, c parameters
    assert "a" in lattice
    assert "b" in lattice
    assert "c" in lattice
    assert lattice["a"] == pytest.approx(4.0, abs=0.01)
    assert lattice["b"] == pytest.approx(4.0, abs=0.01)
    assert lattice["c"] == pytest.approx(4.0, abs=0.01)


def test_structure_to_spglib_cell():
    """Test ASE to spglib conversion."""
    from calm.bulk.fingerprinting import structure_to_spglib_cell

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    atoms = Atoms("Al", positions=[(0, 0, 0)], cell=[4.0, 4.0, 4.0], pbc=True)

    # Convert to spglib format
    cell_tuple = structure_to_spglib_cell(atoms)

    # Should return tuple of (cell, positions, numbers)
    assert isinstance(cell_tuple, tuple)
    assert len(cell_tuple) == 3


def test_atoms_to_dict():
    """Test structure serialization to dict."""
    from calm.structure.payloads import atoms_to_dict

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    atoms = Atoms("Al2", positions=[(0, 0, 0), (0.5, 0.5, 0.5)],
                  cell=[4.0, 4.0, 4.0], pbc=True)

    # Serialize to dict
    atoms_dict = atoms_to_dict(atoms)

    # Should contain required keys
    assert "numbers" in atoms_dict
    assert "scaled_positions" in atoms_dict
    assert "cell" in atoms_dict
    assert "pbc" in atoms_dict

    # Verify content
    assert len(atoms_dict["numbers"]) == 2
    assert len(atoms_dict["scaled_positions"]) == 2


def test_atoms_fingerprint_metadata_extraction():
    """Test that metadata is extracted during fingerprinting."""
    from calm.bulk.fingerprinting import atoms_fingerprint_to_dict

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    # Create FCC Al structure
    atoms = Atoms("Al4",
                  positions=[(0, 0, 0), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)],
                  cell=[4.05, 4.05, 4.05],
                  pbc=True)

    # Extract fingerprint and metadata
    fingerprint, metadata = atoms_fingerprint_to_dict(atoms, decimals=12)

    # Metadata should contain formula, n_atoms, lattice
    assert "formula" in metadata
    assert "n_atoms" in metadata
    assert "lattice" in metadata
    assert metadata["n_atoms"] == 4
    assert "Al" in metadata["formula"]


def test_fingerprint_with_numerical_rounding():
    """Test that numerical rounding is applied correctly."""
    from calm.bulk.fingerprinting import atoms_fingerprint_to_dict

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    # Create structure with slightly different positions
    # Use a difference that's significant at 8 decimals but not at 6
    atoms1 = Atoms("Al", positions=[(0.1234567, 0, 0)],
                   cell=[4.0, 4.0, 4.0], pbc=True)

    atoms2 = Atoms("Al", positions=[(0.1234568, 0, 0)],
                   cell=[4.0, 4.0, 4.0], pbc=True)

    # With 6 decimals, should round to same value
    fp1_6, _ = atoms_fingerprint_to_dict(atoms1, decimals=6)
    fp2_6, _ = atoms_fingerprint_to_dict(atoms2, decimals=6)
    assert fp1_6 == fp2_6  # Should round to same value at 6 decimals

    # With 8 decimals, should be different
    fp1_8, _ = atoms_fingerprint_to_dict(atoms1, decimals=8)
    fp2_8, _ = atoms_fingerprint_to_dict(atoms2, decimals=8)
    assert fp1_8 != fp2_8  # Different at higher precision


def test_fingerprint_wraps_periodic_boundary_before_hashing():
    """Fractional coordinates differing by a lattice vector share a fingerprint."""
    from calm.bulk.fingerprinting import atoms_fingerprint_to_dict

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    at_origin = Atoms(
        "Al",
        positions=[(0.0, 0.0, 0.0)],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    at_boundary = Atoms(
        "Al",
        positions=[(4.0, 0.0, 0.0)],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )

    fingerprint_origin, _ = atoms_fingerprint_to_dict(at_origin)
    fingerprint_boundary, _ = atoms_fingerprint_to_dict(at_boundary)

    assert fingerprint_origin == fingerprint_boundary


def test_fingerprint_metadata_extractors_reject_malformed_present_state():
    from calm.bulk.fingerprinting import (
        atoms_formula,
        atoms_lattice,
        atoms_natoms,
    )

    with pytest.raises(ValueError, match="missing required field 'numbers'"):
        atoms_formula({})
    with pytest.raises(TypeError, match="must be an integer"):
        atoms_natoms({"numbers": [13.0]})
    with pytest.raises(ValueError, match="nonsingular"):
        atoms_lattice({"cell": [[0.0, 0.0, 0.0]] * 3})


def test_canonical_json_bytes_rejects_nonfinite_identity_values():
    from calm.bulk.fingerprinting import canonical_json_bytes

    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_json_bytes({"value": float("nan")})
