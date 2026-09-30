"""Repository guardrails for portable registry qualification evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "benchmarks" / "benchmarks" / "run_registry_performance_qualification.py"
MATRIX = ROOT / "engineering" / "qualification" / "registry-performance-matrix.json"


def test_registry_matrix_separates_portable_oracles_from_host_diagnostics() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert matrix["schema"] == "calm.registry_performance_matrix/v2"
    assert matrix["diagnostic_fields"] == ["observed_proposal_trace_sha256"]
    assert "proposal_count" in matrix["correctness_fields"]
    assert "observed_proposal_trace_sha256" not in matrix["correctness_fields"]
    assert all(
        "observed_proposal_trace_sha256" not in workload["expected"]
        for workload in matrix["workloads"]
    )


def test_registry_runner_retains_exact_same_host_proposal_comparison() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert 'REPORT_SCHEMA = "calm.registry_performance_qualification/v2"' in source
    assert 'MATRIX_SCHEMA = "calm.registry_performance_matrix/v2"' in source
    assert '"observed_proposal_trace_sha256": _digest(proposal_values)' in source
    assert "same_host_diagnostic_only" in source
    assert "validate_measurement_equivalence(" in source
    assert "matrix.correctness_fields + matrix.diagnostic_fields" in source
    assert 'modes[0]["correctness_signature"] != modes[1]["correctness_signature"]' in source
