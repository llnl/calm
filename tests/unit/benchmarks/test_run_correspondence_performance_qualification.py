from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from benchmarks.benchmarks.run_correspondence_performance_qualification import (
    MATRIX_SCHEMA,
    REPORT_SCHEMA,
    load_correspondence_performance_matrix,
    main,
    run_workload_trial,
)


def test_reviewed_correspondence_matrix_covers_two_large_families() -> None:
    matrix = load_correspondence_performance_matrix()
    by_id = {item.benchmark_id: item for item in matrix.workloads}

    assert matrix.default_repeats == 5
    assert matrix.default_memory_repeats == 1
    assert matrix.default_warmup_runs == 1
    assert set(by_id) == {
        "correspondence_small_skew_all",
        "correspondence_isotropic_annulus_proper",
        "correspondence_anisotropic_skew_all",
    }
    assert by_id["correspondence_isotropic_annulus_proper"].profile
    assert by_id["correspondence_anisotropic_skew_all"].profile
    assert all(item.strain_reference_atol == 1e-10 for item in matrix.workloads)
    assert (
        by_id["correspondence_isotropic_annulus_proper"].expected[
            "column_pairs_tested"
        ]
        == 1_597_696
    )
    assert (
        by_id["correspondence_anisotropic_skew_all"].expected[
            "column_pairs_tested"
        ]
        == 667_000
    )


def test_small_correspondence_trial_reproduces_frozen_oracle() -> None:
    workload = load_correspondence_performance_matrix().workloads[0]
    measurement = run_workload_trial(
        workload,
        clear_cache=True,
        measure_memory=False,
    )

    assert measurement["qualification"]["implementation"] == (
        "complete_basis_correspondence_2d"
    )
    assert measurement["qualification"]["correspondence_count"] == 8
    assert measurement["qualification"]["determinant_chunks"] == 0
    assert measurement["cache_info"]["misses"] == 1


def test_cli_writes_direct_correspondence_report(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    assert main(
        [
            "--out",
            str(output),
            "--benchmark",
            "correspondence_small_skew_all",
            "--repeats",
            "1",
            "--warmup-runs",
            "0",
        ]
    ) == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == REPORT_SCHEMA
    assert report["matrix"]["schema"] == MATRIX_SCHEMA
    assert report["measurement_policy"]["timing_thresholds"] == (
        "none_same_host_comparison_only"
    )
    assert report["measurement_policy"]["numerical_reference"] == (
        "60_digit_decimal_generalized_metric_eigenvalues"
    )
    assert report["measurement_policy"]["observed_record_sha256"] == (
        "platform_specific_diagnostic_not_correctness"
    )
    workload = report["workloads"][0]
    assert workload["benchmark_id"] == "correspondence_small_skew_all"
    assert [mode["mode"] for mode in workload["modes"]] == [
        "cold_cache",
        "warm_cache",
    ]
    assert workload["modes"][0]["correctness_signature"] == (
        workload["modes"][1]["correctness_signature"]
    )


def test_reference_oracle_accepts_supported_hypot_rounding(monkeypatch) -> None:
    matrix = load_correspondence_performance_matrix()
    workload = next(
        item
        for item in matrix.workloads
        if item.benchmark_id == "correspondence_isotropic_annulus_proper"
    )
    baseline = run_workload_trial(
        workload,
        clear_cache=True,
        measure_memory=False,
    )

    monkeypatch.setattr(
        np,
        "hypot",
        lambda x, y: np.sqrt(
            np.asarray(x) * np.asarray(x)
            + np.asarray(y) * np.asarray(y)
        ),
    )
    alternate = run_workload_trial(
        workload,
        clear_cache=True,
        measure_memory=False,
    )

    baseline_qualification = baseline["qualification"]
    alternate_qualification = alternate["qualification"]
    assert baseline_qualification["reference_record_sha256"] == (
        alternate_qualification["reference_record_sha256"]
    )
    assert alternate_qualification["max_abs_strain_reference_error"] <= (
        workload.strain_reference_atol
    )
    assert alternate_qualification["transform_key_sha256"] == (
        baseline_qualification["transform_key_sha256"]
    )
