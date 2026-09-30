"""Exact-current persisted contract for structure-backed bulk records.

Metadata-only bulks remain valid current project state.  Once a payload carries
submitted atoms, however, the current schema requires both standardized cell
representations, one shared canonicalization record, and a matching
``standardization`` projection.  The contract is dependency-light and validates
serialized structures without importing ASE or spglib.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from calm.bulk.provenance import (
    CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY,
    BulkCanonicalizationTransforms,
    parse_bulk_canonicalization_transforms,
    validate_bulk_canonicalization_relations,
)
from calm.structure.payloads import canonical_atoms_payload


class CurrentBulkPayloadError(ValueError):
    """A present bulk payload does not satisfy the current project contract."""


class MissingBulkCanonicalizationProvenanceError(CurrentBulkPayloadError):
    """A structure-backed current bulk is missing required provenance state."""


class InvalidBulkCanonicalizationProvenanceError(CurrentBulkPayloadError):
    """Present bulk canonicalization provenance is malformed or inconsistent."""


@dataclass(frozen=True)
class CurrentBulkStructureRecord:
    """Validated atomistic state carried by one current persisted bulk."""

    atoms_submitted: dict[str, Any]
    atoms_conventional: dict[str, Any]
    atoms_primitive: dict[str, Any]
    standardization: dict[str, Any]
    provenance: BulkCanonicalizationTransforms


_SUPPLEMENTAL_FIELDS = frozenset(
    {"atoms_conventional", "atoms_primitive", "standardization"}
)
_PROJECTION_FIELDS = (
    "symprec",
    "no_idealize",
    "angle_tolerance",
    "spglib_version",
)


def _canonical_atoms(
    name: str,
    value: Any,
    *,
    error_type: type[CurrentBulkPayloadError],
) -> dict[str, Any]:
    try:
        canonical = canonical_atoms_payload(value)
    except (TypeError, ValueError) as exc:
        raise error_type(
            f"Current structure-backed bulk field {name!r} is malformed."
        ) from exc
    if dict(value) != canonical:
        raise error_type(
            f"Current structure-backed bulk field {name!r} must already use "
            "CALM's canonical atoms representation."
        )
    if canonical["pbc"] != [True, True, True]:
        raise error_type(
            f"Current structure-backed bulk field {name!r} must be periodic in "
            "all three directions."
        )
    return canonical


def _required_supplemental_atoms(
    payload: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    if name not in payload or payload[name] is None:
        raise MissingBulkCanonicalizationProvenanceError(
            f"Current structure-backed bulk payload is missing required {name!r}."
        )
    return _canonical_atoms(
        name,
        payload[name],
        error_type=InvalidBulkCanonicalizationProvenanceError,
    )


def _atoms_provenance(
    atoms: Mapping[str, Any],
    *,
    field_name: str,
) -> BulkCanonicalizationTransforms:
    info = atoms.get("info")
    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    if not isinstance(info, Mapping) or key not in info:
        raise MissingBulkCanonicalizationProvenanceError(
            f"Current structure-backed bulk field {field_name!r} is missing "
            f"required Atoms.info provenance {key!r}."
        )
    try:
        return parse_bulk_canonicalization_transforms(info[key])
    except (TypeError, ValueError) as exc:
        raise InvalidBulkCanonicalizationProvenanceError(
            f"Current structure-backed bulk field {field_name!r} contains "
            "malformed canonicalization provenance."
        ) from exc


def _standardization_projection(
    payload: Mapping[str, Any],
    *,
    provenance: BulkCanonicalizationTransforms,
) -> dict[str, Any]:
    if "standardization" not in payload or payload["standardization"] is None:
        raise MissingBulkCanonicalizationProvenanceError(
            "Current structure-backed bulk payload is missing required "
            "'standardization' provenance."
        )
    raw = payload["standardization"]
    if not isinstance(raw, Mapping):
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection must be a mapping."
        )
    stored = dict(raw)

    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    if "provenance_info_key" not in stored:
        raise MissingBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection is missing 'provenance_info_key'."
        )
    if stored["provenance_info_key"] != key:
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection names an unsupported "
            "Atoms.info provenance key."
        )

    if "provenance" not in stored or stored["provenance"] is None:
        raise MissingBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection is missing 'provenance'."
        )
    if not isinstance(stored["provenance"], Mapping):
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection provenance must be a mapping."
        )
    try:
        projected = parse_bulk_canonicalization_transforms(stored["provenance"])
    except (TypeError, ValueError) as exc:
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection contains malformed provenance."
        ) from exc
    if projected.to_dict() != provenance.to_dict():
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection does not match the "
            "Atoms.info provenance record."
        )

    expected = provenance.to_dict()
    missing = [name for name in _PROJECTION_FIELDS if name not in stored]
    if missing:
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection is missing required field(s): "
            + ", ".join(missing)
            + "."
        )
    mismatched = [name for name in _PROJECTION_FIELDS if stored[name] != expected[name]]
    if mismatched:
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk standardization projection disagrees with provenance "
            "field(s): " + ", ".join(mismatched) + "."
        )
    return stored


def current_bulk_structure_record(
    payload: Mapping[str, Any] | None,
) -> CurrentBulkStructureRecord | None:
    """Validate atomistic current state or return ``None`` for metadata-only state.

    The absence of submitted atoms is the explicit metadata-only boundary.  A
    payload containing any standardized supplemental field without submitted
    atoms is malformed rather than historical or partially recoverable.
    """

    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise CurrentBulkPayloadError(
            "Current persisted bulk payload must be a mapping or None."
        )
    stored = dict(payload)
    if "atoms" not in stored:
        supplemental = sorted(_SUPPLEMENTAL_FIELDS & stored.keys())
        if supplemental:
            raise CurrentBulkPayloadError(
                "Current metadata-only bulk payload must not contain atomistic "
                "supplemental field(s): " + ", ".join(supplemental) + "."
            )
        return None
    submitted = stored["atoms"]
    if submitted is None:
        raise CurrentBulkPayloadError(
            "Current structure-backed bulk field 'atoms' must not be null."
        )

    atoms_submitted = _canonical_atoms(
        "atoms",
        submitted,
        error_type=CurrentBulkPayloadError,
    )
    atoms_conventional = _required_supplemental_atoms(
        stored,
        "atoms_conventional",
    )
    atoms_primitive = _required_supplemental_atoms(
        stored,
        "atoms_primitive",
    )

    conventional_provenance = _atoms_provenance(
        atoms_conventional,
        field_name="atoms_conventional",
    )
    primitive_provenance = _atoms_provenance(
        atoms_primitive,
        field_name="atoms_primitive",
    )
    if primitive_provenance.to_dict() != conventional_provenance.to_dict():
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current conventional and primitive bulk structures carry different "
            "canonicalization provenance records."
        )

    standardization = _standardization_projection(
        stored,
        provenance=conventional_provenance,
    )
    try:
        validate_bulk_canonicalization_relations(
            cell_input_rows=atoms_submitted["cell"],
            cell_conventional_rows=atoms_conventional["cell"],
            cell_primitive_rows=atoms_primitive["cell"],
            numbers_conventional=atoms_conventional["numbers"],
            numbers_primitive=atoms_primitive["numbers"],
            record=conventional_provenance,
        )
    except (TypeError, ValueError) as exc:
        raise InvalidBulkCanonicalizationProvenanceError(
            "Current bulk canonicalization provenance does not verify the "
            "persisted structures."
        ) from exc

    return CurrentBulkStructureRecord(
        atoms_submitted=atoms_submitted,
        atoms_conventional=atoms_conventional,
        atoms_primitive=atoms_primitive,
        standardization=standardization,
        provenance=conventional_provenance,
    )
