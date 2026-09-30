"""Exact-current derived-interface persistence contract."""

from __future__ import annotations

import json

import pytest

from calm.project.domain.contracts.derived_interface import canonical_derived_interface_spec
from calm.project.domain.identity_v2 import (
    derived_interface_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import DerivedInterface
from calm.project.infrastructure.db.repos.derived_interfaces import (
    _derived_interface_from_row,
    _derived_interface_spec_json,
)


def _spec(**overrides):
    values = {
        "schema": "calm.derived_interface",
        "version": 1,
        "prototype": "proto:1",
        "stage": "registry_refined",
        "strain_alpha": 0.25,
        "registry_shift_frac_a": [0.125, 0.75],
        "z_padding": 2.0,
        "vacuum": None,
        "params": {"search_name": "screen"},
    }
    values.update(overrides)
    return values


def _uid(spec):
    return persisted_entity_uid_v2(
        "derived_interface",
        derived_interface_identity_payload(
            prototype_uid_full="proto:1",
            spec=spec,
        ),
    )


def test_current_spec_canonicalizes_registry_coordinates() -> None:
    canonical = canonical_derived_interface_spec(
        _spec(registry_shift_frac_a=[1.125, -0.25]),
        prototype_uid_full="proto:1",
    )

    assert canonical["registry_shift_frac_a"] == [0.125, 0.75]
    assert canonical["stage"] == "registry_refined"
    assert canonical["vacuum"] is None


def test_current_spec_rejects_historical_fields_and_hidden_stage() -> None:
    with pytest.raises(ValueError, match="missing required current field"):
        canonical_derived_interface_spec(
            {key: value for key, value in _spec().items() if key != "version"},
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="unsupported or historical"):
        canonical_derived_interface_spec(
            _spec(translation=[0.0, 0.0]),
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="reserved schema field"):
        canonical_derived_interface_spec(
            _spec(params={"refinement_stage": "registry_refined"}),
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="Unsupported derived-interface stage"):
        canonical_derived_interface_spec(
            _spec(stage=" registry_refined"),
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="Unsupported derived-interface spec schema"):
        canonical_derived_interface_spec(
            _spec(schema="calm.interface"),
            prototype_uid_full="proto:1",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("strain_alpha", "0.25"),
        ("z_padding", "2.0"),
        ("vacuum", "10.0"),
    ],
)
def test_current_spec_rejects_coercive_geometry_values(field, value) -> None:
    with pytest.raises(TypeError, match="finite real number"):
        canonical_derived_interface_spec(
            _spec(**{field: value}),
            prototype_uid_full="proto:1",
        )


def test_current_spec_requires_json_native_params() -> None:
    with pytest.raises(TypeError, match="JSON-native"):
        canonical_derived_interface_spec(
            _spec(params={"grid": (1, 2)}),
            prototype_uid_full="proto:1",
        )


def test_current_spec_requires_matching_authoritative_prototype() -> None:
    with pytest.raises(ValueError, match="authoritative prototype_uid_full"):
        canonical_derived_interface_spec(
            _spec(prototype="proto:other"),
            prototype_uid_full="proto:1",
        )


def test_current_atom_artifact_reference_is_exact_and_linked() -> None:
    artifact_uid = "artifact:atoms:1"
    canonical = canonical_derived_interface_spec(
        _spec(
            atoms_artifact_uid=artifact_uid,
            artifact_refs=[
                {
                    "artifact_uid": artifact_uid,
                    "kind": "interface_atoms",
                    "role": "derived_interface_atoms",
                    "uri": "artifacts/interface.json",
                }
            ],
        ),
        prototype_uid_full="proto:1",
    )
    assert canonical["atoms_artifact_uid"] == artifact_uid

    with pytest.raises(ValueError, match="contain exactly"):
        canonical_derived_interface_spec(
            _spec(
                atoms_artifact_uid=artifact_uid,
                artifact_refs=[
                    {
                        "uid_full": artifact_uid,
                        "kind": "interface_atoms",
                    }
                ],
            ),
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="requires an exact current"):
        canonical_derived_interface_spec(
            _spec(atoms_artifact_uid=artifact_uid),
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="requires the exact current"):
        canonical_derived_interface_spec(
            _spec(
                artifact_refs=[
                    {
                        "artifact_uid": artifact_uid,
                        "kind": "interface_atoms",
                        "role": "derived_interface_atoms",
                        "uri": "artifacts/interface.json",
                    }
                ]
            ),
            prototype_uid_full="proto:1",
        )

    with pytest.raises(ValueError, match="exact current interface_atoms"):
        canonical_derived_interface_spec(
            _spec(
                atoms_artifact_uid=artifact_uid,
                artifact_refs=[
                    {
                        "artifact_uid": artifact_uid,
                        "kind": "structure",
                        "role": "derived_interface_atoms",
                        "uri": "artifacts/interface.json",
                    }
                ],
            ),
            prototype_uid_full="proto:1",
        )


def test_domain_model_exposes_only_current_derived_interface_fields() -> None:
    interface = DerivedInterface(
        uid_full="iface:test",
        id_short="i_test",
        prototype_uid_full="proto:1",
        spec=_spec(registry_shift_frac_a=[-0.25, 1.5]),
    )

    assert interface.stage == "registry_refined"
    assert interface.registry_shift_frac_a == (0.75, 0.5)
    assert interface.z_padding == pytest.approx(2.0)
    assert interface.params == {"search_name": "screen"}
    assert not hasattr(interface, "registry_shift_frac_b")
    assert not hasattr(interface, "strain_tensor_a")


def test_repository_serialization_preserves_identity_float_precision() -> None:
    spec = canonical_derived_interface_spec(
        _spec(
            stage="relaxed",
            params={"final_energy_eV": -1.2345678901234567},
        ),
        prototype_uid_full="proto:1",
    )
    uid = _uid(spec)
    spec_json = _derived_interface_spec_json(spec)

    assert json.loads(spec_json)["params"]["final_energy_eV"] == (
        spec["params"]["final_energy_eV"]
    )
    interface = _derived_interface_from_row(
        {
            "uid_full": uid,
            "id_short": "i_test",
            "prototype_uid_full": "proto:1",
            "label": "relaxed",
            "spec_json": spec_json,
            "created_at": None,
            "updated_at": None,
        }
    )

    assert interface.uid_full == uid
    assert interface.spec == spec


def test_repository_hydration_verifies_current_spec_identity() -> None:
    spec = canonical_derived_interface_spec(
        _spec(),
        prototype_uid_full="proto:1",
    )
    uid = _uid(spec)
    row = {
        "uid_full": uid,
        "id_short": "i_test",
        "prototype_uid_full": "proto:1",
        "label": "refined",
        "spec_json": json.dumps(spec),
        "created_at": None,
        "updated_at": None,
    }

    interface = _derived_interface_from_row(row)
    assert interface.uid_full == uid
    assert interface.spec == spec

    with pytest.raises(ValueError, match="identity does not match"):
        _derived_interface_from_row({**row, "uid_full": "iface:tampered"})
