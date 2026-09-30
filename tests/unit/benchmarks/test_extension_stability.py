from __future__ import annotations

import json
from pathlib import Path

from benchmarks.benchmarks.claims.extension_stability import (
    ExtensionStabilityConfig,
    compare_extension_snapshots,
    run_extension_stability_qualification,
    select_extension_fixtures,
)
from benchmarks.benchmarks.claims.schemas import (
    SEARCH_EXTENSION_SNAPSHOT_SCHEMA,
    SEARCH_EXTENSION_TRANSITION_SCHEMA,
)
from benchmarks.benchmarks.run_extension_stability_qualification import main


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _inventory_row(
    *,
    key: tuple[int, ...],
    identity_sha256: str = "a" * 64,
    source_count: int = 1,
    source_pairs: tuple[tuple[int, int], ...] = ((1, 1),),
    repeats: tuple[int, ...] = (1,),
    first_discovery: int = 1,
) -> dict[str, object]:
    key_text = json.dumps(list(key), separators=(",", ":"))
    return {
        "pair_key": list(key),
        "pair_key_text": key_text,
        "identity_sha256": identity_sha256,
        "source_count": source_count,
        "source_index_pairs": [list(pair) for pair in source_pairs],
        "repeat_indices": list(repeats),
        "first_discovery_index": first_discovery,
    }


def _snapshot(
    *,
    k_max: int,
    rows: list[dict[str, object]],
    audit_value: int,
) -> dict[str, object]:
    return {
        "schema": SEARCH_EXTENSION_SNAPSHOT_SCHEMA,
        "fixture_id": "synthetic",
        "k_max": k_max,
        "implementation": "primitive_coupled_pair_v2",
        "inventory": rows,
        "audit_totals": {"pairs_candidates_admitted": audit_value},
    }


def test_extension_fixture_profiles_are_deterministic() -> None:
    smoke = select_extension_fixtures(
        ExtensionStabilityConfig(profile="smoke", workers=1)
    )
    standard = select_extension_fixtures(
        ExtensionStabilityConfig(profile="standard", workers=1)
    )

    assert [fixture.fixture_id for fixture, _ in smoke] == [
        "square_standard",
        "rectangular_standard",
        "hexagonal_standard",
        "oblique_standard",
    ]
    assert dict((fixture.fixture_id, k_max) for fixture, k_max in smoke) == {
        "square_standard": 5,
        "rectangular_standard": 3,
        "hexagonal_standard": 3,
        "oblique_standard": 3,
    }
    assert dict((fixture.fixture_id, k_max) for fixture, k_max in standard) == {
        "square_standard": 30,
        "rectangular_standard": 8,
        "hexagonal_standard": 8,
        "oblique_standard": 8,
    }


def test_transition_comparison_detects_identity_and_provenance_regressions() -> None:
    key = (-1, 0, 0, -1, 1, 0, 0, 1)
    previous = _snapshot(
        k_max=1,
        rows=[_inventory_row(key=key, source_count=3)],
        audit_value=3,
    )
    current = _snapshot(
        k_max=2,
        rows=[
            _inventory_row(
                key=key,
                identity_sha256="b" * 64,
                source_count=2,
                source_pairs=((2, 2),),
                repeats=(2,),
                first_discovery=2,
            )
        ],
        audit_value=2,
    )

    transition = compare_extension_snapshots(previous, current)

    assert transition.schema == SEARCH_EXTENSION_TRANSITION_SCHEMA
    assert transition.passed is False
    assert transition.checks["inventory_monotone"] is True
    assert transition.checks["identity_payload_stable"] is False
    assert transition.checks["source_count_nondecreasing"] is False
    assert transition.checks["source_index_pairs_monotone"] is False
    assert transition.checks["repeat_indices_monotone"] is False
    assert transition.checks["first_discovery_stable"] is False
    assert transition.checks["audit_totals_nondecreasing"] is False
    assert transition.violations


def test_smoke_extension_qualification_passes_and_finds_sigma5(
    tmp_path: Path,
) -> None:
    artifacts = run_extension_stability_qualification(
        output_root=tmp_path / "C5",
        repository_root=REPOSITORY_ROOT,
        command=("python-test", "extension-smoke"),
        config=ExtensionStabilityConfig(profile="smoke", workers=1),
    )

    assert artifacts.result.status.value == "pass"
    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert summary["all_passed"] is True
    assert summary["fixture_count"] == 4
    by_fixture = {row["fixture_id"]: row for row in summary["fixtures"]}
    assert by_fixture["square_standard"]["max_k"] == 5
    assert by_fixture["square_standard"]["final_class_count"] == 2
    assert by_fixture["square_standard"]["introduction_indices"] == "[1,5]"

    transitions = [
        json.loads(line)
        for line in artifacts.transitions.read_text(encoding="utf-8").splitlines()
    ]
    sigma5_transition = next(
        row
        for row in transitions
        if row["fixture_id"] == "square_standard" and row["current_k_max"] == 5
    )
    assert sigma5_transition["passed"] is True
    assert sigma5_transition["new_keys"] == ["[-4,-3,-3,-1,5,3,0,1]"]


def test_extension_runner_module_contract(tmp_path: Path, capsys) -> None:
    outdir = tmp_path / "runner"
    assert main(
        [
            "--outdir",
            str(outdir),
            "--profile",
            "smoke",
            "--fixture",
            "square_standard",
            "--k-max",
            "2",
            "--workers",
            "1",
        ]
    ) == 0
    assert "C5 status: pass" in capsys.readouterr().out
    assert (outdir / "search_extension_summary.json").is_file()
