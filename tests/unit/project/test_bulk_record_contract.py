"""Exact-current contracts for persisted bulk atomistic state."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from bulk_record_fixtures import current_bulk_payload
from calm.bulk.provenance import (
    CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY,
)
from calm.project.domain.contracts.bulk_record import (
    CurrentBulkPayloadError,
    InvalidBulkCanonicalizationProvenanceError,
    MissingBulkCanonicalizationProvenanceError,
    current_bulk_structure_record,
)
from calm.project.domain.models import Bulk
from current_structure_fixtures import current_atoms_payload


def test_metadata_only_bulk_remains_valid_current_state() -> None:
    assert current_bulk_structure_record(None) is None
    assert current_bulk_structure_record({}) is None
    assert current_bulk_structure_record({"campaign": "metadata-only"}) is None


def test_structure_backed_bulk_requires_and_verifies_one_current_record() -> None:
    record = current_bulk_structure_record(current_bulk_payload())

    assert record is not None
    assert record.provenance.primitive_multiplicity == 4
    assert record.standardization["provenance"] == record.provenance.to_dict()


@pytest.mark.parametrize(
    "missing_field",
    ["atoms_conventional", "atoms_primitive", "standardization"],
)
def test_structure_backed_bulk_rejects_missing_canonicalization_state(
    missing_field: str,
) -> None:
    payload = current_bulk_payload()
    del payload[missing_field]

    with pytest.raises(MissingBulkCanonicalizationProvenanceError):
        current_bulk_structure_record(payload)


def test_structure_backed_bulk_rejects_missing_atoms_info_provenance() -> None:
    payload = current_bulk_payload()
    del payload["atoms_conventional"]["info"]

    with pytest.raises(MissingBulkCanonicalizationProvenanceError):
        current_bulk_structure_record(payload)


def test_structure_backed_bulk_rejects_malformed_present_provenance() -> None:
    payload = current_bulk_payload()
    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    payload["atoms_conventional"]["info"][key] = "not-json"

    with pytest.raises(InvalidBulkCanonicalizationProvenanceError):
        current_bulk_structure_record(payload)


def test_conventional_and_primitive_provenance_must_match() -> None:
    payload = current_bulk_payload()
    key = CALM_BULK_CANONICALIZATION_TRANSFORMS_INFO_KEY
    primitive_record = json.loads(payload["atoms_primitive"]["info"][key])
    primitive_record["spglib_version"] = "different-current-writer"
    payload["atoms_primitive"]["info"][key] = json.dumps(primitive_record)

    with pytest.raises(
        InvalidBulkCanonicalizationProvenanceError,
        match="carry different",
    ):
        current_bulk_structure_record(payload)


def test_standardization_projection_must_match_atoms_info_authority() -> None:
    payload = current_bulk_payload()
    payload["standardization"]["symprec"] = 2e-5

    with pytest.raises(
        InvalidBulkCanonicalizationProvenanceError,
        match="disagrees",
    ):
        current_bulk_structure_record(payload)


def test_provenance_must_verify_the_persisted_cells() -> None:
    payload = current_bulk_payload()
    payload["atoms_primitive"]["cell"][0][0] += 0.25

    with pytest.raises(
        InvalidBulkCanonicalizationProvenanceError,
        match="does not verify",
    ):
        current_bulk_structure_record(payload)


def test_metadata_only_bulk_cannot_carry_partial_atomistic_state() -> None:
    payload = {"atoms_primitive": current_bulk_payload()["atoms_primitive"]}

    with pytest.raises(CurrentBulkPayloadError, match="metadata-only"):
        current_bulk_structure_record(payload)

    with pytest.raises(CurrentBulkPayloadError, match="must not be null"):
        current_bulk_structure_record({"atoms": None})


def test_bulk_model_does_not_fallback_or_synthesize_missing_cells() -> None:
    submitted_only = Bulk(
        uid_full="bulk:v2:submitted-only",
        id_short="b_submitted",
        label="Submitted only",
        payload={"atoms": current_atoms_payload()},
    )
    assert submitted_only.atoms_conventional is None

    conventional_only = Bulk(
        uid_full="bulk:v2:conventional-only",
        id_short="b_conventional",
        label="Conventional only",
        payload={"atoms_conventional": deepcopy(current_atoms_payload())},
    )
    assert conventional_only.atoms_primitive is None
