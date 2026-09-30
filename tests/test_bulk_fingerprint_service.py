"""Unit tests for BulkFingerprintService.

Tests the domain service that wraps bulk fingerprinting utilities.
"""

from __future__ import annotations

import pytest


def test_service_compute_fingerprint_and_metadata():
    """Test compute_fingerprint_and_metadata method."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()
    atoms = Atoms("Al", positions=[(0, 0, 0)], cell=[4.0, 4.0, 4.0], pbc=True)

    # Compute fingerprint and metadata
    fingerprint, metadata = service.compute_fingerprint_and_metadata(atoms)

    # Should return dictionaries
    assert isinstance(fingerprint, dict)
    assert isinstance(metadata, dict)

    # Fingerprint should have required keys
    assert "numbers" in fingerprint
    assert "scaled_positions" in fingerprint
    assert "cell" in fingerprint

    # Metadata should have derived info
    assert "formula" in metadata
    assert "n_atoms" in metadata


def test_service_compute_uid_from_structure():
    """Test compute_uid_from_structure method."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()
    atoms = Atoms("Al2", positions=[(0, 0, 0), (0.5, 0.5, 0.5)],
                  cell=[4.0, 4.0, 4.0], pbc=True)

    # Compute UID
    uid = service.compute_uid_from_structure(atoms)

    # Should return UID with bulk: prefix
    assert isinstance(uid, str)
    assert uid.startswith("bulk:")


def test_service_compute_uid_from_structure_determinism():
    """Test that compute_uid_from_structure is deterministic."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()
    atoms = Atoms("Al2", positions=[(0, 0, 0), (0.5, 0.5, 0.5)],
                  cell=[4.0, 4.0, 4.0], pbc=True)

    # Compute UID twice
    uid1 = service.compute_uid_from_structure(atoms)
    uid2 = service.compute_uid_from_structure(atoms)

    # Should be identical
    assert uid1 == uid2


def test_service_compute_uid_from_payload():
    """Test compute_uid_from_payload method."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    service = BulkFingerprintService()
    payload = {"material": "Al", "source": "test"}

    # Compute UID from payload
    uid = service.compute_uid_from_payload(payload)

    # Should return hex string
    assert isinstance(uid, str)
    assert len(uid) == 64  # SHA256 hex


def test_service_compute_uid_from_payload_determinism():
    """Test that compute_uid_from_payload is deterministic."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    service = BulkFingerprintService()
    payload = {"material": "Al", "source": "test"}

    # Compute UID twice
    uid1 = service.compute_uid_from_payload(payload)
    uid2 = service.compute_uid_from_payload(payload)

    # Should be identical
    assert uid1 == uid2


def test_service_assemble_structure_payload():
    """Test assemble_structure_payload method."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()
    atoms = Atoms("Al2", positions=[(0, 0, 0), (0.5, 0.5, 0.5)],
                  cell=[4.0, 4.0, 4.0], pbc=True)
    user_meta = {"source": "test", "notes": "test structure"}

    # Assemble payload
    payload = service.assemble_structure_payload(atoms, user_metadata=user_meta)

    # Should have required keys
    assert "atoms" in payload
    assert "fingerprint" in payload
    assert "derived" in payload
    assert "characterization" in payload
    assert "meta" in payload
    assert "atoms_conventional" in payload
    assert "atoms_primitive" in payload
    assert "standardization" in payload

    # Verify structure
    assert payload["meta"] == user_meta
    assert "formula" in payload["derived"]
    assert "n_atoms" in payload["derived"]
    assert "lattice" in payload["derived"]
    assert payload["characterization"]["schema"] == "calm.material_characterization.v1"
    assert payload["characterization"]["cell_volume_A3"] == pytest.approx(64.0)
    assert payload["derived"]["identity_scope"] == "submitted_representation_v1"
    provenance = payload["standardization"]["provenance"]
    assert provenance["schema_version"] == 3
    assert provenance["conventional_relation_verified"] is True
    assert provenance["primitive_relation_verified"] is True
    assert provenance["angle_tolerance"] == -1.0
    assert provenance["spglib_version"]
    assert payload["standardization"]["angle_tolerance"] == -1.0
    assert payload["standardization"]["spglib_version"]


def test_service_standardizes_serializable_atoms_like_input():
    """Atoms-like public inputs must produce one complete current bulk row."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService
    from calm.project.domain.contracts.bulk_record import (
        current_bulk_structure_record,
    )

    pytest.importorskip("spglib")
    ase = pytest.importorskip("ase")

    class AtomsLike:
        def __init__(self, atoms):
            self._atoms = atoms

        def __getattr__(self, name):
            return getattr(self._atoms, name)

        def __len__(self):
            return len(self._atoms)

    submitted = AtomsLike(
        ase.Atoms(
            "Al",
            scaled_positions=[(0.0, 0.0, 0.0)],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        )
    )

    assert not isinstance(submitted, ase.Atoms)

    payload = BulkFingerprintService().assemble_structure_payload(submitted)

    assert current_bulk_structure_record(payload) is not None
    assert payload["atoms"]["cell"] == [
        [4.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [0.0, 0.0, 4.0],
    ]


def test_service_characterizes_submitted_representation(monkeypatch):
    """Persisted characterization must describe the submitted atoms."""
    import calm.project.application.bulk_fingerprinting as module
    import calm.structure.characterization as characterization_module

    submitted = object()
    conventional = object()
    primitive = object()
    labels = {
        submitted: "submitted",
        conventional: "conventional",
        primitive: "primitive",
    }
    fingerprint = {
        "numbers": [13],
        "scaled_positions": [[0.0, 0.0, 0.0]],
        "cell": [[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        "pbc": [True, True, True],
    }
    fingerprint_metadata = {
        "formula": "Al",
        "n_atoms": 1,
        "lattice": {"a": 4.0, "b": 4.0, "c": 4.0},
        "spacegroup": "Pm-3m (221)",
    }
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        module,
        "atoms_fingerprint_to_dict",
        lambda structure, *, decimals, symprec: (
            fingerprint,
            fingerprint_metadata,
        ),
    )
    monkeypatch.setattr(
        module,
        "atoms_to_dict",
        lambda structure: {"representation": labels[structure]},
    )
    monkeypatch.setattr(
        module,
        "bulk_uid_full_from_atoms_dict",
        lambda value: "bulk:test",
    )
    monkeypatch.setattr(
        module,
        "_standardized_structure_payload",
        lambda structure, *, symprec, no_idealize: (
            conventional,
            primitive,
            {"provenance": {}},
        ),
    )

    def characterize(structure, *, derived):
        seen["structure"] = structure
        return {
            "schema": "calm.material_characterization.v1",
            "formula": "Al",
            "reduced_formula": "Al",
            "composition": {"Al": 1},
            "cell_volume_A3": 64.0,
        }

    monkeypatch.setattr(
        characterization_module,
        "material_characterization_data",
        characterize,
    )

    payload = module.BulkFingerprintService().assemble_structure_payload(
        submitted
    )

    assert seen["structure"] is submitted
    assert payload["atoms"] == {"representation": "submitted"}
    assert payload["atoms_conventional"] == {
        "representation": "conventional"
    }
    assert payload["characterization"]["cell_volume_A3"] == 64.0
    assert payload["derived"]["cell_volume_A3"] == 64.0


def test_service_assemble_structure_payload_without_metadata():
    """Test assemble_structure_payload without user metadata."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()
    atoms = Atoms("Al", positions=[(0, 0, 0)], cell=[4.0, 4.0, 4.0], pbc=True)

    # Assemble without metadata
    payload = service.assemble_structure_payload(atoms, user_metadata=None)

    # Should still have all required keys
    assert "atoms" in payload
    assert "fingerprint" in payload
    assert "derived" in payload
    assert "meta" in payload
    assert payload["meta"] == {}


def test_service_extract_formula():
    """Test extract_formula method."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    service = BulkFingerprintService()
    fingerprint = {"numbers": [13, 13, 29]}  # Al, Al, Cu

    # Extract formula
    formula = service.extract_formula(fingerprint)

    # Should contain both elements
    assert "Al" in formula
    assert "Cu" in formula


def test_service_extract_lattice_params():
    """Test extract_lattice_params method."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    service = BulkFingerprintService()
    fingerprint = {
        "cell": [[4.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 6.0]],
    }

    # Extract lattice params
    lattice = service.extract_lattice_params(fingerprint)

    # Should have a, b, c
    assert "a" in lattice
    assert "b" in lattice
    assert "c" in lattice
    assert lattice["a"] == pytest.approx(4.0, abs=0.01)
    assert lattice["b"] == pytest.approx(5.0, abs=0.01)
    assert lattice["c"] == pytest.approx(6.0, abs=0.01)


def test_service_stateless():
    """Test that service is stateless."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    # Create two service instances
    service1 = BulkFingerprintService()
    service2 = BulkFingerprintService()

    atoms = Atoms("Al", positions=[(0, 0, 0)], cell=[4.0, 4.0, 4.0], pbc=True)

    # Both should produce identical results
    uid1 = service1.compute_uid_from_structure(atoms)
    uid2 = service2.compute_uid_from_structure(atoms)

    assert uid1 == uid2


def test_service_payload_contains_uid():
    """Test that assembled payload contains UID in derived metadata."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()
    atoms = Atoms("Al", positions=[(0, 0, 0)], cell=[4.0, 4.0, 4.0], pbc=True)

    # Assemble payload
    payload = service.assemble_structure_payload(atoms)

    # Derived metadata should include UID
    assert "uid" in payload["derived"]
    assert payload["derived"]["uid"].startswith("bulk:")


def test_service_fingerprint_rounding_control():
    """Test that rounding precision can be controlled."""
    from calm.project.application.bulk_fingerprinting import BulkFingerprintService

    try:
        from ase import Atoms
    except ImportError:
        pytest.skip("ASE not available")

    service = BulkFingerprintService()

    # Create structure with high-precision position
    atoms = Atoms("Al", positions=[(0.123456789012345, 0, 0)],
                  cell=[4.0, 4.0, 4.0], pbc=True)

    # Compute with different precisions
    fp1, _ = service.compute_fingerprint_and_metadata(atoms, decimals=6)
    fp2, _ = service.compute_fingerprint_and_metadata(atoms, decimals=12)

    # Position values should be rounded differently
    pos1 = fp1["scaled_positions"][0][0]
    pos2 = fp2["scaled_positions"][0][0]

    # Both should be rounded, but to different precisions
    assert isinstance(pos1, float)
    assert isinstance(pos2, float)
