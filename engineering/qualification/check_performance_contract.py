#!/usr/bin/env python3
"""Verify the CALM compute-performance qualification contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from performance_contracts import (
    validate_correspondence_matrix,
    validate_coupled_matrix,
    validate_registry_matrix,
)
from performance_contracts.common import load_json_object, require_fragments


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION_ROOT = REPOSITORY_ROOT / "engineering" / "qualification"
BENCHMARK_ROOT = REPOSITORY_ROOT / "benchmarks"
BENCHMARK_IMPLEMENTATION_ROOT = BENCHMARK_ROOT / "benchmarks"

MATRIX_PATH = QUALIFICATION_ROOT / "performance-matrix.json"
CORRESPONDENCE_MATRIX_PATH = (
    QUALIFICATION_ROOT / "correspondence-performance-matrix.json"
)
REGISTRY_MATRIX_PATH = QUALIFICATION_ROOT / "registry-performance-matrix.json"
RUNNER_PATH = BENCHMARK_IMPLEMENTATION_ROOT / "run_performance_qualification.py"
WRAPPER_PATH = BENCHMARK_ROOT / "run_performance_qualification.py"
CORRESPONDENCE_RUNNER_PATH = (
    BENCHMARK_IMPLEMENTATION_ROOT
    / "run_correspondence_performance_qualification.py"
)
CORRESPONDENCE_WRAPPER_PATH = (
    BENCHMARK_ROOT / "run_correspondence_performance_qualification.py"
)
REGISTRY_RUNNER_PATH = (
    BENCHMARK_IMPLEMENTATION_ROOT / "run_registry_performance_qualification.py"
)
REGISTRY_WRAPPER_PATH = BENCHMARK_ROOT / "run_registry_performance_qualification.py"
SUPPORT_PATH = BENCHMARK_IMPLEMENTATION_ROOT / "_performance_support.py"
README_PATH = BENCHMARK_ROOT / "README.md"
VALIDATOR_ROOT = QUALIFICATION_ROOT / "performance_contracts"


def _required_paths() -> tuple[Path, ...]:
    return (
        MATRIX_PATH,
        CORRESPONDENCE_MATRIX_PATH,
        REGISTRY_MATRIX_PATH,
        RUNNER_PATH,
        WRAPPER_PATH,
        CORRESPONDENCE_RUNNER_PATH,
        CORRESPONDENCE_WRAPPER_PATH,
        REGISTRY_RUNNER_PATH,
        REGISTRY_WRAPPER_PATH,
        SUPPORT_PATH,
        README_PATH,
        VALIDATOR_ROOT / "__init__.py",
        VALIDATOR_ROOT / "common.py",
        VALIDATOR_ROOT / "coupled.py",
        VALIDATOR_ROOT / "correspondence.py",
        VALIDATOR_ROOT / "registry.py",
    )


def _validate_documentation(errors: list[str]) -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    fragments = (
        "python -m benchmarks.run_performance_qualification",
        "cold_process",
        "warm_process",
        "same-host",
        "pair_key_sha256",
        "--require-clean",
        "--measure-memory",
        "python -m benchmarks.run_correspondence_performance_qualification",
        "cold_cache",
        "warm_cache",
        "python -m benchmarks.run_registry_performance_qualification",
        "rebuild_each_evaluation",
        "prepared_once",
        "observed_proposal_trace_sha256",
    )
    for fragment in fragments:
        if fragment not in readme:
            errors.append(f"benchmarks README is missing {fragment!r}")


def _validate_shared_support(errors: list[str]) -> None:
    support = SUPPORT_PATH.read_text(encoding="utf-8")
    require_fragments(
        support,
        (
            "def peak_process_bytes",
            "def source_metadata",
            "def environment_metadata",
            "def run_json_worker",
            "def validate_measurement_equivalence",
            "def summarize_measurements",
            "def profile_callable",
            "def write_json_report",
        ),
        label="shared performance support",
        errors=errors,
    )


def validate() -> dict[str, Any]:
    errors: list[str] = []
    for path in _required_paths():
        if not path.is_file():
            errors.append(
                "missing performance qualification owner: "
                f"{path.relative_to(REPOSITORY_ROOT)}"
            )
    if errors:
        return {"schema": "calm.performance_contract_check/v1", "errors": errors}

    matrix = load_json_object(MATRIX_PATH)
    correspondence_matrix = load_json_object(CORRESPONDENCE_MATRIX_PATH)
    registry_matrix = load_json_object(REGISTRY_MATRIX_PATH)

    coupled = validate_coupled_matrix(
        matrix,
        runner_text=RUNNER_PATH.read_text(encoding="utf-8"),
        errors=errors,
    )
    correspondence = validate_correspondence_matrix(
        correspondence_matrix,
        runner_text=CORRESPONDENCE_RUNNER_PATH.read_text(encoding="utf-8"),
        errors=errors,
    )
    registry = validate_registry_matrix(
        registry_matrix,
        runner_text=REGISTRY_RUNNER_PATH.read_text(encoding="utf-8"),
        errors=errors,
    )
    _validate_documentation(errors)
    _validate_shared_support(errors)

    return {
        "schema": "calm.performance_contract_check/v1",
        "matrix_schema": coupled["schema"],
        "correspondence_matrix_schema": correspondence["schema"],
        "registry_matrix_schema": registry["schema"],
        "workload_count": coupled["workload_count"],
        "correspondence_workload_count": correspondence["workload_count"],
        "registry_workload_count": registry["workload_count"],
        "profile_workloads": coupled["profile_workloads"],
        "correspondence_profile_workloads": correspondence["profile_workloads"],
        "registry_profile_workloads": registry["profile_workloads"],
        "correctness_field_count": coupled["correctness_field_count"],
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
