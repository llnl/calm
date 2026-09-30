from __future__ import annotations

from copy import deepcopy

import pytest

from calm.project.domain.contracts.slab_record import (
    SLAB_RECORD_SCHEMA,
    SLAB_RECORD_VERSION,
    canonical_miller,
    canonical_slab_record_payload,
)
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from slab_record_fixtures import (
    current_atoms,
    current_slab_payload,
    current_termination_identity,
)


def test_spec_only_slab_record_has_one_exact_current_shape() -> None:
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        miller=(1, 1, 0),
        params={"layers": 4},
        user_payload={"campaign": "test"},
    )

    assert payload == {
        "schema": SLAB_RECORD_SCHEMA,
        "version": SLAB_RECORD_VERSION,
        "params": {"layers": 4},
        "user_payload": {"campaign": "test"},
        "termination": {
            "label": None,
            "shift": 0,
            "top": None,
            "bottom": None,
            "identity": None,
        },
        "structure": {
            "atoms": None,
            "n_atoms": None,
            "area_A2": None,
            "formula": None,
            "slab_thickness_A": None,
            "vacuum_A": None,
            "layers": None,
            "characterization": None,
        },
    }


def test_materialized_slab_record_verifies_atom_count_and_area() -> None:
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        atoms=current_atoms(),
    )

    assert payload["structure"]["n_atoms"] == 1
    assert payload["structure"]["area_A2"] == pytest.approx(1.0)

    wrong_count = deepcopy(payload)
    wrong_count["structure"]["n_atoms"] = 2
    with pytest.raises(ValueError, match="does not match atoms.numbers"):
        canonical_slab_record_payload(
            wrong_count,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )

    wrong_area = deepcopy(payload)
    wrong_area["structure"]["area_A2"] = 2.0
    with pytest.raises(ValueError, match="does not match the atomistic cell"):
        canonical_slab_record_payload(
            wrong_area,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_materialized_current_slab_requires_complete_transform_provenance() -> None:
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        atoms=current_atoms(),
    )

    missing = deepcopy(payload)
    missing["structure"]["atoms"]["info"].pop(
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY
    )
    with pytest.raises(ValueError, match="missing required.*provenance"):
        canonical_slab_record_payload(
            missing,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )

    incomplete = deepcopy(payload)
    incomplete["structure"]["atoms"]["info"][
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY
    ].pop("construction_controls")
    with pytest.raises(ValueError, match="construction_controls provenance"):
        canonical_slab_record_payload(
            incomplete,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )

    malformed = deepcopy(payload)
    malformed["structure"]["atoms"]["info"][
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY
    ]["construction_controls"] = {}
    with pytest.raises(ValueError, match="must not be empty"):
        canonical_slab_record_payload(
            malformed,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_materialized_current_slab_rejects_left_handed_cell() -> None:
    atoms = current_atoms()
    atoms["cell"][1] = [-value for value in atoms["cell"][1]]
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        atoms=None,
    )
    payload["structure"].update(
        {"atoms": atoms, "n_atoms": 1, "area_A2": 1.0}
    )

    with pytest.raises(ValueError, match="right-handed.*must be positive"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_positive_vacuum_slab_requires_interface_ready_cell_and_provenance() -> None:
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        atoms=current_atoms(interface_ready=True),
        vacuum_A=10.0,
    )

    assert payload["structure"]["vacuum_A"] == pytest.approx(10.0)

    tilted = deepcopy(payload)
    tilted["structure"]["atoms"]["cell"][2][:2] = [0.25, -0.5]
    with pytest.raises(ValueError, match="not interface-ready"):
        canonical_slab_record_payload(
            tilted,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )

    missing_policy = deepcopy(payload)
    missing_policy["structure"]["atoms"]["info"][
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY
    ]["vacuum_info"].pop("cell_policy")
    with pytest.raises(ValueError, match="current interface-ready cell policy"):
        canonical_slab_record_payload(
            missing_policy,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )

    false_strain_provenance = deepcopy(payload)
    false_strain_provenance["structure"]["atoms"]["info"][
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY
    ]["vacuum_info"]["canonicalization_applies_physical_strain"] = True
    with pytest.raises(ValueError, match="must not be recorded as a physical strain"):
        canonical_slab_record_payload(
            false_strain_provenance,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_materialized_slab_requires_positive_in_plane_area() -> None:
    atoms = current_atoms()
    atoms["cell"][1] = list(atoms["cell"][0])
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        atoms=None,
    )
    payload["structure"].update(
        {"atoms": atoms, "n_atoms": 1, "area_A2": 0.0}
    )

    with pytest.raises(ValueError, match="must be positive"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_current_slab_record_rejects_historical_flat_aliases() -> None:
    payload = current_slab_payload(bulk_uid_full="bulk:v2:test")
    payload["termination_shift"] = 1

    with pytest.raises(ValueError, match="unsupported or historical"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


@pytest.mark.parametrize(
    "reserved",
    [
        "bulk_uid_full",
        "miller",
        "atoms",
        "termination_label",
        "surface_area",
        "natoms",
        "polar",
    ],
)
def test_user_payload_cannot_smuggle_scientific_slab_state(
    reserved: str,
) -> None:
    payload = current_slab_payload(bulk_uid_full="bulk:v2:test")
    payload["user_payload"][reserved] = "detached-value"

    with pytest.raises(ValueError, match="reserved scientific field"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_versioned_termination_requires_complete_oriented_identity() -> None:
    identity = current_termination_identity("top")
    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        label="A",
        top="A",
        bottom="B",
        identity=identity,
    )
    assert payload["termination"]["identity"]["version"] == 2

    missing_bottom = deepcopy(payload)
    missing_bottom["termination"]["bottom"] = None
    with pytest.raises(ValueError, match="requires label, top, and bottom"):
        canonical_slab_record_payload(
            missing_bottom,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_current_termination_stacking_translation_is_in_plane() -> None:
    identity = current_termination_identity("top")
    assert identity["stacking_translation_frac"] == [0.0, 0.0]

    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        label="A",
        top="A",
        bottom="B",
        identity=identity,
    )
    assert payload["termination"]["identity"][
        "stacking_translation_frac"
    ] == [0.0, 0.0]

    wrong_dimension = deepcopy(payload)
    wrong_dimension["termination"]["identity"][
        "stacking_translation_frac"
    ] = [0.0, 0.0, 0.0]
    with pytest.raises(ValueError, match="must contain two values"):
        canonical_slab_record_payload(
            wrong_dimension,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_current_termination_metadata_is_complete_and_pair_verified() -> None:
    payload = current_slab_payload(bulk_uid_full="bulk:v2:test")
    payload["termination"]["label"] = "A"
    with pytest.raises(ValueError, match="label, top, and bottom together"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )

    payload = current_slab_payload(
        bulk_uid_full="bulk:v2:test",
        label="A",
        top="A",
        bottom="B",
        identity=current_termination_identity("top"),
    )
    payload["termination"]["identity"]["pair"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="pair digest"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_spec_only_slab_rejects_realized_structure_summaries() -> None:
    payload = current_slab_payload(bulk_uid_full="bulk:v2:test")
    payload["structure"]["formula"] = "A"
    with pytest.raises(ValueError, match="Spec-only slabs"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="bulk:v2:test",
            miller=(1, 0, 0),
        )


def test_slab_parent_and_miller_projections_are_exact() -> None:
    payload = current_slab_payload(bulk_uid_full="bulk:v2:test")

    with pytest.raises(TypeError, match="bulk_uid_full"):
        canonical_slab_record_payload(
            payload,
            bulk_uid_full="",
            miller=(1, 0, 0),
        )
    with pytest.raises(ValueError, match="cannot be"):
        canonical_miller((0, 0, 0))
    with pytest.raises(ValueError, match="exactly three"):
        canonical_miller((1, 0))
    with pytest.raises(TypeError, match="exact integer"):
        canonical_miller((True, 0, 1))
