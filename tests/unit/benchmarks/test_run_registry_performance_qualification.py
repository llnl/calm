from __future__ import annotations

import json
from pathlib import Path

from benchmarks.benchmarks.run_registry_performance_qualification import (
    MATRIX_SCHEMA,
    REPORT_SCHEMA,
    _portable_oracle_mismatches,
    load_registry_performance_matrix,
    main,
    run_workload_trial,
)


def test_reviewed_registry_matrix_covers_size_and_step_scaling() -> None:
    matrix = load_registry_performance_matrix()
    by_id = {item.benchmark_id: item for item in matrix.workloads}

    assert matrix.default_repeats == 5
    assert matrix.default_memory_repeats == 1
    assert matrix.diagnostic_fields == ("observed_proposal_trace_sha256",)
    assert set(by_id) == {
        "registry_small_64_atoms_80_steps",
        "registry_medium_600_atoms_400_steps",
        "registry_large_2400_atoms_200_steps",
    }
    assert by_id["registry_medium_600_atoms_400_steps"].profile
    assert by_id["registry_large_2400_atoms_200_steps"].profile
    assert by_id["registry_medium_600_atoms_400_steps"].n_steps == 400
    assert by_id["registry_large_2400_atoms_200_steps"].atoms_per_slab == 1200


def test_small_registry_modes_reproduce_one_frozen_trajectory() -> None:
    workload = load_registry_performance_matrix().workloads[0]
    rebuild = run_workload_trial(
        workload,
        mode="rebuild_each_evaluation",
        measure_memory=False,
    )
    prepared = run_workload_trial(
        workload,
        mode="prepared_once",
        measure_memory=False,
    )

    assert rebuild["qualification"] == prepared["qualification"]
    assert "observed_proposal_trace_sha256" in rebuild["qualification"]
    assert "observed_proposal_trace_sha256" not in workload.expected
    assert rebuild["qualification"]["proposal_count"] == workload.n_steps
    assert rebuild["diagnostics"]["geometry_preparations"] == 81
    assert prepared["diagnostics"]["geometry_preparations"] == 1
    assert rebuild["diagnostics"]["calculator_constructions"] == 1
    assert prepared["diagnostics"]["calculator_constructions"] == 1


def test_cli_writes_registry_performance_report(tmp_path: Path) -> None:
    output = tmp_path / "registry-report.json"
    assert main(
        [
            "--out",
            str(output),
            "--benchmark",
            "registry_small_64_atoms_80_steps",
            "--repeats",
            "1",
        ]
    ) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == REPORT_SCHEMA
    assert report["matrix"]["schema"] == MATRIX_SCHEMA
    assert report["measurement_policy"]["comparison"] == (
        "fresh_process_rebuild_each_evaluation_vs_prepared_once"
    )
    workload = report["workloads"][0]
    assert [mode["mode"] for mode in workload["modes"]] == [
        "rebuild_each_evaluation",
        "prepared_once",
    ]
    assert workload["modes"][0]["correctness_signature"] == (
        workload["modes"][1]["correctness_signature"]
    )
    assert workload["speedup_rebuild_over_prepared"] > 0.0


def test_host_specific_rejected_proposal_digest_is_diagnostic_only() -> None:
    workload = load_registry_performance_matrix().workloads[-1]
    measurement = run_workload_trial(
        workload,
        mode="prepared_once",
        measure_memory=False,
    )
    qualification = dict(measurement["qualification"])
    qualification["observed_proposal_trace_sha256"] = "host-specific-alternate"

    assert _portable_oracle_mismatches(workload.expected, qualification) == {}

    qualification["trajectory_sha256"] = "changed-accepted-trajectory"
    assert _portable_oracle_mismatches(workload.expected, qualification) == {
        "trajectory_sha256": (
            workload.expected["trajectory_sha256"],
            "changed-accepted-trajectory",
        )
    }
