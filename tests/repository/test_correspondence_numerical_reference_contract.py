"""Repository guardrails for portable correspondence numerical evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "benchmarks" / "benchmarks" / "run_correspondence_performance_qualification.py"
MATRIX = ROOT / "engineering" / "qualification" / "correspondence-performance-matrix.json"


def test_correspondence_runner_owns_portable_numerical_reference() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'REPORT_SCHEMA = "calm.correspondence_performance_qualification/v2"' in source
    assert 'MATRIX_SCHEMA = "calm.correspondence_performance_matrix/v2"' in source
    assert "REFERENCE_DECIMAL_PRECISION = 60" in source
    assert "REFERENCE_DECIMAL_DIGITS = 45" in source
    assert "_reference_generalized_eigenvalues" in source
    assert "reference_record_sha256" in source
    assert "observed_record_sha256" in source
    assert "max_abs_strain_reference_error" in source


def test_correspondence_matrix_separates_portable_and_diagnostic_evidence() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert matrix["schema"] == "calm.correspondence_performance_matrix/v2"
    assert "reference_record_sha256" in matrix["correctness_fields"]
    assert "record_sha256" not in matrix["correctness_fields"]
    assert all(
        workload["strain_reference_atol"] == 1e-10
        for workload in matrix["workloads"]
    )
