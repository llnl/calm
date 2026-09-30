"""Bulk fingerprinting service for structure identification.

This service encapsulates the domain logic for:
- computing deterministic representation fingerprints;
- generating stable UIDs for bulk structures; and
- assembling payload data with derived metadata.
"""

from __future__ import annotations

from typing import Any

from calm.bulk.fingerprinting import (
    atoms_fingerprint_to_dict,
    atoms_formula,
    atoms_lattice,
    atoms_natoms,
    bulk_uid_full_from_atoms_dict,
    bulk_uid_full_from_payload,
)
from calm.structure.payloads import atoms_to_dict


def _standardized_structure_payload(
    submitted_atoms: dict[str, Any],
    *,
    symprec: float,
    no_idealize: bool,
) -> tuple[Any | None, Any | None, dict[str, Any] | None]:
    """Standardize the exact submitted representation stored by CALM.

    Public ingestion accepts serializable ASE-compatible objects, not only
    concrete ``ase.Atoms`` instances. Reconstructing from the already validated
    current atoms payload gives the standardizer one concrete ASE object while
    preserving the exact submitted cell, species, positions, and PBC state that
    will be persisted. Dependency-light callers may still assemble submitted
    metadata without ASE; the repository rejects an incomplete payload if
    persistence is attempted.
    """

    from calm.exceptions import OptionalDependencyError
    from calm.structure.payloads import atoms_from_dict

    try:
        structure = atoms_from_dict(submitted_atoms)
    except OptionalDependencyError:
        return None, None, None

    from calm.bulk.bulk import Bulk as CalmBulk
    from calm.bulk.provenance import (
        CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY,
        get_bulk_canonicalization_transforms,
    )

    standardized = CalmBulk(
        structure,
        symprec=symprec,
        no_idealize=no_idealize,
    )
    conventional = standardized.conv
    primitive = standardized.prim
    record = get_bulk_canonicalization_transforms(conventional)
    if record is None:  # pragma: no cover - guarded by the current bulk writer
        raise RuntimeError(
            "Current bulk standardization did not attach canonicalization provenance."
        )
    metadata = {
        "symprec": standardized.symprec,
        "no_idealize": standardized.no_idealize,
        "angle_tolerance": record.angle_tolerance,
        "spglib_version": record.spglib_version,
        "spacegroup": standardized.spacegroup,
        "formula": standardized.formula,
        "provenance_info_key": (CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY),
        "provenance": record.to_dict(),
    }
    return conventional, primitive, metadata


def _derived_structure_metadata(
    fingerprint: dict[str, Any],
    fingerprint_metadata: dict[str, Any],
    *,
    uid_full: str,
) -> dict[str, Any]:
    return {
        "uid": uid_full,
        "identity_scope": "submitted_representation_v1",
        "formula": (fingerprint_metadata.get("formula") or atoms_formula(fingerprint)),
        "n_atoms": (fingerprint_metadata.get("n_atoms") or atoms_natoms(fingerprint)),
        "lattice": (fingerprint_metadata.get("lattice") or atoms_lattice(fingerprint)),
        "spacegroup": fingerprint_metadata.get("spacegroup"),
    }


def _add_characterization_summary(
    derived: dict[str, Any],
    characterization: dict[str, Any],
) -> None:
    derived.update(
        {
            "reduced_formula": characterization.get("reduced_formula"),
            "composition": characterization.get("composition"),
            "cell_volume_A3": characterization.get("cell_volume_A3"),
            "mass_density_g_cm3": characterization.get("mass_density_g_cm3"),
            "spacegroup_symbol": characterization.get("spacegroup_symbol"),
            "spacegroup_number": characterization.get("spacegroup_number"),
            "crystal_system": characterization.get("crystal_system"),
        }
    )


class BulkFingerprintService:
    """Domain service for representation fingerprints and bulk payloads.

    The service is stateless: methods transform supplied structures or payloads
    without retaining mutable state.
    """

    def compute_fingerprint_and_metadata(
        self,
        structure: Any,
        *,
        decimals: int = 12,
        symprec: float = 1e-5,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Compute a representation fingerprint and best-effort metadata.

        The fingerprint is atom-order invariant and suitable for stable UID
        generation. It retains the submitted cell representation and therefore
        is not a universal crystallographic equivalence key.
        """

        return atoms_fingerprint_to_dict(
            structure,
            decimals=decimals,
            symprec=symprec,
        )

    def compute_uid_from_structure(self, structure: Any) -> str:
        """Compute the content-addressed UID of a structure-backed bulk."""

        fingerprint, _ = self.compute_fingerprint_and_metadata(structure)
        return bulk_uid_full_from_atoms_dict(fingerprint)

    def compute_uid_from_payload(self, payload: dict[str, Any]) -> str:
        """Compute the UID of a metadata-only bulk payload."""

        return bulk_uid_full_from_payload(payload)

    def assemble_structure_payload(
        self,
        structure: Any,
        *,
        user_metadata: dict[str, Any] | None = None,
        symprec: float = 1e-5,
        no_idealize: bool = False,
    ) -> dict[str, Any]:
        """Assemble the persistent payload for a structure-backed bulk.

        The submitted representation remains authoritative for the persistent
        UID. When ASE is available, every serializable ASE-compatible input is
        normalized through that exact submitted payload before conventional and
        primitive cells plus their verified provenance are stored.
        """

        fingerprint, fingerprint_metadata = self.compute_fingerprint_and_metadata(
            structure,
            symprec=symprec,
        )
        atoms_dict = atoms_to_dict(structure)
        uid_full = bulk_uid_full_from_atoms_dict(fingerprint)
        conventional, primitive, standardization = _standardized_structure_payload(
            atoms_dict,
            symprec=symprec,
            no_idealize=no_idealize,
        )
        derived = _derived_structure_metadata(
            fingerprint,
            fingerprint_metadata,
            uid_full=uid_full,
        )

        from calm.structure.characterization import (
            material_characterization_data,
        )

        characterization = material_characterization_data(
            structure,
            derived=derived,
        )
        _add_characterization_summary(derived, characterization)

        payload = {
            "atoms": atoms_dict,
            "fingerprint": fingerprint,
            "derived": derived,
            "characterization": characterization,
            "meta": user_metadata or {},
        }
        if (
            conventional is not None
            and primitive is not None
            and standardization is not None
        ):
            payload.update(
                {
                    "atoms_conventional": atoms_to_dict(conventional),
                    "atoms_primitive": atoms_to_dict(primitive),
                    "standardization": standardization,
                }
            )
        return payload

    def extract_formula(self, fingerprint: dict[str, Any]) -> str:
        """Extract a chemical formula from a representation fingerprint."""

        return atoms_formula(fingerprint)

    def extract_lattice_params(
        self,
        fingerprint: dict[str, Any],
    ) -> dict[str, float]:
        """Extract lattice parameters from a representation fingerprint."""

        return atoms_lattice(fingerprint)
