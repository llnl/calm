from __future__ import annotations

from copy import deepcopy
from random import Random

import pytest

from calm.project.domain.contracts.dataset import (
    dataset_content_fingerprint,
    dataset_group_uid,
    dataset_split_decision,
    dataset_split_name,
    validate_dataset_item_values,
    validate_learning_dataset_collection,
)


def _settings() -> dict:
    return {
        "schema_version": "calm.interface_learning.v1",
        "duplicate_policy": "error",
        "failure_policy": "error",
        "require_complete_provenance": True,
        "features": [
            {
                "name": "steps",
                "source": "relaxation.n_steps",
                "dtype": "int",
                "required": True,
            }
        ],
        "targets": [
            {
                "name": "energy",
                "source": "raw_energy.energy_eV",
                "dtype": "float",
                "required": True,
                "units": "eV",
            }
        ],
        "group_by": ["lineage.prototype"],
        "split": {
            "train_fraction": 0.8,
            "validation_fraction": 0.1,
            "test_fraction": 0.1,
            "seed": 17,
            "policy_version": 2,
        },
    }


def _row(*, source: str = "followup:raw:1", prototype: str = "proto:1") -> dict:
    settings = _settings()
    group_by = {"lineage.prototype": prototype}
    group_id = dataset_group_uid(group_by)
    return {
        "schema_version": "calm.interface_learning.v1",
        "source_kind": "joined_interface_record",
        "source_uid_full": source,
        "terminal_source_kind": "raw_energy",
        "interface_uid_full": "interface:relaxed:1",
        "prototype_uid_full": prototype,
        "relaxation_followup_uid": "followup:relax:1",
        "raw_energy_followup_uid": source,
        "thermodynamic_followup_uid": None,
        "features": {"steps": 5},
        "targets": {"energy": -2.0},
        "group_by": group_by,
        "group_id": group_id,
        "split": dataset_split_name(group_id=group_id, split=settings["split"]),
        "split_provenance": dataset_split_decision(
            group_id=group_id,
            split=settings["split"],
        ).to_dict(),
        "split_contract_status": "complete_v2",
        "provenance": {
            "prototype_uid_full": prototype,
            "relaxed_interface_uid_full": "interface:relaxed:1",
            "relaxation_followup_uid": "followup:relax:1",
            "raw_energy_followup_uid": source,
            "thermodynamic_followup_uid": None,
            "terminal_source_uid_full": source,
            "relaxation": {
                "scientific_authority": "calculator_backed",
                "converged": True,
                "residual_satisfied": True,
            },
            "raw_energy": {
                "scientific_authority": "calculator_backed",
                "energy_eV": -2.0,
            },
            "thermodynamic": None,
        },
        "artifact_refs": ["artifact:2", "artifact:1"],
        "status": "done",
    }


def test_group_and_split_identities_are_order_and_input_order_invariant() -> None:
    left = dataset_group_uid({"b": 2, "a": 1})
    right = dataset_group_uid({"a": 1, "b": 2})
    assert left == right

    split = _settings()["split"]
    assignments = {
        group: dataset_split_name(group_id=group, split=split)
        for group in (dataset_group_uid({"prototype": index}) for index in range(50))
    }
    assert assignments == {
        group: dataset_split_name(group_id=group, split=split)
        for group in reversed(tuple(assignments))
    }
    assert set(assignments.values()) <= {"train", "validation", "test"}


def test_randomized_split_probe_is_reproducible_and_group_preserving() -> None:
    rng = Random(14014)
    groups = [
        dataset_group_uid({"prototype": f"proto:{rng.getrandbits(128):032x}"})
        for _ in range(5000)
    ]
    split = _settings()["split"]
    expected = {
        group: dataset_split_name(group_id=group, split=split)
        for group in groups
    }
    rng.shuffle(groups)
    assert {
        group: dataset_split_name(group_id=group, split=split)
        for group in groups
    } == expected

    counts = {name: tuple(expected.values()).count(name) for name in expected.values()}
    assert abs(counts["train"] / len(expected) - 0.8) < 0.03
    assert abs(counts["validation"] / len(expected) - 0.1) < 0.03
    assert abs(counts["test"] / len(expected) - 0.1) < 0.03


def test_split_requires_integer_seed_and_nonempty_group() -> None:
    split = _settings()["split"]
    with pytest.raises(TypeError, match="seed must be an integer"):
        dataset_split_name(group_id="dataset_group:1", split={**split, "seed": 1.5})
    with pytest.raises(ValueError, match="non-empty string"):
        dataset_split_name(group_id="", split=split)


def test_split_half_open_boundaries_include_degenerate_fractions() -> None:
    group_id = dataset_group_uid({"prototype": "proto:boundary"})
    assert dataset_split_name(
        group_id=group_id,
        split={
            "train_fraction": 1.0,
            "validation_fraction": 0.0,
            "test_fraction": 0.0,
            "seed": 0,
            "policy_version": 2,
        },
    ) == "train"
    assert dataset_split_name(
        group_id=group_id,
        split={
            "train_fraction": 0.0,
            "validation_fraction": 0.0,
            "test_fraction": 1.0,
            "seed": 0,
            "policy_version": 2,
        },
    ) == "test"


def test_learning_item_validation_recomputes_group_split_and_lineage() -> None:
    settings = _settings()
    row = _row()
    assert validate_dataset_item_values(
        row,
        schema=settings["schema_version"],
        settings=settings,
    ) == []

    split_tampered = deepcopy(row)
    split_tampered["split"] = next(
        name
        for name in ("train", "validation", "test")
        if name != row["split"]
    )
    split_messages = validate_dataset_item_values(
        split_tampered,
        schema=settings["schema_version"],
        settings=settings,
    )
    assert any("split" in message for message in split_messages)

    tampered = deepcopy(row)
    tampered["group_by"]["lineage.prototype"] = "proto:other"
    messages = validate_dataset_item_values(
        tampered,
        schema=settings["schema_version"],
        settings=settings,
    )
    assert any("group_id" in message for message in messages)
    assert any("authoritative joined lineage" in message for message in messages)


def test_learning_collection_closes_groups_over_prototype_lineage() -> None:
    first = _row(source="followup:raw:1")
    second = _row(source="followup:raw:2")
    second["raw_energy_followup_uid"] = "followup:raw:2"
    second["provenance"]["raw_energy_followup_uid"] = "followup:raw:2"
    second["provenance"]["terminal_source_uid_full"] = "followup:raw:2"

    second["group_by"] = {"lineage.prototype": "proto:other"}
    second["group_id"] = dataset_group_uid(second["group_by"])
    second["split"] = dataset_split_name(
        group_id=second["group_id"],
        split=_settings()["split"],
    )
    second["split_provenance"] = dataset_split_decision(
        group_id=second["group_id"],
        split=_settings()["split"],
    ).to_dict()

    messages = validate_learning_dataset_collection([first, second])
    assert any("fragmented across groups" in message for message in messages)


def test_learning_collection_rejects_duplicate_raw_lineage() -> None:
    raw = _row(source="followup:raw:1", prototype="proto:1")
    thermodynamic = deepcopy(raw)
    thermodynamic["source_uid_full"] = "followup:thermo:1"
    thermodynamic["terminal_source_kind"] = "thermodynamic_quantity"
    thermodynamic["thermodynamic_followup_uid"] = "followup:thermo:1"
    thermodynamic["provenance"]["thermodynamic_followup_uid"] = (
        "followup:thermo:1"
    )
    thermodynamic["provenance"]["terminal_source_uid_full"] = (
        "followup:thermo:1"
    )

    messages = validate_learning_dataset_collection([raw, thermodynamic])
    assert any("occurs under multiple terminal sources" in item for item in messages)


def test_learning_collection_rejects_mixed_thermodynamic_semantics() -> None:
    first = _row(source="followup:thermo:1", prototype="proto:1")
    second = _row(source="followup:thermo:2", prototype="proto:2")
    for index, row in enumerate((first, second), start=1):
        row["terminal_source_kind"] = "thermodynamic_quantity"
        row["raw_energy_followup_uid"] = f"followup:raw:{index}"
        row["thermodynamic_followup_uid"] = f"followup:thermo:{index}"
        row["provenance"]["raw_energy_followup_uid"] = f"followup:raw:{index}"
        row["provenance"]["thermodynamic_followup_uid"] = (
            f"followup:thermo:{index}"
        )
        row["provenance"]["terminal_source_uid_full"] = (
            f"followup:thermo:{index}"
        )
        row["provenance"]["thermodynamic"] = {
            "quantity": "work_of_adhesion_relaxed",
            "formula_id": "calm.work_of_adhesion_relaxed.v1",
            "n_interfaces": 2,
            "convention": {"sign": "positive_for_adhesion"},
            "units": {"value_J_per_m2": "J/m^2"},
            "reference_source": {"mode": "calculated"},
            "calculator_compatibility": {
                "reference_protocol": "relaxed_cleaved_surfaces.v1"
            },
        }
    second["provenance"]["thermodynamic"]["n_interfaces"] = 1

    messages = validate_learning_dataset_collection([first, second])
    assert any(
        "thermodynamic target semantics differ" in message
        for message in messages
    )


def test_content_fingerprint_is_canonical_and_membership_sensitive() -> None:
    settings = _settings()
    first = _row(source="followup:raw:1", prototype="proto:1")
    second = _row(source="followup:raw:2", prototype="proto:2")
    second["interface_uid_full"] = "interface:relaxed:2"
    second["relaxation_followup_uid"] = "followup:relax:2"
    second["provenance"]["relaxed_interface_uid_full"] = "interface:relaxed:2"
    second["provenance"]["relaxation_followup_uid"] = "followup:relax:2"
    second["provenance"]["raw_energy_followup_uid"] = "followup:raw:2"
    second["provenance"]["terminal_source_uid_full"] = "followup:raw:2"

    first_with_storage = {**first, "dataset_index": 0, "uid_full": "item:1"}
    second_with_storage = {**second, "dataset_index": 1, "uid_full": "item:2"}
    expected = dataset_content_fingerprint(
        schema=settings["schema_version"],
        settings=settings,
        rows=[first_with_storage, second_with_storage],
    )
    reordered = dataset_content_fingerprint(
        schema=settings["schema_version"],
        settings=settings,
        rows=[
            {**second_with_storage, "dataset_index": 0},
            {**first_with_storage, "dataset_index": 1},
        ],
    )
    assert reordered == expected

    changed = deepcopy(second_with_storage)
    changed["targets"]["energy"] = -3.0
    assert dataset_content_fingerprint(
        schema=settings["schema_version"],
        settings=settings,
        rows=[first_with_storage, changed],
    ) != expected
