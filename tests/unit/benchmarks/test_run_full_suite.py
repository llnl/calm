from __future__ import annotations

import sys
from pathlib import Path

from benchmarks.benchmarks.run_full_suite import (
    BENCHMARK_TEST_TARGETS,
    build_stage_plan,
    main,
)


def test_default_plan_runs_all_five_qualification_layers(tmp_path: Path) -> None:
    plan = build_stage_plan(
        outdir=tmp_path,
        python_executable="python-test",
    )

    assert [stage.name for stage in plan] == [
        "benchmark contract tests",
        "CALM versus pymatgen ZSL",
        "four-case coupled qualification",
        "equal-square K=5 and K=30 oracle",
        "project-centered public API qualification",
    ]
    assert plan[0].command == (
        "python-test",
        "-m",
        "pytest",
        "-q",
        *BENCHMARK_TEST_TARGETS,
    )
    assert plan[1].command[:3] == (
        "python-test",
        "-m",
        "benchmarks.run_all",
    )
    assert str(tmp_path.resolve() / "cross_tool") in plan[1].command
    assert plan[2].command[-2:] == ("--k-max", "5")
    assert plan[3].command[-5:] == (
        "--k-max",
        "5",
        "--k-max",
        "30",
        "--measure-memory",
    )
    assert plan[4].command[-1] == "--reset"


def test_plan_supports_explicit_stage_skips(tmp_path: Path) -> None:
    plan = build_stage_plan(
        outdir=tmp_path,
        include_tests=False,
        include_cross_tool=False,
        include_smoke=False,
        include_square_oracle=True,
        include_public_api=False,
        measure_memory=False,
    )

    assert [stage.name for stage in plan] == [
        "equal-square K=5 and K=30 oracle"
    ]
    assert "--measure-memory" not in plan[0].command


def test_dry_run_prints_commands_without_execution(
    tmp_path: Path,
    capsys,
) -> None:
    assert main(
        [
            "--outdir",
            str(tmp_path),
            "--dry-run",
            "--skip-tests",
            "--skip-cross-tool",
            "--skip-smoke",
            "--skip-public-api",
        ]
    ) == 0

    output = capsys.readouterr().out
    assert sys.executable in output
    assert "benchmarks.run_coupled_qualification" in output
    assert "--case equal_square" in output
    assert "Dry run complete" in output
