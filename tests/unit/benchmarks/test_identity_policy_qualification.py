from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from benchmarks.benchmarks.claims.claim_ids import ClaimId
from benchmarks.benchmarks.claims.identity_policy import (
    IDENTITY_PAIR_KEY_FULL,
    SIGMA5_PAIR_KEY_FULL,
    IdentityPolicyConfig,
    classify_source_pair,
    full_square_group,
    identity_group,
    run_identity_policy_qualification,
)
from benchmarks.benchmarks.run_identity_policy_qualification import main


I2 = np.eye(2, dtype=int)
SHEAR = np.array([[1, 1], [0, 1]], dtype=int)
REFLECTION = np.array([[1, 0], [0, -1]], dtype=int)
SIGMA5_A = np.array([[2, -1], [1, 2]], dtype=int)
SIGMA5_B = np.array([[2, 1], [-1, 2]], dtype=int)


def _stack(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.vstack([a, b])


def _policy(
    *, symmetry: str = "full", orientation: str = "proper", exchange: bool = False
) -> dict[str, object]:
    return {
        "key_version": 1,
        "pair_symmetry_policy": symmetry,
        "correspondence_orientation": orientation,
        "material_exchange_identified": exchange,
    }


def test_identity_and_sigma5_anchor_keys_remain_distinct() -> None:
    group = full_square_group()
    identity = classify_source_pair(
        _stack(I2, I2),
        policy=_policy(),
        point_group_a=group,
        point_group_b=group,
    )
    sigma5 = classify_source_pair(
        _stack(SIGMA5_A, SIGMA5_B),
        policy=_policy(),
        point_group_a=group,
        point_group_b=group,
    )

    assert tuple(identity["primitive_pair_key"]) == IDENTITY_PAIR_KEY_FULL
    assert tuple(sigma5["primitive_pair_key"]) == SIGMA5_PAIR_KEY_FULL
    assert identity["primitive_pair_key"] != sigma5["primitive_pair_key"]


def test_common_right_relabeling_and_repetition_preserve_identity() -> None:
    group = identity_group()
    source = _stack(I2, SHEAR)
    common_right = np.array([[2, 1], [1, 1]], dtype=int)
    repeat = np.array([[2, 0], [0, 1]], dtype=int)

    baseline = classify_source_pair(
        source,
        policy=_policy(),
        point_group_a=group,
        point_group_b=group,
    )
    relabeled = classify_source_pair(
        source @ common_right,
        policy=_policy(),
        point_group_a=group,
        point_group_b=group,
    )
    repeated = classify_source_pair(
        source @ repeat,
        policy=_policy(),
        point_group_a=group,
        point_group_b=group,
    )

    assert relabeled["primitive_pair_key"] == baseline["primitive_pair_key"]
    assert repeated["primitive_pair_key"] == baseline["primitive_pair_key"]
    assert repeated["repeat_index"] == 2
    assert repeated["primitiveization_verified"] is True


def test_orientation_and_symmetry_policies_change_only_declared_relations() -> None:
    identity = identity_group()
    d4 = full_square_group()
    mirrored = _stack(I2, REFLECTION)

    proper = classify_source_pair(
        mirrored,
        policy=_policy(orientation="proper"),
        point_group_a=identity,
        point_group_b=identity,
    )
    all_orientations = classify_source_pair(
        mirrored,
        policy=_policy(orientation="all"),
        point_group_a=identity,
        point_group_b=identity,
    )
    sigma5 = _stack(SIGMA5_A, SIGMA5_B)
    reflected_sigma5 = _stack(REFLECTION @ SIGMA5_A, SIGMA5_B)
    full_a = classify_source_pair(
        sigma5,
        policy=_policy(symmetry="full", orientation="all"),
        point_group_a=d4,
        point_group_b=d4,
    )
    full_b = classify_source_pair(
        reflected_sigma5,
        policy=_policy(symmetry="full", orientation="all"),
        point_group_a=d4,
        point_group_b=d4,
    )
    proper_a = classify_source_pair(
        sigma5,
        policy=_policy(symmetry="proper", orientation="all"),
        point_group_a=d4,
        point_group_b=d4,
    )
    proper_b = classify_source_pair(
        reflected_sigma5,
        policy=_policy(symmetry="proper", orientation="all"),
        point_group_a=d4,
        point_group_b=d4,
    )

    assert proper["status"] == "orientation_rejected"
    assert all_orientations["status"] == "projected"
    assert full_a["primitive_pair_key"] == full_b["primitive_pair_key"]
    assert proper_a["primitive_pair_key"] != proper_b["primitive_pair_key"]


def test_standard_identity_policy_qualification_passes_both_claims(
    tmp_path: Path,
) -> None:
    artifacts = run_identity_policy_qualification(
        output_root=tmp_path / "identity",
        repository_root=Path(__file__).resolve().parents[3],
        command=("python-test", "identity-policy"),
        config=IdentityPolicyConfig(profile="standard"),
    )

    assert [(result.claim_id.value, result.status.value) for result in artifacts.results] == [
        ("C3", "pass"),
        ("C4", "pass"),
    ]
    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert summary["all_passed"] is True
    assert summary["observation_count"] == 18
    assert summary["identity_policy_observation_count"] == 12
    assert summary["metamorphic_observation_count"] == 6
    assert artifacts.identity_observations.is_file()
    assert artifacts.metamorphic_observations.is_file()
    assert artifacts.summary_csv.is_file()
    assert len(artifacts.claim_result_paths) == 2


def test_cli_can_run_only_c4_smoke_profile(tmp_path: Path, capsys) -> None:
    outdir = tmp_path / "c4"

    assert main(
        [
            "--outdir",
            str(outdir),
            "--profile",
            "smoke",
            "--claim",
            "C4",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "C4 status: pass" in output
    summary = json.loads(
        (outdir / "identity_policy_summary.json").read_text(encoding="utf-8")
    )
    assert summary["selected_claims"] == ["C4"]
    assert summary["observation_count"] == 6
