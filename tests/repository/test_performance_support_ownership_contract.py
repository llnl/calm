"""Repository guardrails for shared performance-qualification mechanics."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_ROOT = ROOT / "benchmarks" / "benchmarks"
SUPPORT = BENCHMARK_ROOT / "_performance_support.py"
RUNNERS = (
    BENCHMARK_ROOT / "run_performance_qualification.py",
    BENCHMARK_ROOT / "run_correspondence_performance_qualification.py",
    BENCHMARK_ROOT / "run_registry_performance_qualification.py",
)
CHECKER = ROOT / "engineering" / "qualification" / "check_performance_contract.py"
VALIDATORS = tuple(
    ROOT / "engineering" / "qualification" / "performance_contracts" / name
    for name in ("common.py", "coupled.py", "correspondence.py", "registry.py")
)


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_performance_runners_share_mechanics_without_sharing_oracles() -> None:
    support_tree = ast.parse(SUPPORT.read_text(encoding="utf-8"))
    imported_calm_modules = {
        node.module
        for node in ast.walk(support_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("calm")
    }
    assert imported_calm_modules == set()

    retired_local_mechanics = {
        "_peak_process_bytes",
        "_profile_entries",
        "_worker_environment",
        "_git_text",
        "_git_clean",
        "source_metadata",
        "environment_metadata",
    }
    for runner in RUNNERS:
        text = runner.read_text(encoding="utf-8")
        assert "._performance_support import" in text
        assert not (_function_names(runner) & retired_local_mechanics)

    assert "run_qualification_case" in RUNNERS[0].read_text(encoding="utf-8")
    assert "_reference_generalized_eigenvalues" in RUNNERS[1].read_text(
        encoding="utf-8"
    )
    assert "_portable_oracle_mismatches" in RUNNERS[2].read_text(encoding="utf-8")


def test_performance_checker_delegates_matrix_family_validation() -> None:
    checker_text = CHECKER.read_text(encoding="utf-8")
    checker_tree = ast.parse(checker_text)
    validate = next(
        node
        for node in checker_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate"
    )
    assert validate.end_lineno is not None
    assert validate.end_lineno - validate.lineno + 1 <= 70
    assert "validate_coupled_matrix" in checker_text
    assert "validate_correspondence_matrix" in checker_text
    assert "validate_registry_matrix" in checker_text
    assert all(path.is_file() for path in VALIDATORS)


def test_report_schema_owners_remain_separate() -> None:
    coupled, correspondence, registry = (
        path.read_text(encoding="utf-8") for path in RUNNERS
    )
    assert 'PERFORMANCE_SCHEMA = "calm.compute_performance_qualification/v2"' in coupled
    assert 'REPORT_SCHEMA = "calm.correspondence_performance_qualification/v2"' in correspondence
    assert 'REPORT_SCHEMA = "calm.registry_performance_qualification/v2"' in registry
