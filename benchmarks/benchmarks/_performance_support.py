"""Shared mechanics for repository performance-qualification runners.

Scientific workload construction, correctness oracles, and report policy remain
owned by each runner.  This module owns only reusable execution mechanics:
source/runtime evidence, process workers, memory normalization, measurement
comparison and summaries, profile extraction, workload selection, and stable
JSON report writing.
"""

from __future__ import annotations

import cProfile
import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import platform
from pathlib import Path
import pstats
import statistics
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence, TypeVar

import numpy as np

try:  # ``resource`` is unavailable on Windows.
    import resource as _resource
except ImportError:  # pragma: no cover - platform-specific fallback
    _resource = None


_THREAD_ENVIRONMENT_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
)
_WorkloadT = TypeVar("_WorkloadT")


def sha256_path(path: Path) -> str:
    """Return the SHA-256 digest of one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_positive_int(name: str, value: object) -> int:
    """Require one non-Boolean positive integer."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def exact_nonnegative_int(name: str, value: object) -> int:
    """Require one non-Boolean nonnegative integer."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result < 0:
        raise ValueError(f"{name} must be nonnegative")
    return result


def peak_process_bytes() -> int | None:
    """Return process-lifetime peak resident memory in bytes when available."""

    if _resource is None:
        return None
    value = int(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss)
    if value < 0:
        return None
    if sys.platform == "darwin":
        return value
    return value * 1024


def correctness_signature(
    measurement: Mapping[str, Any],
    correctness_fields: Sequence[str],
) -> dict[str, Any]:
    """Extract one exact qualification signature from a measurement."""

    qualification = measurement.get("qualification")
    if not isinstance(qualification, Mapping):
        raise TypeError("measurement qualification must be a mapping")
    missing = [field for field in correctness_fields if field not in qualification]
    if missing:
        raise RuntimeError(
            "performance measurement is missing correctness fields: "
            + ", ".join(missing)
        )
    return {field: qualification[field] for field in correctness_fields}


def validate_measurement_equivalence(
    measurements: Sequence[Mapping[str, Any]],
    *,
    correctness_fields: Sequence[str],
    error_prefix: str = "performance trials changed exact scientific results",
) -> dict[str, Any]:
    """Require exact correctness agreement across recorded measurements."""

    if not measurements:
        raise ValueError("at least one measurement is required")
    reference = correctness_signature(measurements[0], correctness_fields)
    for index, measurement in enumerate(measurements[1:], start=1):
        observed = correctness_signature(measurement, correctness_fields)
        if observed != reference:
            raise RuntimeError(
                f"{error_prefix} at measurement {index}: "
                f"expected={reference!r}, observed={observed!r}"
            )
    return reference


def _distribution(values: Sequence[float], *, standard_deviation: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "minimum": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "maximum": max(values),
    }
    if standard_deviation:
        result["sample_standard_deviation"] = (
            statistics.stdev(values) if len(values) > 1 else 0.0
        )
    return result


def _peak_distribution(
    values: Sequence[int],
    *,
    include_sample_count: bool,
    include_extrema: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if include_sample_count:
        result["sample_count"] = len(values)
    if include_extrema:
        result["minimum"] = min(values) if values else None
    result["median"] = statistics.median(values) if values else None
    if include_extrema:
        result["maximum"] = max(values) if values else None
    return result


def summarize_measurements(
    timing_measurements: Sequence[Mapping[str, Any]],
    *,
    memory_measurements: Sequence[Mapping[str, Any]] = (),
    include_timing_sample_count: bool = True,
    include_standard_deviation: bool = True,
    include_process_memory: bool = True,
    detailed_peak_distributions: bool = True,
) -> dict[str, Any]:
    """Summarize timing and separately traced memory measurements."""

    if not timing_measurements:
        raise ValueError("at least one timing measurement is required")
    elapsed = [float(item["elapsed_seconds"]) for item in timing_measurements]
    python_peaks = [
        int(item["peak_python_bytes"])
        for item in memory_measurements
        if item.get("peak_python_bytes") is not None
    ]
    process_peaks = [
        int(item["peak_process_bytes"])
        for item in timing_measurements
        if item.get("peak_process_bytes") is not None
    ]
    result: dict[str, Any] = {}
    if include_timing_sample_count:
        result["timing_sample_count"] = len(elapsed)
    result["elapsed_seconds"] = _distribution(
        elapsed,
        standard_deviation=include_standard_deviation,
    )
    result["peak_python_bytes"] = _peak_distribution(
        python_peaks,
        include_sample_count=detailed_peak_distributions,
        include_extrema=detailed_peak_distributions,
    )
    if include_process_memory:
        result["peak_process_bytes"] = _peak_distribution(
            process_peaks,
            include_sample_count=detailed_peak_distributions,
            include_extrema=detailed_peak_distributions,
        )
    return result


def worker_environment() -> dict[str, str]:
    """Return a deterministic subprocess environment without overriding policy."""

    environment = dict(os.environ)
    environment.setdefault("PYTHONHASHSEED", "0")
    return environment


def run_json_worker(
    *,
    module: str,
    payload: Mapping[str, Any],
    repository_root: Path,
    error_label: str,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    """Run one repository worker module and decode its single JSON object."""

    command = (
        str(python_executable),
        "-m",
        module,
        "--worker-payload",
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True),
    )
    completed = subprocess.run(
        command,
        cwd=repository_root,
        env=worker_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{error_label} failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise TypeError(f"{error_label} did not return one JSON object")
    return value


def selected_workloads(
    workloads: Sequence[_WorkloadT],
    identifiers: Sequence[str],
    *,
    identifier: Callable[[_WorkloadT], str],
    label: str,
) -> tuple[_WorkloadT, ...]:
    """Select workloads in request order and reject unknown identifiers."""

    by_id = {identifier(workload): workload for workload in workloads}
    if not identifiers:
        return tuple(workloads)
    unknown = sorted(set(identifiers) - set(by_id))
    if unknown:
        raise ValueError(f"unknown {label} identifiers: " + ", ".join(unknown))
    return tuple(by_id[value] for value in identifiers)


def _relative_filename(filename: str, repository_root: Path) -> str:
    path = Path(filename)
    if not path.is_absolute():
        return filename
    try:
        return str(path.resolve().relative_to(repository_root))
    except ValueError:
        return str(path)


def profile_callable(
    callback: Callable[[], Mapping[str, Any]],
    *,
    artifact_path: Path | None,
    repository_root: Path,
    production_root: Path | None,
    top_n: int,
    include_call_counts: bool = True,
    relative_filenames: bool = True,
) -> dict[str, Any]:
    """Profile one callback and return its measurement and sorted entries."""

    top_n = exact_positive_int("profile_top", top_n)
    profiler = cProfile.Profile()
    profiler.enable()
    measurement = dict(callback())
    profiler.disable()

    artifact: str | None = None
    artifact_sha256: str | None = None
    if artifact_path is not None:
        resolved = artifact_path.expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        profiler.dump_stats(str(resolved))
        artifact = str(resolved)
        artifact_sha256 = sha256_path(resolved)

    overall: list[dict[str, Any]] = []
    production: list[dict[str, Any]] = []
    for (filename, line, function), values in pstats.Stats(profiler).stats.items():
        primitive_calls, total_calls, self_time, cumulative_time, _callers = values
        entry: dict[str, Any] = {
            "file": (
                _relative_filename(filename, repository_root)
                if relative_filenames
                else str(filename)
            ),
            "line": int(line),
            "function": str(function),
            "self_seconds": float(self_time),
            "cumulative_seconds": float(cumulative_time),
        }
        if include_call_counts:
            entry.update(
                {
                    "primitive_calls": int(primitive_calls),
                    "total_calls": int(total_calls),
                }
            )
        overall.append(entry)
        if production_root is not None:
            try:
                Path(filename).resolve().relative_to(production_root)
            except (ValueError, OSError):
                continue
            production.append(entry)

    order = lambda item: (
        -item["cumulative_seconds"],
        -item["self_seconds"],
        item["file"],
        item["line"],
        item["function"],
    )
    overall.sort(key=order)
    production.sort(key=order)
    return {
        "measurement": measurement,
        "artifact": artifact,
        "artifact_sha256": artifact_sha256,
        "overall_top_cumulative": overall[:top_n],
        "production_top_cumulative": production[:top_n],
    }


def _distribution_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _git_text(repository_root: Path, *arguments: str) -> str | None:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def source_metadata(repository_root: Path) -> dict[str, Any]:
    """Return exact source identity without claiming cleanliness implicitly."""

    commit = _git_text(repository_root, "rev-parse", "HEAD")
    status = _git_text(repository_root, "status", "--short")
    return {
        "repository_root": str(repository_root),
        "git_commit": commit,
        "git_status_short": status,
        "git_clean": status == "" if status is not None else None,
    }


def environment_metadata() -> dict[str, Any]:
    """Return runtime and thread-policy evidence for interpretation."""

    distributions = {
        name: _distribution_version(name)
        for name in (
            "calm",
            "numpy",
            "scipy",
            "ase",
            "spglib",
            "numba",
            "llvmlite",
        )
    }
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "distributions": distributions,
        "thread_environment": {
            name: os.environ.get(name)
            for name in _THREAD_ENVIRONMENT_VARIABLES
        },
    }


def write_json_report(report: Mapping[str, Any], output: str | Path) -> None:
    """Write one stable, human-readable JSON report."""

    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
