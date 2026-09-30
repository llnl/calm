from dataclasses import dataclass

import pytest

from calm.public.projections.stage import (
    expose_public_stage_targets,
    normalize_stage_results,
)


@dataclass
class _EnergyResult:
    target_uid: str
    target_kind: str
    prototype_uid: str
    status: str
    run_uid: str
    followup_uid: str
    energy: float
    energy_units: str
    artifact_refs: tuple[str, ...]


def test_typed_stage_result_preserves_stage_specific_fields() -> None:
    rows = normalize_stage_results(
        [
            _EnergyResult(
                target_uid="iface:1",
                target_kind="interface",
                prototype_uid="proto:1",
                status="completed",
                run_uid="run:1",
                followup_uid="followup:1",
                energy=-2.5,
                energy_units="eV",
                artifact_refs=("artifact:1",),
            )
        ]
    )

    assert rows == [
        {
            "target_uid": "iface:1",
            "target_kind": "interface",
            "prototype_uid": "proto:1",
            "status": "completed",
            "run_uid": "run:1",
            "followup_uid": "followup:1",
            "energy": -2.5,
            "energy_units": "eV",
            "artifact_refs": ["artifact:1"],
            "derived_interface_uid": None,
            "relaxed_interface_uid": None,
            "reason": None,
        }
    ]


def test_mapping_stage_result_accepts_the_current_field_names() -> None:
    rows = normalize_stage_results(
        [
            {
                "prototype_uid": "proto:1",
                "target_uid": "iface:1",
                "target_kind": "interface",
                "status": "done",
                "run_uid": 7,
            }
        ]
    )

    assert rows[0]["prototype_uid"] == "proto:1"
    assert rows[0]["target_uid"] == "iface:1"
    assert rows[0]["target_kind"] == "interface"
    assert rows[0]["status"] == "done"
    assert rows[0]["run_uid"] == "7"


def test_redundant_prototype_target_and_null_stage_fields_are_omitted() -> None:
    rows = normalize_stage_results(
        [
            {
                "prototype_uid": "proto:1",
                "target_uid": "proto:1",
                "target_kind": "prototype",
                "status": "skipped",
                "run_uid": "run:1",
                "energy": None,
                "energy_units": None,
            }
        ]
    )

    assert rows == [
        {
            "prototype_uid": "proto:1",
            "status": "skipped",
            "run_uid": "run:1",
            "followup_uid": None,
            "derived_interface_uid": None,
            "relaxed_interface_uid": None,
            "artifact_refs": None,
            "reason": None,
        }
    ]


def test_stage_result_rejects_arbitrary_objects_and_missing_status() -> None:
    with pytest.raises(TypeError, match="dataclass instances or mappings"):
        normalize_stage_results([object()])

    with pytest.raises(ValueError, match="must define prototype_uid"):
        normalize_stage_results([{"prototype": "proto:1", "status": "done"}])

    with pytest.raises(ValueError, match="must define status"):
        normalize_stage_results([{"prototype_uid": "proto:1"}])


def test_public_projection_restores_explicit_prototype_target_identity() -> None:
    compact = normalize_stage_results(
        [
            {
                "prototype_uid": "proto:1",
                "target_uid": "proto:1",
                "target_kind": "prototype",
                "status": "skipped",
                "run_uid": "run:1",
            }
        ]
    )

    assert "target_uid" not in compact[0]
    assert expose_public_stage_targets(compact)[0] == {
        **compact[0],
        "target_uid": "proto:1",
        "target_kind": "prototype",
    }
