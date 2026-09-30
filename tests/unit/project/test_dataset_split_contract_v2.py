from __future__ import annotations

from copy import deepcopy

import pytest

import calm.project.domain.contracts.dataset as contract
from calm.public.inputs.settings import DatasetSplitSettings


def _split(*, seed: int = 17) -> dict[str, object]:
    return {
        "train_fraction": 0.8,
        "validation_fraction": 0.1,
        "test_fraction": 0.1,
        "seed": seed,
        "policy_version": 2,
    }


def test_settings_accept_only_the_current_versioned_policy() -> None:
    current = DatasetSplitSettings()
    assert current.policy_version == 2
    assert current.to_dict()["policy_version"] == 2

    with pytest.raises(ValueError, match="declare policy_version=2"):
        DatasetSplitSettings.from_value(
            {
                "train_fraction": 0.8,
                "validation_fraction": 0.1,
                "test_fraction": 0.1,
                "seed": 0,
            }
        )
    with pytest.raises(ValueError, match="must equal 2"):
        DatasetSplitSettings(policy_version=1).validate()
    with pytest.raises(ValueError, match="must equal 2"):
        DatasetSplitSettings(policy_version=3).validate()


def test_v2_golden_hash_bytes_and_assignment_are_reconstructible() -> None:
    group_id = contract.dataset_group_uid(
        {"lineage.prototype": "proto:alpha"}
    )
    decision = contract.dataset_split_decision(
        group_id=group_id,
        split=_split(),
    )
    payload = decision.to_dict()

    assert group_id == (
        "dataset_group:"
        "a3139762a011afe4c83abb73470ed8ae091fc08bba44d394b3f1421c354b73c3"
    )
    assert payload["input_bytes_hex"] == (
        "31373a646174617365745f67726f75703a"
        "6133313339373632613031316166653463383361626237333437306564386165"
        "3039316663303862626134346433393462336631343231633335346237336333"
    )
    assert payload["sha256_hex"] == (
        "03d47fec6c272bc0a434abe9a6c8319f99c367879fe63cda27189d2f42449817"
    )
    assert payload["hash_prefix_hex"] == "03d47fec6c272bc0"
    assert payload["hash_prefix_u64"] == "275986130579958720"
    assert payload["unit_coordinate_hex"] == "0x1.ea3ff6361395ep-7"
    assert payload["split"] == "train"
    assert payload["policy_version"] == 2


def test_v2_exact_boundary_comparison_uses_half_open_intervals() -> None:
    lower_train = 2**63 - 1
    train_boundary = 2**63
    lower_test = 3 * 2**62 - 1
    test_boundary = 3 * 2**62

    kwargs = {"train_fraction": 0.5, "validation_fraction": 0.25}
    assert contract._dataset_split_name_from_prefix_u64(
        lower_train,
        **kwargs,
    ) == "train"
    assert contract._dataset_split_name_from_prefix_u64(
        train_boundary,
        **kwargs,
    ) == "validation"
    assert contract._dataset_split_name_from_prefix_u64(
        lower_test,
        **kwargs,
    ) == "validation"
    assert contract._dataset_split_name_from_prefix_u64(
        test_boundary,
        **kwargs,
    ) == "test"


def test_v2_randomized_probe_is_reproducible_and_group_preserving() -> None:
    groups = [
        contract.dataset_group_uid({"prototype": f"proto:{index:08d}"})
        for index in range(5000)
    ]
    split = _split(seed=29)
    forward = {
        group_id: contract.dataset_split_name(group_id=group_id, split=split)
        for group_id in groups
    }
    reverse = {
        group_id: contract.dataset_split_name(group_id=group_id, split=split)
        for group_id in reversed(groups)
    }
    assert forward == reverse
    counts = {
        name: tuple(forward.values()).count(name)
        for name in ("train", "validation", "test")
    }
    assert abs(counts["train"] / len(groups) - 0.8) < 0.03
    assert abs(counts["validation"] / len(groups) - 0.1) < 0.03
    assert abs(counts["test"] / len(groups) - 0.1) < 0.03


def test_seed_and_utf8_group_bytes_are_frozen() -> None:
    group_id = "dataset_group:alpha/β"
    assert contract.dataset_split_input_bytes(
        seed=-7,
        group_id=group_id,
    ) == b"-7:dataset_group:alpha/\xce\xb2"

    first = contract.dataset_split_decision(
        group_id=group_id,
        split=_split(seed=-7),
    )
    second = contract.dataset_split_decision(
        group_id=group_id,
        split=_split(seed=-6),
    )
    assert first.sha256_hex != second.sha256_hex


def test_split_provenance_is_complete_or_invalid() -> None:
    group_id = contract.dataset_group_uid({"prototype": "proto:1"})
    split = _split()
    provenance = contract.dataset_split_decision(
        group_id=group_id,
        split=split,
    ).to_dict()

    assert contract.dataset_split_provenance_status(
        provenance,
        group_id=group_id,
        split=split,
    ) == "complete_v2"
    assert contract.dataset_split_provenance_status(
        None,
        group_id=group_id,
        split=split,
    ) == "invalid"

    tampered = deepcopy(provenance)
    tampered["hash_prefix_hex"] = "0000000000000000"
    assert contract.dataset_split_provenance_status(
        tampered,
        group_id=group_id,
        split=split,
    ) == "invalid"


def test_split_contract_declares_group_scope_and_half_open_intervals() -> None:
    payload = contract.dataset_split_contract()
    assert payload["policy_version"] == 2
    assert payload["comparison_policy"] == (
        "exact_u64_ratio_vs_binary64_threshold_ratios"
    )
    assert payload["assignment_scope"] == "whole_leakage_control_group"
    assert payload["prototype_closure_required"] is True
    assert payload["intervals"] == {
        "train": "[0, train_fraction)",
        "validation": (
            "[train_fraction, train_fraction + validation_fraction)"
        ),
        "test": "[train_fraction + validation_fraction, 1)",
    }


def test_split_fractions_reject_coercive_values() -> None:
    for value in (True, "0.8"):
        split = _split()
        split["train_fraction"] = value
        with pytest.raises(TypeError, match="fractions must be real numbers"):
            contract.dataset_split_decision(
                group_id="dataset_group:test",
                split=split,
            )
        with pytest.raises(TypeError, match="fractions must be real numbers"):
            DatasetSplitSettings(train_fraction=value).validate()  # type: ignore[arg-type]


def test_dataset_schema_requires_an_exact_current_identifier() -> None:
    assert contract.canonical_dataset_schema("calm.interface.v1") == (
        "calm.interface.v1"
    )
    for value in ("interface", " calm.interface.v1", "calm.interface.v1 "):
        with pytest.raises(ValueError):
            contract.canonical_dataset_schema(value)
    with pytest.raises(TypeError, match="must be a string"):
        contract.canonical_dataset_schema(1)  # type: ignore[arg-type]


def test_dataset_item_fingerprint_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError, match="payload keys must be strings"):
        contract.canonical_dataset_item_payload({1: "value"})
