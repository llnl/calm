"""Dependency-light mutation tests for source-environment ownership."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from engineering.qualification.check_source_environments import validate


ROOT = Path(__file__).resolve().parents[3]
REQUIRED_FILES = (
    ".gitignore",
    "pyproject.toml",
    "environments/README.md",
    "environments/calm-chgnet.yml",
    "environments/calm-grace.yml",
    "environments/calm-mace.yml",
    "environments/calm-science.yml",
    "environments/validate_environment.py",
    "engineering/architecture/current-source-environments.json",
    "engineering/qualification/qualification-matrix.json",
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
            / "current-source-environments.json"
        ),
    )


def test_source_environment_checker_accepts_the_current_tree() -> None:
    assert validate()["errors"] == []


def test_source_environment_checker_ignores_generated_bytecode(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    generated = root / "environments" / "__pycache__"
    generated.mkdir()
    (generated / "validator.cpython-312.pyc").write_bytes(b"generated")

    assert _validate(root)["errors"] == []


def test_source_environment_checker_rejects_an_unowned_recipe(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    (root / "environments" / "calm-full.yml").write_text(
        "name: calm-full\n",
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("files must exactly match ownership" in error for error in result["errors"])


def test_source_environment_checker_rejects_recipe_drift(tmp_path: Path) -> None:
    root = _repository(tmp_path)
    recipe = root / "environments" / "calm-science.yml"
    recipe.write_text(
        recipe.read_text(encoding="utf-8").replace(
            "scipy>=1.11.2,<2",
            "scipy>=1.12,<2",
        ),
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("exact pyproject-derived recipe" in error for error in result["errors"])


def test_source_environment_checker_rejects_dependency_projection_drift(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            '  "spglib>=2.6,<3"',
            '  "spglib>=2.7,<3"',
            1,
        ),
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("exact pyproject-derived recipe" in error for error in result["errors"])


def test_source_environment_checker_rejects_provider_registration_drift(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    matrix = root / "engineering" / "qualification" / "qualification-matrix.json"
    payload = json.loads(matrix.read_text(encoding="utf-8"))
    payload["providers"] = [
        item for item in payload["providers"] if item["family"] != "mace"
    ]
    matrix.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    result = _validate(root)

    assert any("must match registered qualification families" in error for error in result["errors"])


def test_source_environment_checker_rejects_retired_recipe_documentation(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    readme = root / "environments" / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nUse the retired calm-full.yml bundle.\n",
        encoding="utf-8",
    )

    result = _validate(root)

    assert any("must not reference retired 'calm-full.yml'" in error for error in result["errors"])


def test_source_environment_checker_rejects_legacy_validator_logic(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path)
    validator = root / "environments" / "validate_environment.py"
    validator.write_text(
        validator.read_text(encoding="utf-8")
        + "\n# legacy calm-base environment detection\n",
        encoding="utf-8",
    )

    result = _validate(root)

    assert any(
        "must not retain legacy marker 'calm-base'" in error
        for error in result["errors"]
    )
