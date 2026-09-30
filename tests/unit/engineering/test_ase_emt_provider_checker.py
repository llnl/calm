"""Dependency-light tests for the ASE EMT provider evidence checker."""

from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKER_PATH = (
    REPO_ROOT / "engineering" / "qualification" / "check_ase_emt_provider.py"
)


def _checker_module():
    spec = importlib.util.spec_from_file_location(
        "check_ase_emt_provider",
        CHECKER_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identity_paths_find_nested_ase_emt_cpu_specs() -> None:
    checker = _checker_module()
    payload = {
        "configuration": {
            "calculator": {
                "family": "ase",
                "model": "EMT",
                "device": "cpu",
            }
        },
        "backends": [
            {
                "identity": {
                    "calculator_specs": {
                        "target": {
                            "family": "ASE",
                            "model": "emt",
                        }
                    }
                }
            }
        ],
    }

    matches = checker._identity_paths(payload)

    assert "root.configuration.calculator" in matches
    assert "root.backends[0].identity.calculator_specs.target" in matches


def test_run_check_records_success_and_failure_without_optional_dependencies(
    tmp_path: Path,
) -> None:
    checker = _checker_module()

    passed = checker._run_check(
        "construction",
        lambda work_root: {"work_root": str(work_root)},
        work_root=tmp_path,
    )

    def fail(_work_root: Path):
        raise RuntimeError("provider failure")

    failed = checker._run_check(
        "energy",
        fail,
        work_root=tmp_path,
    )

    assert passed["status"] == "passed"
    assert passed["details"]["work_root"] == str(tmp_path)
    assert failed["status"] == "failed"
    assert failed["error_type"] == "RuntimeError"
    assert failed["error"] == "provider failure"
    assert "provider failure" in failed["traceback"]
