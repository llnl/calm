"""Exact-current strain and registry refinement-result contracts."""

from __future__ import annotations

import copy

import pytest

from calm.project.domain.contracts.refinement_result import (
    canonical_refinement_result_payload,
)
from test_helpers import (
    make_current_registry_result_payload,
    make_current_strain_result_payload,
)


def _validate_strain(payload, **overrides):
    values = {
        "kind": "strain_partition_scan",
        "payload": payload,
        "prototype_uid_full": "proto:1",
        "target_uid_full": "proto:1",
        "target_kind": "prototype",
        "best_energy": payload["selection"]["value"],
        "param1": payload["selection"]["alpha"],
        "param2": None,
        "n_points": len(payload["points"]),
    }
    values.update(overrides)
    return canonical_refinement_result_payload(**values)


def _validate_registry(payload, **overrides):
    shift = payload["registry_shift_frac_a"]
    values = {
        "kind": "registry_search",
        "payload": payload,
        "prototype_uid_full": "proto:1",
        "target_uid_full": "proto:1",
        "target_kind": "prototype",
        "best_energy": payload["score"],
        "param1": shift[0],
        "param2": shift[1],
        "n_points": payload["n_steps"],
    }
    values.update(overrides)
    return canonical_refinement_result_payload(**values)


def test_strain_result_uses_versioned_selection_and_exact_scalar_projections() -> None:
    payload = make_current_strain_result_payload(alpha=0.25, value=0.1)

    canonical = _validate_strain(payload)

    assert canonical == payload
    assert canonical["version"] == 2
    assert canonical["result_stage"] == "strain_partitioned"
    assert canonical["selection"] == {
        "metric": "potential_energy_density_eV_per_A2",
        "alpha": 0.25,
        "value": 0.1,
    }

    with pytest.raises(ValueError, match="best_energy"):
        _validate_strain(payload, best_energy=0.2)
    with pytest.raises(ValueError, match="param1"):
        _validate_strain(payload, param1=0.5)
    with pytest.raises(ValueError, match="n_points"):
        _validate_strain(payload, n_points=2)


def test_strain_result_persists_exact_per_side_geometry() -> None:
    payload = make_current_strain_result_payload(alpha=0.25, value=0.1)

    canonical = _validate_strain(payload)
    point = canonical["points"][0]

    assert point["side_a_principal_log_strains"] == pytest.approx([-0.005, 0.01])
    assert point["side_b_principal_log_strains"] == pytest.approx([-0.03, 0.015])
    assert point["side_a_max_abs_principal_log_strain"] == pytest.approx(0.01)
    assert point["side_b_max_abs_principal_log_strain"] == pytest.approx(0.03)
    assert point["side_a_airm_distance"] + point[
        "side_b_airm_distance"
    ] == pytest.approx(2.0 * (0.02**2 + 0.04**2) ** 0.5)
    assert point["interface_area_A2"] == pytest.approx(point["area_A2"])

    tampered = copy.deepcopy(payload)
    tampered["points"][0]["side_a_max_abs_principal_log_strain"] += 0.01
    with pytest.raises(ValueError, match="side-A maximum principal"):
        _validate_strain(tampered)

    tampered = copy.deepcopy(payload)
    tampered["points"][0]["side_b_airm_distance"] *= 0.5
    with pytest.raises(ValueError, match="side-B AIRM distance"):
        _validate_strain(tampered)

    tampered = copy.deepcopy(payload)
    tampered["points"][0]["interface_area_A2"] = 11.0
    with pytest.raises(ValueError, match="must equal"):
        _validate_strain(tampered)


def test_strain_result_rejects_historical_aliases_and_target_duplicates() -> None:
    payload = make_current_strain_result_payload()

    for field, value in (
        ("target_metric", "potential_energy_density_eV_per_A2"),
        ("target_alpha", 0.25),
        ("target_uid_full", "proto:1"),
        ("target_kind", "prototype"),
    ):
        with pytest.raises(ValueError, match="unsupported or historical"):
            _validate_strain({**payload, field: value})

    with pytest.raises(TypeError, match="version must be an integer"):
        _validate_strain({**payload, "version": 2.0})
    with pytest.raises(ValueError, match="expected 2"):
        _validate_strain({**payload, "version": 1})


def test_registry_result_is_versioned_translation_only_state() -> None:
    payload = make_current_registry_result_payload(n_steps=3, z_padding=2.0)

    canonical = _validate_registry(payload)

    assert canonical == payload
    assert canonical["result_stage"] == "registry_refined"
    assert canonical["z_padding"] == pytest.approx(2.0)
    assert canonical["provenance"]["z_search_enabled"] is False
    assert canonical["trace"][-1]["best_score"] == canonical["score"]


def test_registry_result_rejects_aliases_and_inconsistent_projections() -> None:
    payload = make_current_registry_result_payload()

    for field, value in (
        ("mc", payload["provenance"]),
        ("registry_provenance_status", "complete_v1"),
        ("translation", payload["registry_shift_frac_a"]),
        ("gap", payload["z_padding"]),
        ("target_uid_full", "proto:1"),
    ):
        with pytest.raises(ValueError, match="unsupported or historical"):
            _validate_registry({**payload, field: value})

    with pytest.raises(ValueError, match="param1"):
        _validate_registry(payload, param1=0.9)
    with pytest.raises(ValueError, match="n_points"):
        _validate_registry(payload, n_points=1)


def test_registry_result_requires_exact_current_provenance_fields() -> None:
    payload = make_current_registry_result_payload()
    provenance = copy.deepcopy(payload["provenance"])
    provenance["backend"] = "historical"

    with pytest.raises(ValueError, match="unsupported or historical"):
        _validate_registry({**payload, "provenance": provenance})

    provenance = copy.deepcopy(payload["provenance"])
    provenance["z_search_enabled"] = True
    with pytest.raises(ValueError, match="translation-only"):
        _validate_registry({**payload, "provenance": provenance})

    provenance = copy.deepcopy(payload["provenance"])
    provenance["rng"]["seed_mode"] = "entropy"
    provenance["rng"]["seed"] = None
    with pytest.raises(ValueError, match="explicit reproducible seed"):
        _validate_registry({**payload, "provenance": provenance})

    provenance = copy.deepcopy(payload["provenance"])
    provenance["rng"]["historical_state"] = "opaque"
    with pytest.raises(ValueError, match="unsupported or historical"):
        _validate_registry({**payload, "provenance": provenance})


def test_registry_result_verifies_compact_and_proposal_trace_consistency() -> None:
    payload = make_current_registry_result_payload(n_steps=3)

    tampered = copy.deepcopy(payload)
    tampered["proposal_trace"][-1]["best_score"] += 1.0
    with pytest.raises(ValueError, match="compact trace"):
        _validate_registry(tampered)

    tampered = copy.deepcopy(payload)
    tampered["n_accepted"] -= 1
    with pytest.raises(ValueError, match="accepted proposal count"):
        _validate_registry(tampered)

    tampered = copy.deepcopy(payload)
    tampered["registry_shift_frac_a"] = [0.25, 0.5]
    with pytest.raises(ValueError, match="final proposal best_translation"):
        _validate_registry(
            tampered,
            param1=0.25,
            param2=0.5,
        )


def test_refinement_target_identity_lives_only_in_authoritative_columns() -> None:
    payload = make_current_strain_result_payload()

    with pytest.raises(ValueError, match="equal prototype_uid_full"):
        _validate_strain(payload, target_uid_full="proto:other")
    with pytest.raises(ValueError, match="iface: target UID"):
        _validate_strain(
            payload,
            target_kind="interface",
            target_uid_full="proto:1",
        )

    canonical = _validate_strain(
        payload,
        target_kind="interface",
        target_uid_full="iface:v2:abc",
    )
    assert "target_uid_full" not in canonical
    assert "target_kind" not in canonical
