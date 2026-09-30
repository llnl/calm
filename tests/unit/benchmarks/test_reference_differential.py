from __future__ import annotations

import ast
import json
from pathlib import Path

from benchmarks.benchmarks.claims.claim_ids import ClaimStatus
from benchmarks.benchmarks.claims.differential_search import (
    REFERENCE_DIFFERENTIAL_SUMMARY_SCHEMA,
    ReferenceDifferentialConfig,
    default_differential_fixtures,
    run_reference_differential_qualification,
    select_differential_fixtures,
)
from benchmarks.benchmarks.claims.reference.coupled_match_reference import (
    enumerate_metric_point_group,
    exhaustive_reference_search,
    metric2,
)
from benchmarks.benchmarks.run_reference_differential import main


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REFERENCE_MODULE = (
    REPOSITORY_ROOT
    / "benchmarks"
    / "benchmarks"
    / "claims"
    / "reference"
    / "coupled_match_reference.py"
)


def _top_level_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_exact_reference_is_independent_of_production_and_numpy() -> None:
    imported = _top_level_import_roots(REFERENCE_MODULE)
    assert "calm" not in imported
    assert "numpy" not in imported


def test_exact_metric_point_groups_have_expected_orders() -> None:
    assert len(enumerate_metric_point_group(metric2(((1, 0), (0, 1))))) == 8
    assert len(enumerate_metric_point_group(metric2(((4, 0), (0, 1))))) == 4
    assert (
        len(
            enumerate_metric_point_group(
                metric2(((1, "1/2"), ("1/2", 1)))
            )
        )
        == 12
    )
    assert len(enumerate_metric_point_group(metric2(((5, 1), (1, 3))))) == 2


def test_exact_square_reference_recovers_identity_and_sigma5_through_k5() -> None:
    result = exhaustive_reference_search(
        metric2(((1, 0), (0, 1))),
        metric2(((1, 0), (0, 1))),
        k_max=5,
    )

    assert result.keys == {
        (-1, 0, 0, -1, 1, 0, 0, 1),
        (-4, -3, -3, -1, 5, 3, 0, 1),
    }
    by_key = {item.key: item for item in result.classes}
    assert by_key[(-4, -3, -3, -1, 5, 3, 0, 1)].first_discovery_index == 5


def test_standard_fixture_matrix_is_deterministic_and_structurally_broad() -> None:
    fixtures = default_differential_fixtures()
    fixture_ids = [fixture.fixture_id for fixture in fixtures]

    assert len(fixtures) == 15
    assert len(set(fixture_ids)) == len(fixtures)
    assert {
        "square",
        "rectangular",
        "hexagonal",
        "oblique",
        "near_square",
        "near_hexagonal",
    } <= {fixture.family for fixture in fixtures}
    assert all(len(fixture.sha256()) == 64 for fixture in fixtures)
    assert [fixture.fixture_id for fixture in fixtures] == fixture_ids


def test_smoke_selection_is_explicit_and_stable() -> None:
    selected = select_differential_fixtures(
        ReferenceDifferentialConfig(profile="smoke", k_max_override=2)
    )
    assert [fixture.fixture_id for fixture in selected] == [
        "square_standard",
        "rectangular_standard",
        "hexagonal_standard",
        "oblique_standard",
    ]


def test_reference_differential_smoke_qualifies_exact_inventory(tmp_path: Path) -> None:
    artifacts = run_reference_differential_qualification(
        output_root=tmp_path / "C2",
        repository_root=REPOSITORY_ROOT,
        command=("python-test", "reference-differential"),
        config=ReferenceDifferentialConfig(
            profile="smoke",
            k_max_override=2,
        ),
    )

    assert artifacts.result.status is ClaimStatus.PASS
    assert artifacts.manifest.is_file()
    assert artifacts.claim_result.is_file()
    assert artifacts.comparisons.is_file()
    assert artifacts.fixture_results.is_file()
    summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert summary["schema"] == REFERENCE_DIFFERENTIAL_SUMMARY_SCHEMA
    assert summary["fixture_count"] == 4
    assert summary["exact_match_count"] == 4
    assert summary["all_exact"] is True
    assert all(row["exact_match"] for row in summary["fixtures"])


def test_reference_differential_cli_supports_direct_fixture_selection(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "selected"
    assert main(
        [
            "--outdir",
            str(output),
            "--fixture",
            "square_standard",
            "--k-max",
            "2",
        ]
    ) == 0
    assert "C2 status: pass" in capsys.readouterr().out
    summary = json.loads(
        (output / "reference_differential_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert summary["fixture_count"] == 1
    assert summary["fixtures"][0]["fixture_id"] == "square_standard"
