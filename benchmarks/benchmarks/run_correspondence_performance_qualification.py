"""Qualify and measure direct basis-correspondence enumeration workloads."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, localcontext
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
import tracemalloc
from typing import Any, Mapping, Sequence

import numpy as np

from calm.interface.matching import _correspondence as correspondence
from calm.interface.matching._correspondence import (
    enumerate_basis_correspondences_2d,
)

from ._performance_support import (
    environment_metadata,
    exact_nonnegative_int,
    exact_positive_int,
    profile_callable,
    selected_workloads,
    sha256_path,
    source_metadata,
    summarize_measurements,
    validate_measurement_equivalence,
    write_json_report,
)


REPORT_SCHEMA = "calm.correspondence_performance_qualification/v2"
MATRIX_SCHEMA = "calm.correspondence_performance_matrix/v2"
REFERENCE_DECIMAL_PRECISION = 60
REFERENCE_DECIMAL_DIGITS = 45
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MATRIX_PATH = (
    REPOSITORY_ROOT
    / "engineering"
    / "qualification"
    / "correspondence-performance-matrix.json"
)
DIAGNOSTIC_STATS_FIELDS = ("determinant_chunks",)


@dataclass(frozen=True)
class CorrespondencePerformanceWorkload:
    benchmark_id: str
    family: str
    metric_a: np.ndarray
    metric_b: np.ndarray
    eps_principal_max: float
    orientation: str
    metric_tolerance: float
    entry_limit: int | None
    strain_reference_atol: float
    profile: bool
    purpose: str
    expected: Mapping[str, Any]


@dataclass(frozen=True)
class CorrespondencePerformanceMatrix:
    path: Path
    sha256: str
    default_repeats: int
    default_memory_repeats: int
    default_warmup_runs: int
    correctness_fields: tuple[str, ...]
    workloads: tuple[CorrespondencePerformanceWorkload, ...]


def _matrix(name: str, value: object) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must be one finite 2x2 matrix")
    return matrix


def _finite_positive_float(name: str, value: object) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def load_correspondence_performance_matrix(
    path: str | Path = DEFAULT_MATRIX_PATH,
) -> CorrespondencePerformanceMatrix:
    matrix_path = Path(path).expanduser().resolve()
    payload = json.loads(matrix_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("correspondence performance matrix must be an object")
    if payload.get("schema") != MATRIX_SCHEMA:
        raise ValueError(
            "unsupported correspondence performance matrix schema: "
            f"{payload.get('schema')!r}"
        )

    correctness = payload.get("correctness_fields")
    if not isinstance(correctness, list) or not correctness:
        raise ValueError("correctness_fields must be a nonempty list")
    correctness_fields = tuple(str(value) for value in correctness)
    if len(set(correctness_fields)) != len(correctness_fields):
        raise ValueError("correctness_fields must be unique")

    raw_workloads = payload.get("workloads")
    if not isinstance(raw_workloads, list) or not raw_workloads:
        raise ValueError("workloads must be a nonempty list")
    workloads: list[CorrespondencePerformanceWorkload] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(raw_workloads):
        if not isinstance(raw, dict):
            raise TypeError(f"workloads[{index}] must be an object")
        benchmark_id = str(raw.get("id", "")).strip()
        if not benchmark_id or benchmark_id in identifiers:
            raise ValueError(f"invalid or duplicate workload id {benchmark_id!r}")
        identifiers.add(benchmark_id)
        expected = raw.get("expected")
        if not isinstance(expected, dict):
            raise TypeError(f"workload {benchmark_id!r} expected must be an object")
        entry_limit_raw = raw.get("entry_limit")
        entry_limit = (
            None
            if entry_limit_raw is None
            else exact_positive_int("entry_limit", entry_limit_raw)
        )
        workloads.append(
            CorrespondencePerformanceWorkload(
                benchmark_id=benchmark_id,
                family=str(raw.get("family", "")).strip(),
                metric_a=_matrix("metric_a", raw.get("metric_a")),
                metric_b=_matrix("metric_b", raw.get("metric_b")),
                eps_principal_max=float(raw.get("eps_principal_max")),
                orientation=str(raw.get("orientation", "")),
                metric_tolerance=float(raw.get("metric_tolerance")),
                entry_limit=entry_limit,
                strain_reference_atol=_finite_positive_float(
                    "strain_reference_atol",
                    raw.get("strain_reference_atol"),
                ),
                profile=bool(raw.get("profile", False)),
                purpose=str(raw.get("purpose", "")).strip(),
                expected=dict(expected),
            )
        )

    return CorrespondencePerformanceMatrix(
        path=matrix_path,
        sha256=sha256_path(matrix_path),
        default_repeats=exact_positive_int(
            "default_repeats", payload.get("default_repeats")
        ),
        default_memory_repeats=exact_positive_int(
            "default_memory_repeats", payload.get("default_memory_repeats")
        ),
        default_warmup_runs=exact_nonnegative_int(
            "default_warmup_runs", payload.get("default_warmup_runs")
        ),
        correctness_fields=correctness_fields,
        workloads=tuple(workloads),
    )


def _digest(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _decimal_float(value: object) -> Decimal:
    return Decimal.from_float(float(value))


def _reference_generalized_eigenvalues(
    workload: CorrespondencePerformanceWorkload,
    transform: np.ndarray,
) -> tuple[Decimal, Decimal]:
    """Return deterministic generalized metric eigenvalues for one transform."""

    metric_a = workload.metric_a
    metric_b = workload.metric_b
    a00, a01, a11 = (
        _decimal_float(metric_a[0, 0]),
        _decimal_float(metric_a[0, 1]),
        _decimal_float(metric_a[1, 1]),
    )
    b00, b01, b11 = (
        _decimal_float(metric_b[0, 0]),
        _decimal_float(metric_b[0, 1]),
        _decimal_float(metric_b[1, 1]),
    )
    u00, u01, u10, u11 = (int(value) for value in transform.ravel())
    two = Decimal(2)
    four = Decimal(4)

    transformed_00 = (
        b00 * u00 * u00
        + two * b01 * u00 * u10
        + b11 * u10 * u10
    )
    transformed_01 = (
        b00 * u00 * u01
        + b01 * (u00 * u11 + u10 * u01)
        + b11 * u10 * u11
    )
    transformed_11 = (
        b00 * u01 * u01
        + two * b01 * u01 * u11
        + b11 * u11 * u11
    )

    determinant_a = a00 * a11 - a01 * a01
    determinant_transformed = (
        transformed_00 * transformed_11 - transformed_01 * transformed_01
    )
    cross = (
        transformed_00 * a11
        + transformed_11 * a00
        - two * transformed_01 * a01
    )
    discriminant = (
        cross * cross
        - four * determinant_a * determinant_transformed
    )
    if determinant_a <= 0 or discriminant < 0:
        raise RuntimeError(
            "invalid deterministic generalized-eigenvalue reference state"
        )
    root = discriminant.sqrt()
    denominator = two * determinant_a
    eigenvalues = (
        (cross - root) / denominator,
        (cross + root) / denominator,
    )
    if eigenvalues[0] <= 0 or eigenvalues[1] <= 0:
        raise RuntimeError(
            "nonpositive deterministic generalized-eigenvalue reference"
        )
    return eigenvalues


def _reference_record_evidence(
    workload: CorrespondencePerformanceWorkload,
    correspondences: Sequence[Any],
) -> tuple[str, float]:
    payload: list[dict[str, Any]] = []
    maximum_error = 0.0
    with localcontext() as context:
        context.prec = REFERENCE_DECIMAL_PRECISION
        for item in correspondences:
            eigenvalues = _reference_generalized_eigenvalues(
                workload,
                item.U_B,
            )
            reference_strains = tuple(
                0.5 * math.log(float(value))
                for value in eigenvalues
            )
            maximum_error = max(
                maximum_error,
                *(
                    abs(float(observed) - reference)
                    for observed, reference in zip(
                        item.principal_strains,
                        reference_strains,
                        strict=True,
                    )
                ),
            )
            payload.append(
                {
                    "u": [int(value) for value in item.U_B.ravel()],
                    "lambda": [
                        format(value, f".{REFERENCE_DECIMAL_DIGITS}E")
                        for value in eigenvalues
                    ],
                }
            )
    return _digest(payload), maximum_error


def _qualification(
    workload: CorrespondencePerformanceWorkload,
    correspondences: Sequence[Any],
    stats: Mapping[str, int],
) -> dict[str, Any]:
    transform_payload = [
        [int(value) for value in item.U_B.ravel()]
        for item in correspondences
    ]
    observed_record_payload = [
        {
            "u": [int(value) for value in item.U_B.ravel()],
            "s": [float(value).hex() for value in item.principal_strains],
        }
        for item in correspondences
    ]
    reference_digest, maximum_reference_error = _reference_record_evidence(
        workload,
        correspondences,
    )
    if maximum_reference_error > workload.strain_reference_atol:
        raise RuntimeError(
            f"correspondence numerical reference mismatch for "
            f"{workload.benchmark_id}: max_abs_error="
            f"{maximum_reference_error:.17g}, atol="
            f"{workload.strain_reference_atol:.17g}"
        )
    diagnostic_stats = {
        key: int(stats[key])
        for key in DIAGNOSTIC_STATS_FIELDS
        if key in stats
    }
    qualification = {
        "implementation": "complete_basis_correspondence_2d",
        "transform_key_sha256": _digest(transform_payload),
        "reference_record_sha256": reference_digest,
        "observed_record_sha256": _digest(observed_record_payload),
        "max_abs_strain_reference_error": maximum_reference_error,
        "strain_reference_atol": workload.strain_reference_atol,
        "correspondence_count": len(correspondences),
        **{key: int(value) for key, value in stats.items()},
        **diagnostic_stats,
    }
    for key, expected in workload.expected.items():
        if qualification.get(key) != expected:
            raise RuntimeError(
                f"correspondence oracle mismatch for {workload.benchmark_id}: "
                f"{key}: expected={expected!r}, observed={qualification.get(key)!r}"
            )
    return qualification


def run_workload_trial(
    workload: CorrespondencePerformanceWorkload,
    *,
    clear_cache: bool,
    measure_memory: bool,
) -> dict[str, Any]:
    if clear_cache:
        correspondence._enumerate_cached.cache_clear()
    stats: dict[str, int] = {}
    if measure_memory:
        tracemalloc.start()
    start = time.perf_counter()
    try:
        results = enumerate_basis_correspondences_2d(
            workload.metric_a,
            workload.metric_b,
            eps_principal_max=workload.eps_principal_max,
            orientation=workload.orientation,  # type: ignore[arg-type]
            metric_tolerance=workload.metric_tolerance,
            entry_limit=workload.entry_limit,
            stats=stats,
        )
    finally:
        elapsed = time.perf_counter() - start
        if measure_memory:
            _current, peak_python_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        else:
            peak_python_bytes = None
    return {
        "elapsed_seconds": elapsed,
        "peak_python_bytes": peak_python_bytes,
        "qualification": _qualification(workload, results, stats),
        "cache_info": correspondence._enumerate_cached.cache_info()._asdict(),
    }


def _mode_result(
    mode: str,
    measurements: Sequence[Mapping[str, Any]],
    memory_measurements: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> dict[str, Any]:
    all_measurements = tuple(measurements) + tuple(memory_measurements)
    return {
        "mode": mode,
        "correctness_signature": validate_measurement_equivalence(
            all_measurements,
            correctness_fields=fields,
            error_prefix=f"{mode} correspondence trials changed correctness",
        ),
        "summary": summarize_measurements(
            measurements,
            memory_measurements=memory_measurements,
            include_timing_sample_count=False,
            include_process_memory=False,
        ),
        "timing_measurements": list(measurements),
        "memory_measurements": list(memory_measurements),
    }

def _profile(
    workload: CorrespondencePerformanceWorkload,
    output_directory: str | Path | None,
) -> dict[str, Any]:
    correspondence._enumerate_cached.cache_clear()
    artifact = None
    if output_directory is not None:
        artifact = (
            Path(output_directory).expanduser().resolve()
            / f"{workload.benchmark_id}.prof"
        )
    evidence = profile_callable(
        lambda: run_workload_trial(
            workload,
            clear_cache=False,
            measure_memory=False,
        ),
        artifact_path=artifact,
        repository_root=REPOSITORY_ROOT,
        production_root=REPOSITORY_ROOT / "calm",
        top_n=30,
        include_call_counts=False,
        relative_filenames=False,
    )
    return {
        "benchmark_id": workload.benchmark_id,
        "measurement": evidence["measurement"],
        "profile_artifact": evidence["artifact"],
        "production_top_cumulative": evidence["production_top_cumulative"],
    }

def run_qualification(
    *,
    matrix: CorrespondencePerformanceMatrix,
    workloads: Sequence[CorrespondencePerformanceWorkload],
    repeats: int,
    memory_repeats: int,
    warmup_runs: int,
    measure_memory: bool,
    include_profiles: bool,
    profile_output_directory: str | Path | None,
    require_clean: bool,
) -> dict[str, Any]:
    source = source_metadata(REPOSITORY_ROOT)
    if require_clean and source["git_clean"] is not True:
        raise RuntimeError(
            "correspondence performance qualification requires a clean "
            "identified Git source tree"
        )
    repeats = exact_positive_int("repeats", repeats)
    memory_repeats = exact_positive_int("memory_repeats", memory_repeats)
    warmup_runs = exact_nonnegative_int("warmup_runs", warmup_runs)
    workload_results: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []

    for workload in workloads:
        cold = tuple(
            run_workload_trial(
                workload,
                clear_cache=True,
                measure_memory=False,
            )
            for _ in range(repeats)
        )
        cold_memory = (
            tuple(
                run_workload_trial(
                    workload,
                    clear_cache=True,
                    measure_memory=True,
                )
                for _ in range(memory_repeats)
            )
            if measure_memory
            else ()
        )
        correspondence._enumerate_cached.cache_clear()
        for _ in range(warmup_runs):
            run_workload_trial(
                workload,
                clear_cache=False,
                measure_memory=False,
            )
        warm = tuple(
            run_workload_trial(
                workload,
                clear_cache=False,
                measure_memory=False,
            )
            for _ in range(repeats)
        )
        warm_memory = (
            tuple(
                run_workload_trial(
                    workload,
                    clear_cache=False,
                    measure_memory=True,
                )
                for _ in range(memory_repeats)
            )
            if measure_memory
            else ()
        )
        modes = (
            _mode_result(
                "cold_cache",
                cold,
                cold_memory,
                matrix.correctness_fields,
            ),
            _mode_result(
                "warm_cache",
                warm,
                warm_memory,
                matrix.correctness_fields,
            ),
        )
        if modes[0]["correctness_signature"] != modes[1]["correctness_signature"]:
            raise RuntimeError(
                f"cold/warm cache mismatch for {workload.benchmark_id}"
            )
        workload_results.append(
            {
                "benchmark_id": workload.benchmark_id,
                "family": workload.family,
                "purpose": workload.purpose,
                "modes": list(modes),
            }
        )
        if include_profiles and workload.profile:
            profiles.append(_profile(workload, profile_output_directory))

    return {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "environment": environment_metadata(),
        "matrix": {
            "path": str(matrix.path),
            "sha256": matrix.sha256,
            "schema": MATRIX_SCHEMA,
        },
        "measurement_policy": {
            "timing_repeats": repeats,
            "memory_repeats": memory_repeats if measure_memory else 0,
            "warmup_runs": warmup_runs,
            "cold_cache": "clear production LRU before every trial",
            "warm_cache": "reuse production LRU after explicit warmup",
            "numerical_reference": (
                "60_digit_decimal_generalized_metric_eigenvalues"
            ),
            "observed_record_sha256": (
                "platform_specific_diagnostic_not_correctness"
            ),
            "timing_thresholds": "none_same_host_comparison_only",
        },
        "workloads": workload_results,
        "profiles": profiles,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure exact basis-correspondence enumeration performance."
    )
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX_PATH))
    parser.add_argument("--out", default="build/performance/0337d-correspondence.json")
    parser.add_argument("--benchmark", action="append", default=[])
    parser.add_argument("--repeats", type=int)
    parser.add_argument("--memory-repeats", type=int)
    parser.add_argument("--warmup-runs", type=int)
    parser.add_argument("--measure-memory", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--profile-outdir")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--list", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    matrix = load_correspondence_performance_matrix(args.matrix)
    workloads = selected_workloads(
        matrix.workloads,
        args.benchmark,
        identifier=lambda workload: workload.benchmark_id,
        label="correspondence workload",
    )
    if args.list:
        for workload in workloads:
            print(
                f"{workload.benchmark_id}: family={workload.family} "
                f"profile={workload.profile}"
            )
        return 0
    report = run_qualification(
        matrix=matrix,
        workloads=workloads,
        repeats=matrix.default_repeats if args.repeats is None else args.repeats,
        memory_repeats=(
            matrix.default_memory_repeats
            if args.memory_repeats is None
            else args.memory_repeats
        ),
        warmup_runs=(
            matrix.default_warmup_runs
            if args.warmup_runs is None
            else args.warmup_runs
        ),
        measure_memory=args.measure_memory,
        include_profiles=args.profile,
        profile_output_directory=args.profile_outdir,
        require_clean=args.require_clean,
    )
    write_json_report(report, args.out)
    print(Path(args.out).expanduser().resolve())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
