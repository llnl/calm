"""Dependency-light tests for stable artifact and packaging qualification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from engineering.qualification import check_install_artifacts
from engineering.qualification.check_install_artifacts import (
    _artifact_requirement,
    _artifact_version,
    _sha256,
    _work_root_policy_error,
)
from engineering.qualification.check_installed_package import (
    _assert_installed_module,
)
from engineering.qualification.check_packaging_contract import validate


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_packaging_contract_is_exact_and_current() -> None:
    result = validate()
    assert result["errors"] == []
    assert result["version"] == "1.0.0"
    assert result["requires_python"] == ">=3.10,<3.13"
    assert result["base_dependencies"] == ["numpy", "sqlalchemy"]
    assert result["schema"] == "calm.packaging_contract.v5"
    assert result["license_status"] == "approved"
    assert result["license_expression"] == "MIT"
    assert result["sdist_profile"] == "minimal_installation_source"
    assert result["wheel_profile"] == "installable_package_only"
    assert result["conda_profile"] == "local_source_base_package"
    assert result["conda_source_kind"] == "local_path"
    assert result["source_environment_schema"] == "calm.source_environments.v1"
    assert result["source_environment_recipe_count"] == 4
    assert result["source_environment_provider_count"] == 5
    assert result["minimum_dependency_track"] == [
        "ase",
        "numpy",
        "scipy",
        "spglib",
        "sqlalchemy",
    ]
    constraints = (
        REPO_ROOT
        / "engineering"
        / "qualification"
        / "constraints"
        / "minimum-py310-py312.txt"
    ).read_text(encoding="utf-8")
    assert "numpy==1.26.0" in constraints
    assert "scipy==1.11.2" in constraints


def test_artifact_source_identity_fails_closed_when_status_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git_value(*args: str) -> str | None:
        if args == ("rev-parse", "HEAD"):
            return "abc123"
        return None

    monkeypatch.setattr(check_install_artifacts, "_git_value", fake_git_value)
    assert check_install_artifacts._source_identity() == {
        "git_commit": "abc123",
        "git_dirty": None,
    }


def test_artifact_requirements_select_exact_extra(tmp_path: Path) -> None:
    wheel = tmp_path / "calm-1.0.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    assert _artifact_requirement(wheel, "base") == f"calm @ {wheel.as_uri()}"
    assert _artifact_requirement(wheel, "science") == (
        f"calm[science] @ {wheel.as_uri()}"
    )
    assert _artifact_version() == "1.0.0"
    assert _sha256(wheel) == hashlib.sha256(b"wheel").hexdigest()


def test_installed_smoke_rejects_source_checkout_import() -> None:
    with pytest.raises(RuntimeError, match="source checkout"):
        _assert_installed_module(
            str(REPO_ROOT / "calm" / "__init__.py"),
            REPO_ROOT,
        )


def test_artifact_work_root_accepts_ignored_repository_output() -> None:
    work_root = REPO_ROOT / "build" / "qualification" / "install-artifacts"
    assert _work_root_policy_error(work_root) is None


def test_artifact_work_root_accepts_external_output(tmp_path: Path) -> None:
    assert _work_root_policy_error(tmp_path / "install-artifacts") is None


def test_artifact_work_root_rejects_visible_repository_output() -> None:
    work_root = REPO_ROOT / "work" / "install-artifacts"
    assert _work_root_policy_error(work_root) == (
        "--work-root inside the repository must be beneath a Git-ignored "
        "generated-output directory; use build/qualification/... or a path "
        "outside the checkout"
    )


def test_artifact_work_root_rejects_repository_ancestor() -> None:
    assert _work_root_policy_error(REPO_ROOT) == (
        "--work-root must not be the repository root or one of its ancestors"
    )
    assert _work_root_policy_error(REPO_ROOT.parent) == (
        "--work-root must not be the repository root or one of its ancestors"
    )


def test_artifact_work_root_rejection_precedes_mutation() -> None:
    work_root = REPO_ROOT / "work" / "install-artifacts-policy-test"
    assert not work_root.exists()

    with pytest.raises(SystemExit) as exc_info:
        check_install_artifacts.main(["--work-root", str(work_root)])

    assert exc_info.value.code == 2
    assert not work_root.exists()
