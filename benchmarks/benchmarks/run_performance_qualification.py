"""Measure correctness-preserving CALM compute performance.

The performance harness deliberately separates two measurement modes:

``cold_process``
    Every recorded trial executes in a fresh Python interpreter.  This measures
    import, allocator, and process-local cache behavior without contamination
    from earlier trials.

``warm_process``
    One interpreter executes explicit warm-up runs followed by recorded trials.
    This measures steady process-local behavior, including bounded or LRU cache
    reuse owned by the production implementation.

The harness reuses :mod:`benchmarks.run_coupled_qualification` for scientific
execution and frozen-oracle validation.  It does not contain a second matching
implementation and it never treats an elapsed-time threshold as scientific
correctness evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._performance_support import (
    correctness_signature,
    environment_metadata,
    exact_nonnegative_int,
    exact_positive_int,
    peak_process_bytes,
    profile_callable,
    run_json_worker,
    selected_workloads,
    sha256_path,
    source_metadata as _source_metadata,
    summarize_measurements,
    validate_measurement_equivalence,
    write_json_report,
)

from .run_coupled_qualification import (
    QualificationCase,
    default_qualification_cases,
    run_qualification_case,
)


PERFORMANCE_SCHEMA = "calm.compute_performance_qualification/v2"
MATRIX_SCHEMA = "calm.compute_performance_matrix/v1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CALM_SOURCE_ROOT = REPOSITORY_ROOT / "calm"
DEFAULT_MATRIX_PATH = (
    REPOSITORY_ROOT
    / "engineering"
    / "qualification"
    / "performance-matrix.json"
)
_ROW_ENVIRONMENT_FIELDS = {
    "python_version",
    "numpy_version",
    "calm_version",
    "platform",
}


@dataclass(frozen=True)
class PerformanceWorkload:
    """One exact benchmark workload from the performance matrix."""

    benchmark_id: str
    family: str
    case: str
    k_max: int
    modes: tuple[str, ...]
    profile: bool
    purpose: str


@dataclass(frozen=True)
class PerformanceMatrix:
    """Validated executable performance qualification contract."""

    path: Path
    sha256: str
    default_repeats: int
    default_memory_repeats: int
    default_warmup_runs: int
    correctness_fields: tuple[str, ...]
    workloads: tuple[PerformanceWorkload, ...]


def load_performance_matrix(
    path: str | Path = DEFAULT_MATRIX_PATH,
) -> PerformanceMatrix:
    """Load and validate the machine-readable performance contract."""

    matrix_path = Path(path).expanduser().resolve()
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("performance matrix must contain one JSON object")
    if payload.get("schema") != MATRIX_SCHEMA:
        raise ValueError(
            "unsupported performance matrix schema: "
            f"{payload.get('schema')!r}"
        )

    default_repeats = exact_positive_int(
        "default_repeats",
        payload.get("default_repeats"),
    )
    default_memory_repeats = exact_positive_int(
        "default_memory_repeats",
        payload.get("default_memory_repeats"),
    )
    default_warmup_runs = exact_nonnegative_int(
        "default_warmup_runs",
        payload.get("default_warmup_runs"),
    )

    raw_fields = payload.get("correctness_fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ValueError("correctness_fields must be a nonempty list")
    correctness_fields = tuple(str(field) for field in raw_fields)
    if len(set(correctness_fields)) != len(correctness_fields):
        raise ValueError("correctness_fields must be unique")

    raw_workloads = payload.get("workloads")
    if not isinstance(raw_workloads, list) or not raw_workloads:
        raise ValueError("workloads must be a nonempty list")

    workloads: list[PerformanceWorkload] = []
    identifiers: set[str] = set()
    valid_modes = {"cold_process", "warm_process"}
    for index, raw in enumerate(raw_workloads):
        if not isinstance(raw, dict):
            raise TypeError(f"workloads[{index}] must be an object")
        benchmark_id = str(raw.get("id", "")).strip()
        if not benchmark_id:
            raise ValueError(f"workloads[{index}].id must be nonempty")
        if benchmark_id in identifiers:
            raise ValueError(f"duplicate benchmark id {benchmark_id!r}")
        identifiers.add(benchmark_id)

        modes = tuple(str(mode) for mode in raw.get("modes", ()))
        if not modes or set(modes) - valid_modes:
            raise ValueError(
                f"workload {benchmark_id!r} has invalid modes {modes!r}"
            )
        if len(set(modes)) != len(modes):
            raise ValueError(f"workload {benchmark_id!r} repeats a mode")

        workloads.append(
            PerformanceWorkload(
                benchmark_id=benchmark_id,
                family=str(raw.get("family", "")).strip(),
                case=str(raw.get("case", "")).strip(),
                k_max=exact_positive_int(
                    f"workloads[{index}].k_max",
                    raw.get("k_max"),
                ),
                modes=modes,
                profile=bool(raw.get("profile", False)),
                purpose=str(raw.get("purpose", "")).strip(),
            )
        )

    known_cases = {case.name for case in default_qualification_cases()}
    unknown_cases = sorted({item.case for item in workloads} - known_cases)
    if unknown_cases:
        raise ValueError(
            "performance matrix references unknown qualification cases: "
            + ", ".join(unknown_cases)
        )

    return PerformanceMatrix(
        path=matrix_path,
        sha256=sha256_path(matrix_path),
        default_repeats=default_repeats,
        default_memory_repeats=default_memory_repeats,
        default_warmup_runs=default_warmup_runs,
        correctness_fields=correctness_fields,
        workloads=tuple(workloads),
    )


def _qualification_case(name: str) -> QualificationCase:
    cases = {case.name: case for case in default_qualification_cases()}
    try:
        return cases[name]
    except KeyError as exc:
        known = ", ".join(sorted(cases))
        raise ValueError(f"unknown qualification case {name!r}; known: {known}") from exc


def run_workload_trial(
    workload: PerformanceWorkload,
    *,
    measure_memory: bool,
) -> dict[str, Any]:
    """Execute one workload through the authoritative coupled qualification."""

    row = run_qualification_case(
        _qualification_case(workload.case),
        k_max=workload.k_max,
        measure_memory=measure_memory,
    )
    qualification = {
        key: value
        for key, value in row.items()
        if key not in _ROW_ENVIRONMENT_FIELDS
        and key not in {"elapsed_seconds", "peak_python_bytes"}
    }
    peak = row["peak_python_bytes"]
    return {
        "process_id": os.getpid(),
        "elapsed_seconds": float(row["elapsed_seconds"]),
        "peak_python_bytes": None if peak == "" else int(peak),
        "peak_process_bytes": peak_process_bytes(),
        "qualification": qualification,
    }


def run_warm_process_measurements(
    workload: PerformanceWorkload,
    *,
    repeats: int,
    warmup_runs: int,
    measure_memory: bool,
) -> tuple[dict[str, Any], ...]:
    """Run warm-up and recorded trials in the current interpreter."""

    repeats = exact_positive_int("repeats", repeats)
    warmup_runs = exact_nonnegative_int("warmup_runs", warmup_runs)
    for _ in range(warmup_runs):
        run_workload_trial(workload, measure_memory=False)
    return tuple(
        run_workload_trial(workload, measure_memory=measure_memory)
        for _ in range(repeats)
    )


def _run_worker_subprocess(
    workload: PerformanceWorkload,
    *,
    python_executable: str,
    measure_memory: bool,
) -> dict[str, Any]:
    payload = {
        "benchmark_id": workload.benchmark_id,
        "family": workload.family,
        "case": workload.case,
        "k_max": workload.k_max,
        "modes": list(workload.modes),
        "profile": workload.profile,
        "purpose": workload.purpose,
        "measure_memory": bool(measure_memory),
    }
    return run_json_worker(
        module="benchmarks.run_performance_qualification",
        payload=payload,
        repository_root=REPOSITORY_ROOT,
        error_label="fresh-process performance worker",
        python_executable=python_executable,
    )


def run_cold_process_measurements(
    workload: PerformanceWorkload,
    *,
    repeats: int,
    python_executable: str = sys.executable,
    measure_memory: bool,
) -> tuple[dict[str, Any], ...]:
    """Run every recorded trial in a fresh Python interpreter."""

    repeats = exact_positive_int("repeats", repeats)
    return tuple(
        _run_worker_subprocess(
            workload,
            python_executable=python_executable,
            measure_memory=measure_memory,
        )
        for _ in range(repeats)
    )


def profile_workload(
    workload: PerformanceWorkload,
    *,
    top_n: int,
    output_directory: str | Path | None,
    correctness_fields: Sequence[str],
) -> dict[str, Any]:
    """Profile one authoritative trial and preserve its exact signature."""

    artifact = None
    if output_directory is not None:
        artifact = (
            Path(output_directory).expanduser().resolve()
            / f"{workload.benchmark_id}.prof"
        )
    evidence = profile_callable(
        lambda: run_workload_trial(workload, measure_memory=False),
        artifact_path=artifact,
        repository_root=REPOSITORY_ROOT,
        production_root=CALM_SOURCE_ROOT,
        top_n=top_n,
    )
    measurement = evidence["measurement"]
    return {
        "benchmark_id": workload.benchmark_id,
        "measurement": measurement,
        "correctness_signature": correctness_signature(
            measurement,
            correctness_fields,
        ),
        "profile_artifact": evidence["artifact"],
        "profile_artifact_sha256": evidence["artifact_sha256"],
        "production_top_cumulative": evidence["production_top_cumulative"],
        "overall_top_cumulative": evidence["overall_top_cumulative"],
    }

def _mode_result(
    *,
    mode: str,
    timing_measurements: Sequence[Mapping[str, Any]],
    memory_measurements: Sequence[Mapping[str, Any]],
    correctness_fields: Sequence[str],
) -> dict[str, Any]:
    all_measurements = tuple(timing_measurements) + tuple(memory_measurements)
    return {
        "mode": mode,
        "process_memory_scope": (
            "fresh_process_lifetime_high_water"
            if mode == "cold_process"
            else "shared_process_lifetime_high_water"
        ),
        "summary": summarize_measurements(
            timing_measurements,
            memory_measurements=memory_measurements,
        ),
        "correctness_signature": validate_measurement_equivalence(
            all_measurements,
            correctness_fields=correctness_fields,
        ),
        "timing_measurements": list(timing_measurements),
        "memory_measurements": list(memory_measurements),
    }


def run_performance_qualification(
    *,
    matrix: PerformanceMatrix,
    workloads: Sequence[PerformanceWorkload],
    repeats: int,
    memory_repeats: int,
    warmup_runs: int,
    include_cold: bool,
    include_warm: bool,
    measure_memory: bool,
    python_executable: str,
    include_profiles: bool,
    profile_all: bool,
    profile_top: int,
    profile_output_directory: str | Path | None,
    require_clean: bool,
) -> dict[str, Any]:
    """Execute selected workloads and return one complete evidence object."""

    repeats = exact_positive_int("repeats", repeats)
    memory_repeats = exact_positive_int("memory_repeats", memory_repeats)
    warmup_runs = exact_nonnegative_int("warmup_runs", warmup_runs)
    source = _source_metadata(REPOSITORY_ROOT)
    if require_clean and source["git_clean"] is not True:
        raise RuntimeError(
            "performance qualification requires a clean identified Git source tree"
        )
    if not include_cold and not include_warm and not include_profiles:
        raise ValueError("at least one measurement mode or profile must be enabled")

    workload_results: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    for workload in workloads:
        modes: list[dict[str, Any]] = []
        if include_cold and "cold_process" in workload.modes:
            cold_timing = run_cold_process_measurements(
                workload,
                repeats=repeats,
                python_executable=python_executable,
                measure_memory=False,
            )
            cold_memory = (
                run_cold_process_measurements(
                    workload,
                    repeats=memory_repeats,
                    python_executable=python_executable,
                    measure_memory=True,
                )
                if measure_memory
                else ()
            )
            modes.append(
                _mode_result(
                    mode="cold_process",
                    timing_measurements=cold_timing,
                    memory_measurements=cold_memory,
                    correctness_fields=matrix.correctness_fields,
                )
            )
        if include_warm and "warm_process" in workload.modes:
            warm_timing = run_warm_process_measurements(
                workload,
                repeats=repeats,
                warmup_runs=warmup_runs,
                measure_memory=False,
            )
            warm_memory = (
                run_warm_process_measurements(
                    workload,
                    repeats=memory_repeats,
                    warmup_runs=0,
                    measure_memory=True,
                )
                if measure_memory
                else ()
            )
            modes.append(
                _mode_result(
                    mode="warm_process",
                    timing_measurements=warm_timing,
                    memory_measurements=warm_memory,
                    correctness_fields=matrix.correctness_fields,
                )
            )

        signatures = [item["correctness_signature"] for item in modes]
        if signatures and any(signature != signatures[0] for signature in signatures[1:]):
            raise RuntimeError(
                f"cold/warm correctness mismatch for {workload.benchmark_id!r}"
            )

        workload_results.append(
            {
                "benchmark_id": workload.benchmark_id,
                "family": workload.family,
                "case": workload.case,
                "k_max": workload.k_max,
                "purpose": workload.purpose,
                "modes": modes,
            }
        )

        if include_profiles and (profile_all or workload.profile):
            profile = profile_workload(
                workload,
                top_n=profile_top,
                output_directory=profile_output_directory,
                correctness_fields=matrix.correctness_fields,
            )
            if signatures and profile["correctness_signature"] != signatures[0]:
                raise RuntimeError(
                    f"profiled trial changed correctness for {workload.benchmark_id!r}"
                )
            profiles.append(profile)

    return {
        "schema": PERFORMANCE_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "environment": environment_metadata(),
        "invocation": {
            "arguments": list(sys.argv),
            "working_directory": str(Path.cwd()),
        },
        "matrix": {
            "path": str(matrix.path),
            "sha256": matrix.sha256,
            "schema": MATRIX_SCHEMA,
        },
        "measurement_policy": {
            "timing_repeats": repeats,
            "memory_repeats": memory_repeats if measure_memory else 0,
            "warmup_runs": warmup_runs,
            "measure_memory_separately": bool(measure_memory),
            "python_allocation_metric": "tracemalloc_peak_during_scientific_run",
            "process_memory_metric": "ru_maxrss_process_lifetime_high_water",
            "process_memory_comparison_mode": "cold_process_only",
            "cold_process": bool(include_cold),
            "warm_process": bool(include_warm),
            "profiles": bool(include_profiles),
            "timing_thresholds": "none_same_host_comparison_only",
        },
        "workloads": workload_results,
        "profiles": profiles,
    }


def _workload_from_worker_payload(payload: Mapping[str, Any]) -> PerformanceWorkload:
    return PerformanceWorkload(
        benchmark_id=str(payload["benchmark_id"]),
        family=str(payload["family"]),
        case=str(payload["case"]),
        k_max=exact_positive_int("worker k_max", payload["k_max"]),
        modes=tuple(str(value) for value in payload["modes"]),
        profile=bool(payload["profile"]),
        purpose=str(payload["purpose"]),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure cold- and warm-process CALM performance while preserving "
            "the coupled-matcher correctness oracle."
        )
    )
    parser.add_argument("--out", help="Destination JSON report path.")
    parser.add_argument(
        "--matrix",
        default=str(DEFAULT_MATRIX_PATH),
        help="Performance matrix JSON path.",
    )
    parser.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help="Benchmark id; repeat to select multiple workloads. Defaults to all.",
    )
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--memory-repeats", type=int)
    parser.add_argument("--warmup-runs", type=int)
    parser.add_argument("--skip-cold", action="store_true")
    parser.add_argument("--skip-warm", action="store_true")
    parser.add_argument("--measure-memory", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-all", action="store_true")
    parser.add_argument("--profile-top", type=int, default=25)
    parser.add_argument("--profile-outdir")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--worker-payload", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.worker_payload is not None:
        payload = json.loads(args.worker_payload)
        if not isinstance(payload, dict):
            raise TypeError("worker payload must be one JSON object")
        workload = _workload_from_worker_payload(payload)
        measurement = run_workload_trial(
            workload,
            measure_memory=bool(payload.get("measure_memory", False)),
        )
        sys.stdout.write(
            json.dumps(measurement, sort_keys=True, ensure_ascii=True) + "\n"
        )
        return 0

    matrix = load_performance_matrix(args.matrix)
    workloads = selected_workloads(
        matrix.workloads,
        args.benchmark,
        identifier=lambda workload: workload.benchmark_id,
        label="performance benchmark",
    )
    if args.list:
        for workload in workloads:
            print(
                f"{workload.benchmark_id}: case={workload.case} "
                f"k_max={workload.k_max} modes={','.join(workload.modes)}"
            )
        return 0
    if not args.out:
        raise ValueError("--out is required unless --list is used")

    repeats = matrix.default_repeats if args.repeats is None else args.repeats
    memory_repeats = (
        matrix.default_memory_repeats
        if args.memory_repeats is None
        else args.memory_repeats
    )
    warmup_runs = (
        matrix.default_warmup_runs
        if args.warmup_runs is None
        else args.warmup_runs
    )
    report = run_performance_qualification(
        matrix=matrix,
        workloads=workloads,
        repeats=repeats,
        memory_repeats=memory_repeats,
        warmup_runs=warmup_runs,
        include_cold=not args.skip_cold,
        include_warm=not args.skip_warm,
        measure_memory=bool(args.measure_memory),
        python_executable=args.python,
        include_profiles=bool(args.profile or args.profile_all),
        profile_all=bool(args.profile_all),
        profile_top=args.profile_top,
        profile_output_directory=args.profile_outdir,
        require_clean=bool(args.require_clean),
    )
    write_json_report(report, args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
