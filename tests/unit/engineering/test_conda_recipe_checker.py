"""Dependency-light mutation tests for the CALM conda recipe contract."""

from __future__ import annotations

from importlib import util
import json
from pathlib import Path
import shutil
import subprocess
from types import ModuleType

import pytest

from engineering.qualification.check_conda_recipe import validate


ROOT = Path(__file__).resolve().parents[3]
REQUIRED_FILES = (
    "LICENSE",
    "NOTICE",
    "pyproject.toml",
    "conda-recipe/README.md",
    "conda-recipe/meta.yaml",
    "conda-recipe/run_test.py",
    "engineering/architecture/current-conda-package.json",
    "engineering/architecture/current-python-distribution.json",
)


def _repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for relative in REQUIRED_FILES:
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    return root


def _validate(root: Path) -> dict[str, object]:
    return validate(
        repo_root=root,
        contract_path=(
            root
            / "engineering"
            / "architecture"
            / "current-conda-package.json"
        ),
    )


def _run_test_module() -> ModuleType:
    path = ROOT / "conda-recipe" / "run_test.py"
    spec = util.spec_from_file_location("calm_conda_run_test", path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record() -> dict[str, object]:
    return {
        "name": "calm",
        "version": "1.0.0",
        "build_number": 0,
        "subdir": "noarch",
        "depends": [
            "numpy >=1.26,<3",
            "python >=3.10,<3.13",
            "sqlalchemy >=2.0,<3",
        ],
        "files": [
            "site-packages/calm/__init__.py",
            "site-packages/calm/__pycache__/__init__.cpython-312.pyc",
            "site-packages/calm/public/project.py",
            "site-packages/calm/public/__pycache__/project.cpython-312.pyc",
            "site-packages/calm-1.0.0.dist-info/METADATA",
        ],
    }


def test_conda_checker_accepts_the_current_recipe() -> None:
    assert validate()["errors"] == []


def test_conda_checker_rejects_a_competing_build_script(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "conda-recipe" / "build.sh").write_text(
        "python -m pip install .\n",
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("owned_files" in error for error in result["errors"])


def test_conda_checker_rejects_build_script_drift(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    recipe = root / "conda-recipe" / "meta.yaml"
    recipe.write_text(
        recipe.read_text(encoding="utf-8").replace(" --no-deps", ""),
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("canonical" in error for error in result["errors"])


def test_conda_checker_rejects_science_in_the_base_run_set(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(
        text.replace(
            '    "sqlalchemy>=2.0,<3",\n]',
            '    "sqlalchemy>=2.0,<3",\n    "scipy>=1.11.2,<2",\n]',
            1,
        ),
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("import-light base package" in error for error in result["errors"])


def test_conda_checker_rejects_license_expression_drift(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    contract = (
        root
        / "engineering"
        / "architecture"
        / "current-python-distribution.json"
    )
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["license_policy"]["expression"] = "Apache-2.0"
    contract.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    result = _validate(root)

    assert any("MIT expression" in error for error in result["errors"])


def test_conda_checker_rejects_license_file_drift(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    (root / "LICENSE").write_text("tampered\n", encoding="utf-8")

    result = _validate(root)

    assert any("license file digest mismatch" in error for error in result["errors"])


def test_conda_checker_rejects_future_import_in_run_test(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    run_test = root / "conda-recipe" / "run_test.py"
    run_test.write_text(
        run_test.read_text(encoding="utf-8").replace(
            "from importlib import metadata\n",
            "from __future__ import annotations\n\n"
            "from importlib import metadata\n",
            1,
        ),
        encoding="utf-8",
    )

    result = _validate(root)

    assert any(
        "must not contain __future__ imports" in error
        for error in result["errors"]
    )


def test_conda_checker_rejects_run_test_contract_drift(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    run_test = root / "conda-recipe" / "run_test.py"
    run_test.write_text(
        run_test.read_text(encoding="utf-8").replace(
            '{"numpy", "python", "sqlalchemy"}',
            '{"numpy", "python"}',
            1,
        ),
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("run_test.py constants" in error for error in result["errors"])


def test_conda_run_test_accepts_the_reviewed_package_record() -> None:
    module = _run_test_module()

    projection = module._record_projection(_record())

    assert projection["dependency_names"] == ["numpy", "python", "sqlalchemy"]
    assert "calm/__init__.py" in projection["installed_site_package_files"]


def test_conda_run_test_rejects_science_dependency_bundling() -> None:
    module = _run_test_module()
    record = _record()
    record["depends"] = [*record["depends"], "scipy >=1.11.2,<2"]

    with pytest.raises(AssertionError):
        module._record_projection(record)


def test_conda_run_test_rejects_foreign_site_package_content() -> None:
    module = _run_test_module()
    record = _record()
    record["files"] = [
        *record["files"],
        "site-packages/tests/test_accidental.py",
    ]

    with pytest.raises(AssertionError):
        module._record_projection(record)
