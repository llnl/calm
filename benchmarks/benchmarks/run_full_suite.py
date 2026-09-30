"""Run the complete modern CALM benchmark and qualification suite.

This is the repository-level orchestration entry point.  It runs benchmark
contract tests, the CALM-versus-pymatgen ZSL comparison, the synthetic coupled
qualification matrix, the frozen equal-square oracle through ``K=30``, and the
project-centered public API qualification.

Usage
-----

.. code-block:: bash

    python -m benchmarks.run_full_suite --outdir bench_out

The command stops at the first failing stage and returns that stage's exit code.
Use ``--dry-run`` to print the exact commands without executing them.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_TEST_TARGETS = (
    "tests/unit/benchmarks",
    "tests/repository/test_public_api_qualification_contract.py",
    "tests/repository/test_benchmark_documentation_contract.py",
    "tests/repository/test_performance_qualification_contract.py",
    "tests/repository/test_legacy_benchmark_contract.py",
)


@dataclass(frozen=True)
class BenchmarkStage:
    """One named subprocess in the complete benchmark suite."""

    name: str
    command: tuple[str, ...]


def build_stage_plan(
    *,
    outdir: str | Path,
    max_areas: str = "50,100,200,400",
    pareto_area: float = 400.0,
    python_executable: str = sys.executable,
    include_tests: bool = True,
    include_cross_tool: bool = True,
    include_smoke: bool = True,
    include_square_oracle: bool = True,
    include_public_api: bool = True,
    measure_memory: bool = True,
) -> tuple[BenchmarkStage, ...]:
    """Build the deterministic subprocess plan for the complete suite."""

    output_root = Path(outdir).expanduser().resolve()
    stages: list[BenchmarkStage] = []

    if include_tests:
        stages.append(
            BenchmarkStage(
                name="benchmark contract tests",
                command=(
                    python_executable,
                    "-m",
                    "pytest",
                    "-q",
                    *BENCHMARK_TEST_TARGETS,
                ),
            )
        )

    if include_cross_tool:
        stages.append(
            BenchmarkStage(
                name="CALM versus pymatgen ZSL",
                command=(
                    python_executable,
                    "-m",
                    "benchmarks.run_all",
                    "--outdir",
                    str(output_root / "cross_tool"),
                    "--max-areas",
                    str(max_areas),
                    "--pareto-area",
                    str(float(pareto_area)),
                ),
            )
        )

    if include_smoke:
        stages.append(
            BenchmarkStage(
                name="four-case coupled qualification",
                command=(
                    python_executable,
                    "-m",
                    "benchmarks.run_coupled_qualification",
                    "--out",
                    str(output_root / "coupled-smoke.csv"),
                    "--k-max",
                    "5",
                ),
            )
        )

    if include_square_oracle:
        square_command = [
            python_executable,
            "-m",
            "benchmarks.run_coupled_qualification",
            "--out",
            str(output_root / "coupled-square-scaling.csv"),
            "--case",
            "equal_square",
            "--k-max",
            "5",
            "--k-max",
            "30",
        ]
        if measure_memory:
            square_command.append("--measure-memory")
        stages.append(
            BenchmarkStage(
                name="equal-square K=5 and K=30 oracle",
                command=tuple(square_command),
            )
        )

    if include_public_api:
        stages.append(
            BenchmarkStage(
                name="project-centered public API qualification",
                command=(
                    python_executable,
                    "-m",
                    "benchmarks.run_public_api_qualification",
                    "--project",
                    str(output_root / "public_api_qualification.calm"),
                    "--out",
                    str(output_root / "public_api_qualification.json"),
                    "--reset",
                ),
            )
        )

    return tuple(stages)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the complete CALM benchmark and qualification suite."
    )
    parser.add_argument("--outdir", default="bench_out")
    parser.add_argument("--max-areas", default="50,100,200,400")
    parser.add_argument("--pareto-area", type=float, default=400.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-cross-tool", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--skip-square-oracle", action="store_true")
    parser.add_argument("--skip-public-api", action="store_true")
    parser.add_argument("--no-measure-memory", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.outdir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    stages = build_stage_plan(
        outdir=output_root,
        max_areas=args.max_areas,
        pareto_area=args.pareto_area,
        include_tests=not args.skip_tests,
        include_cross_tool=not args.skip_cross_tool,
        include_smoke=not args.skip_smoke,
        include_square_oracle=not args.skip_square_oracle,
        include_public_api=not args.skip_public_api,
        measure_memory=not args.no_measure_memory,
    )
    if not stages:
        print("No benchmark stages selected.", file=sys.stderr)
        return 2

    for stage in stages:
        print(f"\n== {stage.name} ==", flush=True)
        print(f"+ {shlex.join(stage.command)}", flush=True)
        if args.dry_run:
            continue
        completed = subprocess.run(
            stage.command,
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        if completed.returncode != 0:
            print(
                f"Stage failed ({stage.name}) with exit code "
                f"{completed.returncode}.",
                file=sys.stderr,
            )
            return int(completed.returncode)

    if args.dry_run:
        print("\nDry run complete; no benchmark stages were executed.")
    else:
        print(f"\nComplete benchmark outputs written under: {output_root}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
