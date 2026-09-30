"""Exact-current raw, reference, and thermodynamic result contracts."""

from __future__ import annotations

import copy

import pytest

from calm.project.domain.contracts.energy_result import (
    canonical_energy_result_payload,
    energy_result_identity_qualifiers,
)
from energy_result_fixtures import (
    failed_raw_energy_payload,
    raw_energy_payload,
    reference_energy_payload,
    thermodynamic_payload,
)


def _validate_raw(payload, **overrides):
    values = {
        "kind": "energy_stage",
        "status": "done",
        "payload": payload,
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "best_energy": payload.get("energy_eV"),
        "param1": None,
        "param2": None,
        "n_points": payload.get("n_steps"),
    }
    values.update(overrides)
    return canonical_energy_result_payload(**values)


def _validate_reference(payload, **overrides):
    energy = payload.get("energy") or {}
    reference = payload["reference"]
    metadata = reference["metadata"]
    values = {
        "kind": "reference_energy",
        "status": "done",
        "payload": payload,
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "best_energy": energy.get("total_eV"),
        "param1": energy.get("per_formula_unit_eV"),
        "param2": (
            float(metadata["interface_formula_units"])
            if metadata.get("interface_formula_units") is not None
            else None
        ),
        "n_points": energy.get("n_steps"),
    }
    values.update(overrides)
    return canonical_energy_result_payload(**values)


def _validate_thermo(payload, **overrides):
    quantity = payload.get("quantity") or {}
    normalization = payload.get("normalization") or {}
    values = {
        "kind": "thermodynamic_quantity",
        "status": "done",
        "payload": payload,
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:1",
        "target_kind": "interface",
        "best_energy": quantity.get("value_eV_per_A2"),
        "param1": normalization.get("area_A2"),
        "param2": (
            float(normalization["n_interfaces"])
            if normalization.get("n_interfaces") is not None
            else None
        ),
        "n_points": 1,
    }
    values.update(overrides)
    return canonical_energy_result_payload(**values)


def test_raw_energy_result_uses_exact_backend_and_scalar_projections() -> None:
    payload = raw_energy_payload(
        -4.25,
        backend_name="real",
        backend_identity={"name": "real", "calculator": "emt"},
        n_steps=3,
    )

    canonical = _validate_raw(payload)

    assert canonical == payload
    assert canonical["result_stage"] == "energy_evaluated"
    assert canonical["backend"]["identity"]["calculator"] == "emt"
    assert energy_result_identity_qualifiers(
        kind="energy_stage", payload=canonical
    ) == {}

    with pytest.raises(ValueError, match="best_energy"):
        _validate_raw(payload, best_energy=-4.0)
    with pytest.raises(ValueError, match="n_points"):
        _validate_raw(payload, n_points=2)


def test_raw_energy_result_rejects_historical_aliases_and_invalid_targets() -> None:
    payload = raw_energy_payload(-1.0)
    for field, value in (
        ("energy_backend", "real"),
        ("backend_identity", {"name": "real"}),
        ("energy_settings", {"mode": "single_point"}),
        ("target_uid_full", "iface:1"),
    ):
        with pytest.raises(ValueError, match="unsupported or historical"):
            _validate_raw({**payload, field: value})

    with pytest.raises(ValueError, match="target_uid_full to equal"):
        _validate_raw(
            raw_energy_payload(-1.0, interface_area_A2=None),
            target_kind="prototype",
            target_uid_full="proto:other",
        )


def test_failed_energy_results_require_null_scientific_projections() -> None:
    payload = failed_raw_energy_payload()
    canonical = _validate_raw(
        payload,
        status="failed",
        best_energy=None,
        n_points=None,
    )
    assert canonical == payload

    with pytest.raises(ValueError, match="null generic scalar projections"):
        _validate_raw(payload, status="failed", best_energy=0.0, n_points=None)


def test_reference_energy_result_owns_reference_identity_and_normalization() -> None:
    payload = reference_energy_payload(
        reference_uid_full="reference:a",
        reference_kind="strained_bulk_a",
        formula_id="interface_excess_strained_bulk",
        energy_eV=-6.0,
        energy_eV_per_formula_unit=-2.0,
        reference_formula_units=3,
        interface_formula_units=4,
    )

    canonical = _validate_reference(payload)

    assert canonical == payload
    assert energy_result_identity_qualifiers(
        kind="reference_energy", payload=canonical
    ) == {"reference_kind": "strained_bulk_a"}

    tampered = copy.deepcopy(payload)
    tampered["reference"]["metadata"]["target_uid_full"] = "iface:1"
    with pytest.raises(ValueError, match="duplicated identity field"):
        _validate_reference(tampered)

    tampered = copy.deepcopy(payload)
    tampered["energy"]["per_formula_unit_eV"] = -1.5
    with pytest.raises(ValueError, match="does not match total_eV"):
        _validate_reference(tampered, param1=-1.5)


def test_thermodynamic_result_owns_units_source_and_normalization() -> None:
    payload = thermodynamic_payload(
        raw_energy_followup_uid="followup:raw",
        value_eV_per_A2=0.125,
        area_A2=8.0,
        n_interfaces=2,
    )

    canonical = _validate_thermo(payload)

    assert canonical == payload
    assert energy_result_identity_qualifiers(
        kind="thermodynamic_quantity", payload=canonical
    ) == {"raw_energy_followup_uid": "followup:raw"}

    tampered = copy.deepcopy(payload)
    tampered["quantity"]["value_J_per_m2"] += 1.0
    with pytest.raises(ValueError, match="canonical conversion"):
        _validate_thermo(tampered)

    with pytest.raises(ValueError, match="param1"):
        _validate_thermo(payload, param1=9.0)


    tampered = copy.deepcopy(payload)
    tampered["references"]["values"]["bulk_a_eV_per_formula_unit"] = -3.0
    with pytest.raises(ValueError, match="authoritative calculation|does not match"):
        _validate_thermo(tampered)

    tampered = copy.deepcopy(payload)
    tampered["components"]["excess_energy_eV"] += 0.5
    with pytest.raises(ValueError, match="authoritative calculation"):
        _validate_thermo(tampered)

    tampered = copy.deepcopy(payload)
    tampered["references"] = {"bulk_a_eV_per_formula_unit": -1.0}
    with pytest.raises(ValueError, match="status must be"):
        _validate_thermo(tampered)


    tampered = copy.deepcopy(payload)
    tampered["references"]["source_kind"] = "manual"
    tampered["references"]["result_uids"] = {}
    with pytest.raises(ValueError, match="Manual thermodynamic references"):
        _validate_thermo(tampered)


def test_energy_result_rejects_schema_owned_workflow_metadata() -> None:
    payload = raw_energy_payload(
        -1.0,
        workflow_metadata={"energy_settings": {"mode": "single_point"}},
    )

    with pytest.raises(ValueError, match="schema-owned or historical"):
        _validate_raw(payload)


def test_failed_thermodynamic_result_can_record_unresolved_compatibility() -> None:
    completed = thermodynamic_payload(
        raw_energy_followup_uid="followup:raw",
        value_eV_per_A2=0.125,
        area_A2=8.0,
        n_interfaces=2,
    )
    payload = {
        "schema": completed["schema"],
        "version": completed["version"],
        "result_stage": "thermodynamic_failed",
        "source": completed["source"],
        "convention": completed["convention"],
        "references": completed["references"],
        "calculator_compatibility": {
            "status": "unresolved",
            "reason": (
                "thermodynamic_derivation_failed_before_calculator_"
                "compatibility_verification"
            ),
        },
        "normalization_area_source_status": None,
        "failure": {
            "message": "calculator mismatch",
            "exception_type": "ValueError",
            "module": "builtins",
        },
    }

    canonical = _validate_thermo(
        payload,
        status="failed",
        best_energy=None,
        param1=None,
        param2=None,
        n_points=None,
    )
    assert canonical == payload

    completed["calculator_compatibility"] = payload["calculator_compatibility"]
    with pytest.raises(ValueError, match="cannot use unresolved"):
        _validate_thermo(completed)


def test_verified_thermodynamic_calculators_must_match_exactly() -> None:
    payload = thermodynamic_payload(
        raw_energy_followup_uid="followup:raw",
        value_eV_per_A2=0.125,
        area_A2=8.0,
        n_interfaces=2,
    )

    tampered = copy.deepcopy(payload)
    tampered["calculator_compatibility"]["reference"]["settings"] = {
        "mode": "different"
    }
    with pytest.raises(ValueError, match="identical raw and reference"):
        _validate_thermo(tampered)

    tampered = copy.deepcopy(payload)
    tampered["calculator_compatibility"]["reference"][
        "interface_area_A2"
    ] = 9.0
    with pytest.raises(ValueError, match="identical raw and reference interface areas"):
        _validate_thermo(tampered)
