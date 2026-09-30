"""Repository contracts for qualification matrices and API consistency checks."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "engineering" / "qualification"
CORE_MATRIX = QUALIFICATION / "qualification-matrix.json"
PROVIDER_MATRIX = QUALIFICATION / "provider-matrix.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _python_paths(matrix: dict) -> set[str]:
    return {
        token
        for profile in matrix["profiles"].values()
        for check in profile["checks"]
        for token in check["command"]
        if isinstance(token, str) and token.endswith(".py")
    }


def test_core_qualification_matrix_uses_consistency_not_a_freeze() -> None:
    required_files = {
        "qualification-matrix.json",
        "check_public_api_consistency.py",
        "check_public_table_views.py",
        "check_repository_root.py",
        "check_source_environments.py",
        "check_conda_recipe.py",
        "check_install_artifacts.py",
        "check_installed_package.py",
        "check_packaging_contract.py",
        "check_python_distribution_artifacts.py",
        "check_package_organization.py",
        "check_pytest_junit.py",
        "provider-matrix.json",
        "qualify.py",
        "run_numbered_examples.py",
    }
    files = {path.name for path in QUALIFICATION.iterdir() if path.is_file()}
    assert required_files <= files
    assert "beta-contract-freeze.json" not in files
    assert "check_beta_contract_freeze.py" not in files

    matrix = _load(CORE_MATRIX)
    assert matrix["schema_version"] == "calm.qualification_matrix.v3"
    assert matrix["report_schema_version"] == "calm.qualification_report.v3"
    assert matrix["source_policy"] == {
        "require_git_commit": True,
        "require_clean_git": True,
    }
    check_ids = [
        check["id"]
        for profile in matrix["profiles"].values()
        for check in profile["checks"]
    ]
    assert len(check_ids) == len(set(check_ids))
    contracts = {
        check["id"]: check["command"]
        for check in matrix["profiles"]["contracts"]["checks"]
    }
    assert contracts["repository-root-consistency"] == [
        "{python}",
        "engineering/qualification/check_repository_root.py",
    ]
    assert contracts["source-environment-consistency"] == [
        "{python}",
        "engineering/qualification/check_source_environments.py",
    ]
    assert contracts["public-api-consistency"] == [
        "{python}",
        "engineering/qualification/check_public_api_consistency.py",
    ]
    assert contracts["public-table-view-architecture"] == [
        "{python}",
        "engineering/qualification/check_public_table_views.py",
    ]
    assert contracts["packaging-contract"] == [
        "{python}",
        "engineering/qualification/check_packaging_contract.py",
    ]
    assert "conda-recipe" in contracts["compile-source-tests-examples"]
    assert "environments" in contracts["compile-source-tests-examples"]
    assert contracts["package-organization-consistency"] == [
        "{python}",
        "engineering/qualification/check_package_organization.py",
    ]
    assert contracts["ruff-typing-modernization"] == [
        "{python}",
        "-m",
        "ruff",
        "check",
        "--config",
        "engineering/qualification/ruff-typing-modernization.toml",
        "@engineering/qualification/typing-modernization-files.txt",
    ]
    assert contracts["ruff-complete-tree"] == [
        "{python}",
        "-m",
        "ruff",
        "check",
        ".",
    ]
    assert "beta-contract-freeze" not in contracts
    for relative in _python_paths(matrix):
        assert (ROOT / relative).is_file(), relative


def test_core_matrix_preserves_platform_ci_and_skip_policy() -> None:
    matrix = _load(CORE_MATRIX)
    assert set(matrix["profiles"]) == set(matrix["qualification_contract"]["required_profiles"])
    cells = {
        (cell["platform"], cell["architecture"], cell["python"]): cell
        for cell in matrix["cells"]
    }
    for platform_name, architecture, tier in (
        ("macos", "arm64", "primary"),
        ("linux", "x86_64", "secondary"),
    ):
        for python_minor in ("3.10", "3.11", "3.12"):
            assert cells[(platform_name, architecture, python_minor)]["tier"] == tier

    contract = matrix["qualification_contract"]
    assert contract["package_version"] == "1.0.0"
    assert contract["requires_python"] == ">=3.10,<3.13"
    assert contract["dependency_tracks"] == ["current", "minimum-direct"]

    science = {
        check["id"]: check["command"]
        for check in matrix["profiles"]["science"]["checks"]
    }
    assert "--junitxml" in science["full-dependency-enabled-suite"]
    assert "not real_backend" in science["full-dependency-enabled-suite"]
    assert science["science-skip-allowlist"].count("--allow-skipped") == 1

    examples = matrix["profiles"]["examples"]["checks"][0]
    assert "tensorpotential" in examples["requires_modules"]
    packaging = {
        check["id"]: check["command"]
        for check in matrix["profiles"]["packaging"]["checks"]
    }
    assert set(packaging) == {
        "wheel-sdist-current-dependencies",
        "wheel-sdist-minimum-dependencies",
    }
    assert "current" in packaging["wheel-sdist-current-dependencies"]
    assert "minimum" in packaging["wheel-sdist-minimum-dependencies"]
    for check in matrix["profiles"]["packaging"]["checks"]:
        assert check["requires_distributions"] == ["build", "twine"]
        assert "requires_modules" not in check

    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert "qualification:linux-py311-contract:" in ci
    assert "--profile contracts" in ci
    assert "requirements-test-py311.txt" in ci

    requirements = (
        ROOT / "engineering" / "ci" / "requirements-test-py311.txt"
    ).read_text(encoding="utf-8")
    assert ".[science,dataframe,plot]" in requirements


def test_provider_qualification_remains_separate() -> None:
    core = _load(CORE_MATRIX)
    providers = {item["family"]: item for item in core["providers"]}
    assert providers["ase"]["qualification_matrix"] == (
        "engineering/qualification/provider-matrix.json"
    )
    matrix = _load(PROVIDER_MATRIX)
    assert matrix["source_policy"] == {
        "require_git_commit": True,
        "require_clean_git": True,
    }
    assert {"calm", "numpy", "sqlalchemy", "ase"} <= set(
        matrix["evidence_distributions"]
    )
    assert matrix["provider_contract"]["family"] == "ase"
    assert matrix["provider_contract"]["model"] == "EMT"
    for relative in _python_paths(matrix):
        assert (ROOT / relative).is_file(), relative
