"""Dependency-light execution tests for the qualification harness."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

from engineering.qualification.qualify import (
    _missing_prerequisites,
    _source_policy_violations,
    _source_stability_violations,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS = REPO_ROOT / "engineering" / "qualification" / "qualify.py"
MATRIX = REPO_ROOT / "engineering" / "qualification" / "qualification-matrix.json"


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS), *arguments],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _minimal_matrix(
    command: list[str],
    *,
    cell_python: str | None = None,
    provider: bool = False,
) -> dict:
    python_minor = cell_python or f"{sys.version_info.major}.{sys.version_info.minor}"
    system = platform.system().lower()
    platform_name = "macos" if system == "darwin" else system
    architecture = platform.machine().lower()
    architecture = {"amd64": "x86_64", "aarch64": "arm64"}.get(
        architecture,
        architecture,
    )
    matrix = {
        "schema_version": (
            "calm.provider_qualification_matrix.v1"
            if provider
            else "calm.qualification_matrix.v2"
        ),
        "report_schema_version": (
            "calm.provider_qualification_report.v1"
            if provider
            else "calm.qualification_report.v2"
        ),
        "profiles": {
            "smoke": {
                "description": "test profile",
                "checks": [{"id": "smoke-check", "command": command}],
            }
        },
        "cells": [
            {
                "id": "current",
                "platform": platform_name,
                "architecture": architecture,
                "python": python_minor,
                "profiles": ["smoke"],
                "required": True,
                "tier": "primary",
            }
        ],
    }
    if provider:
        matrix["provider_contract"] = {
            "family": "demo",
            "model": "v1",
            "device": "cpu",
            "required_evidence": ["construction"],
        }
    return matrix


def test_list_and_dry_run_do_not_require_optional_tools(tmp_path: Path) -> None:
    listed = _run("--list")
    assert listed.returncode == 0
    assert "macos-arm64-py311-core" in listed.stdout
    assert "Current environment:" in listed.stdout

    output = tmp_path / "plan.json"
    planned = _run(
        "--matrix",
        str(MATRIX),
        "--profile",
        "contracts",
        "--dry-run",
        "--output",
        str(output),
    )
    assert planned.returncode == 0, planned.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "planned"
    assert report["cell_qualified"] is False
    assert all(check["status"] == "planned" for check in report["checks"])


def test_provider_matrix_uses_provider_qualification_flag(tmp_path: Path) -> None:
    matrix_path = tmp_path / "provider-matrix.json"
    matrix_path.write_text(
        json.dumps(
            _minimal_matrix(
                ["{python}", "-c", "print('provider qualified')"],
                provider=True,
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "provider-report.json"
    completed = _run(
        "--matrix",
        str(matrix_path),
        "--cell",
        "current",
        "--output",
        str(output),
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema_version"] == "calm.provider_qualification_report.v1"
    assert report["qualification_kind"] == "provider"
    assert report["provider_contract"]["family"] == "demo"
    assert report["provider_qualified"] is True
    assert "cell_qualified" not in report


def test_provider_dry_run_never_claims_qualification(tmp_path: Path) -> None:
    matrix_path = tmp_path / "provider-matrix.json"
    matrix_path.write_text(
        json.dumps(
            _minimal_matrix(
                ["{python}", "-c", "print('must not execute')"],
                provider=True,
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "provider-plan.json"
    completed = _run(
        "--matrix",
        str(matrix_path),
        "--cell",
        "current",
        "--dry-run",
        "--output",
        str(output),
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "planned"
    assert report["provider_qualified"] is False
    assert report["checks"][0]["status"] == "planned"


def test_current_cell_selects_exact_environment(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(_minimal_matrix(["{python}", "-c", "print('current')"])),
        encoding="utf-8",
    )
    output = tmp_path / "current.json"
    completed = _run(
        "--matrix",
        str(matrix_path),
        "--current-cell",
        "--output",
        str(output),
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["selection"]["cell"] == "current"
    assert report["selection"]["cell_tier"] == "primary"
    assert report["selection"]["selected_from_current_environment"] is True
    assert report["selection"]["complete_cell"] is True
    assert report["cell_qualified"] is True


def test_current_cell_rejects_output_named_for_another_cell(tmp_path: Path) -> None:
    matrix = _minimal_matrix(["{python}", "-c", "print('current')"])
    current = matrix["cells"][0]
    current_id = (
        f"{current['platform']}-{current['architecture']}-"
        f"py{str(current['python']).replace('.', '')}-core"
    )
    current["id"] = current_id
    other_id = f"{current['platform']}-{current['architecture']}-py00-core"
    matrix["cells"].append(
        {
            **current,
            "id": other_id,
            "python": "0.0",
        }
    )
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    output = tmp_path / f"{other_id.removesuffix('-core')}.json"

    completed = _run(
        "--matrix",
        str(matrix_path),
        "--current-cell",
        "--output",
        str(output),
    )

    assert completed.returncode == 2
    assert "identifies a different cell" in completed.stderr
    assert not output.exists()


def test_complete_cell_passes_and_writes_logs(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(_minimal_matrix(["{python}", "-c", "print('qualified')"])),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    completed = _run(
        "--matrix",
        str(matrix_path),
        "--cell",
        "current",
        "--output",
        str(output),
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["selection"]["complete_cell"] is True
    assert report["cell_qualified"] is True
    check = report["checks"][0]
    stdout_log = output.parent / f"{output.stem}.d" / check["stdout_log"]
    content = stdout_log.read_bytes()
    assert content.decode().strip() == "qualified"
    assert check["stdout_sha256"] == hashlib.sha256(content).hexdigest()
    assert check["stdout_size_bytes"] == len(content)
    assert len(report["matrix_sha256"]) == 64


def test_failed_check_returns_nonzero_and_preserves_stderr(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            _minimal_matrix(
                [
                    "{python}",
                    "-c",
                    (
                        "import sys; print('failure detail', file=sys.stderr); "
                        "raise SystemExit(7)"
                    ),
                ]
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    completed = _run(
        "--matrix",
        str(matrix_path),
        "--profile",
        "smoke",
        "--output",
        str(output),
    )
    assert completed.returncode == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["cell_qualified"] is False
    assert report["checks"][0]["returncode"] == 7
    stderr_log = output.parent / f"{output.stem}.d" / report["checks"][0]["stderr_log"]
    assert "failure detail" in stderr_log.read_text(encoding="utf-8")


def test_cell_environment_mismatch_fails_before_commands_run(tmp_path: Path) -> None:
    matrix_path = tmp_path / "matrix.json"
    matrix_path.write_text(
        json.dumps(
            _minimal_matrix(
                ["{python}", "-c", "raise RuntimeError('must not execute')"],
                cell_python="0.0",
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"
    completed = _run(
        "--matrix",
        str(matrix_path),
        "--cell",
        "current",
        "--output",
        str(output),
    )
    assert completed.returncode == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["checks"] == []
    assert any(item.startswith("python:") for item in report["cell_mismatches"])


def test_junit_skip_checker_enforces_the_allowlist(tmp_path: Path) -> None:
    checker = REPO_ROOT / "engineering" / "qualification" / "check_pytest_junit.py"
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<testsuite tests='1' skipped='1'>
  <testcase file='tests/test_sample.py' name='test_optional'>
    <skipped message='expected environment gate'/>
  </testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    rejected = subprocess.run(
        [sys.executable, str(checker), str(junit)],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert rejected.returncode == 1
    assert "Unexpected skipped tests" in rejected.stderr

    accepted = subprocess.run(
        [
            sys.executable,
            str(checker),
            str(junit),
            "--allow-skipped",
            "tests/test_sample.py::test_optional",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert accepted.returncode == 0


def test_v3_source_policy_detects_dirty_or_unidentified_source() -> None:
    matrix = {
        "source_policy": {
            "require_git_commit": True,
            "require_clean_git": True,
        }
    }
    assert _source_policy_violations(
        matrix, {"git_commit": "abc123", "git_dirty": False}
    ) == []
    assert _source_policy_violations(
        matrix, {"git_commit": None, "git_dirty": True}
    ) == [
        "source tree has no resolvable Git commit",
        "source tree contains uncommitted changes",
    ]


def test_default_matrix_binds_release_evidence_to_clean_source() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == "calm.qualification_matrix.v3"
    assert matrix["report_schema_version"] == "calm.qualification_report.v3"
    assert matrix["source_policy"] == {
        "require_git_commit": True,
        "require_clean_git": True,
    }
    assert {"calm", "numpy", "sqlalchemy", "ase", "ruff", "mkdocs"} <= set(
        matrix["evidence_distributions"]
    )


def test_distribution_prerequisites_do_not_accept_shadow_modules(monkeypatch) -> None:
    from importlib import metadata

    def missing(_name: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(metadata, "version", missing)
    assert _missing_prerequisites(
        {"requires_distributions": ["build", "twine"]}
    ) == ["distribution:build", "distribution:twine"]


def test_source_policy_fails_closed_when_git_status_is_unavailable() -> None:
    matrix = {
        "source_policy": {
            "require_git_commit": True,
            "require_clean_git": True,
        }
    }
    environment = {"git_commit": "abc123", "git_dirty": None}
    assert _source_policy_violations(matrix, environment) == [
        "source tree Git status is unavailable"
    ]


def test_source_stability_detects_commit_changes() -> None:
    assert _source_stability_violations(
        {"git_commit": "before"},
        {"git_commit": "after"},
    ) == ["source Git commit changed during qualification"]
