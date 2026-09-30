from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPOSITORY_ROOT / "engineering" / "qualification" / "performance-matrix.json"
CORRESPONDENCE_MATRIX = (
    REPOSITORY_ROOT
    / "engineering"
    / "qualification"
    / "correspondence-performance-matrix.json"
)
REGISTRY_MATRIX = (
    REPOSITORY_ROOT
    / "engineering"
    / "qualification"
    / "registry-performance-matrix.json"
)
README = REPOSITORY_ROOT / "benchmarks" / "README.md"


def test_performance_contract_checker_accepts_the_reviewed_matrix() -> None:
    completed = subprocess.run(
        [sys.executable, "engineering/qualification/check_performance_contract.py"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result["schema"] == "calm.performance_contract_check/v1"
    assert result["matrix_schema"] == "calm.compute_performance_matrix/v1"
    assert result["correspondence_matrix_schema"] == (
        "calm.correspondence_performance_matrix/v2"
    )
    assert result["workload_count"] == 7
    assert result["correspondence_workload_count"] == 3
    assert result["registry_matrix_schema"] == "calm.registry_performance_matrix/v2"
    assert result["registry_workload_count"] == 3
    assert result["registry_profile_workloads"] == [
        "registry_large_2400_atoms_200_steps",
        "registry_medium_600_atoms_400_steps",
    ]
    assert result["correspondence_profile_workloads"] == [
        "correspondence_anisotropic_skew_all",
        "correspondence_isotropic_annulus_proper",
    ]
    assert result["errors"] == []


def test_performance_matrix_owns_cold_warm_and_exact_correctness_evidence() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema"] == "calm.compute_performance_matrix/v1"
    assert matrix["roadmap_series"] == "0337"
    assert matrix["update"] == "0337a"
    assert matrix["default_repeats"] >= 3
    assert matrix["default_memory_repeats"] >= 1
    assert matrix["default_warmup_runs"] >= 1
    assert all(
        workload["modes"] == ["cold_process", "warm_process"]
        for workload in matrix["workloads"]
    )
    assert {
        "pair_key_sha256",
        "pair_identity_sha256",
        "class_count",
        "source_count_total",
        "primitive_classes_created",
    } <= set(matrix["correctness_fields"])



def test_correspondence_matrix_owns_direct_exact_funnel_evidence() -> None:
    matrix = json.loads(CORRESPONDENCE_MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema"] == "calm.correspondence_performance_matrix/v2"
    assert matrix["roadmap_series"] == "0337"
    assert matrix["update"] == "0337d"
    assert matrix["default_repeats"] >= 3
    assert {
        "transform_key_sha256",
        "reference_record_sha256",
        "column_pairs_tested",
        "unimodular_states_tested",
        "strain_admissible_states",
    } <= set(matrix["correctness_fields"])
    by_id = {workload["id"]: workload for workload in matrix["workloads"]}
    assert by_id["correspondence_isotropic_annulus_proper"]["expected"][
        "column_pairs_tested"
    ] == 1_597_696
    assert by_id["correspondence_anisotropic_skew_all"]["expected"][
        "column_pairs_tested"
    ] == 667_000
    assert all(
        workload["strain_reference_atol"] == 1e-10
        for workload in by_id.values()
    )
    assert all(
        "reference_record_sha256" in workload["expected"]
        and "record_sha256" not in workload["expected"]
        for workload in by_id.values()
    )

def test_registry_matrix_owns_fixed_seed_preparation_evidence() -> None:
    matrix = json.loads(REGISTRY_MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema"] == "calm.registry_performance_matrix/v2"
    assert matrix["roadmap_series"] == "0337"
    assert matrix["update"] == "0337e"
    assert matrix["default_repeats"] >= 3
    assert {
        "proposal_count",
        "trajectory_sha256",
        "score_trace_sha256",
        "objective_evaluations",
        "atom_count",
    } <= set(matrix["correctness_fields"])
    by_id = {workload["id"]: workload for workload in matrix["workloads"]}
    assert by_id["registry_medium_600_atoms_400_steps"]["n_steps"] == 400
    assert by_id["registry_large_2400_atoms_200_steps"]["atoms_per_slab"] == 1200
    assert all(workload["expected"] for workload in by_id.values())
    assert matrix["diagnostic_fields"] == ["observed_proposal_trace_sha256"]
    assert all(
        "observed_proposal_trace_sha256" not in workload["expected"]
        for workload in by_id.values()
    )


def test_performance_documentation_defines_interpretable_evidence() -> None:
    readme = README.read_text(encoding="utf-8")
    assert "python -m benchmarks.run_performance_qualification" in readme
    assert "cold_process" in readme
    assert "warm_process" in readme
    assert "same-host" in readme
    assert "--require-clean" in readme
    assert "pair_key_sha256" in readme
    assert "peak_process_bytes" in readme
    assert "peak_python_bytes" in readme
    assert "python -m benchmarks.run_correspondence_performance_qualification" in readme
    assert "cold_cache" in readme
    assert "warm_cache" in readme
    assert "determinant_chunks" in readme
    assert "reference_record_sha256" in readme
    assert "observed_record_sha256" in readme
    assert "strain_reference_atol=1e-10" in readme
    assert "python -m benchmarks.run_registry_performance_qualification" in readme
    assert "rebuild_each_evaluation" in readme
    assert "prepared_once" in readme
