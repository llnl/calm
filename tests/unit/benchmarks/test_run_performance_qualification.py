from __future__ import annotations

import json
from pathlib import Path

from benchmarks.benchmarks.run_performance_qualification import (
    MATRIX_SCHEMA,
    PERFORMANCE_SCHEMA,
    PerformanceWorkload,
    load_performance_matrix,
    main,
    run_warm_process_measurements,
    summarize_measurements,
    validate_measurement_equivalence,
)


def _workload(*, k_max: int = 1) -> PerformanceWorkload:
    return PerformanceWorkload(
        benchmark_id=f"test_equal_square_k{k_max}",
        family="coupled_matching",
        case="equal_square",
        k_max=k_max,
        modes=("cold_process", "warm_process"),
        profile=False,
        purpose="Unit-test workload.",
    )


def test_reviewed_matrix_covers_square_scaling_and_geometry_families() -> None:
    matrix = load_performance_matrix()
    by_id = {workload.benchmark_id: workload for workload in matrix.workloads}

    assert matrix.default_repeats == 3
    assert matrix.default_memory_repeats == 1
    assert matrix.default_warmup_runs == 1
    assert [by_id[f"coupled_equal_square_k{k}"].k_max for k in (5, 10, 20, 30)] == [
        5,
        10,
        20,
        30,
    ]
    assert {
        by_id["coupled_rectangular_k5"].case,
        by_id["coupled_hexagonal_k5"].case,
        by_id["coupled_oblique_k5"].case,
    } == {
        "rect_small_mismatch",
        "hex_near_degenerate",
        "oblique_tradeoff",
    }
    assert [workload.benchmark_id for workload in matrix.workloads if workload.profile] == [
        "coupled_equal_square_k20"
    ]
    assert "pair_key_sha256" in matrix.correctness_fields
    assert "pair_identity_sha256" in matrix.correctness_fields


def test_measurement_summary_preserves_raw_distribution_semantics() -> None:
    measurements = (
        {
            "elapsed_seconds": 2.0,
            "peak_python_bytes": 200,
            "peak_process_bytes": 2_000,
            "qualification": {"pair_key_sha256": "same"},
        },
        {
            "elapsed_seconds": 1.0,
            "peak_python_bytes": 100,
            "peak_process_bytes": 1_000,
            "qualification": {"pair_key_sha256": "same"},
        },
        {
            "elapsed_seconds": 3.0,
            "peak_python_bytes": 300,
            "peak_process_bytes": 3_000,
            "qualification": {"pair_key_sha256": "same"},
        },
    )

    signature = validate_measurement_equivalence(
        measurements,
        correctness_fields=("pair_key_sha256",),
    )
    summary = summarize_measurements(
        measurements,
        memory_measurements=measurements,
    )

    assert signature == {"pair_key_sha256": "same"}
    assert summary["timing_sample_count"] == 3
    assert summary["elapsed_seconds"] == {
        "minimum": 1.0,
        "median": 2.0,
        "mean": 2.0,
        "maximum": 3.0,
        "sample_standard_deviation": 1.0,
    }
    assert summary["peak_python_bytes"] == {
        "sample_count": 3,
        "minimum": 100,
        "median": 200,
        "maximum": 300,
    }
    assert summary["peak_process_bytes"] == {
        "sample_count": 3,
        "minimum": 1_000,
        "median": 2_000,
        "maximum": 3_000,
    }


def test_warm_trials_reproduce_the_exact_square_oracle() -> None:
    measurements = run_warm_process_measurements(
        _workload(),
        repeats=2,
        warmup_runs=0,
        measure_memory=False,
    )

    signature = validate_measurement_equivalence(
        measurements,
        correctness_fields=(
            "implementation",
            "oracle_status",
            "pair_key_sha256",
            "pair_identity_sha256",
            "class_count",
        ),
    )
    assert signature["implementation"] == "primitive_coupled_pair_v2"
    assert signature["oracle_status"] == "pass"
    assert signature["class_count"] == 1
    assert len(signature["pair_key_sha256"]) == 64
    assert len(signature["pair_identity_sha256"]) == 64


def test_cli_writes_a_stable_report_from_a_small_matrix(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    report_path = tmp_path / "report.json"
    matrix_path.write_text(
        json.dumps(
            {
                "schema": MATRIX_SCHEMA,
                "default_repeats": 1,
                "default_memory_repeats": 1,
                "default_warmup_runs": 0,
                "correctness_fields": [
                    "implementation",
                    "oracle_status",
                    "pair_key_sha256",
                    "pair_identity_sha256",
                    "class_count",
                ],
                "workloads": [
                    {
                        "id": "test_equal_square_k1",
                        "family": "coupled_matching",
                        "case": "equal_square",
                        "k_max": 1,
                        "modes": ["warm_process"],
                        "profile": False,
                        "purpose": "Small CLI contract fixture.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(
        [
            "--matrix",
            str(matrix_path),
            "--out",
            str(report_path),
            "--skip-cold",
        ]
    ) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema"] == PERFORMANCE_SCHEMA
    assert report["matrix"]["schema"] == MATRIX_SCHEMA
    assert report["measurement_policy"]["timing_thresholds"] == (
        "none_same_host_comparison_only"
    )
    workload = report["workloads"][0]
    assert workload["benchmark_id"] == "test_equal_square_k1"
    assert workload["modes"][0]["mode"] == "warm_process"
    assert workload["modes"][0]["process_memory_scope"] == (
        "shared_process_lifetime_high_water"
    )
    assert report["measurement_policy"]["process_memory_comparison_mode"] == (
        "cold_process_only"
    )
    assert workload["modes"][0]["correctness_signature"]["oracle_status"] == "pass"
