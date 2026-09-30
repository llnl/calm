"""Repository contracts for source-checkout environment ownership."""

from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from calm.calculators.registry import default_registry
from engineering.qualification.check_source_environments import validate


ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENTS = ROOT / "environments"
CONTRACT = (
    ROOT
    / "engineering"
    / "architecture"
    / "current-source-environments.json"
)


def test_source_environment_contract_is_exact_and_current() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    result = validate()

    assert result == {
        "errors": [],
        "owned_files": [
            "README.md",
            "calm-chgnet.yml",
            "calm-grace.yml",
            "calm-mace.yml",
            "calm-science.yml",
            "validate_environment.py",
        ],
        "provider_families": ["ase", "chgnet", "grace", "lammps", "mace"],
        "recipes": [
            "calm-chgnet.yml",
            "calm-grace.yml",
            "calm-mace.yml",
            "calm-science.yml",
        ],
        "schema": "calm.source_environments.v1",
    }
    assert payload["provider_profiles"].keys() == dict.fromkeys(
        default_registry().families()
    ).keys()
    assert payload["validation"]["supported_profiles"] == [
        "base",
        "provider",
        "science",
    ]


def test_environment_recipes_are_pyproject_derived_runtime_layers() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    shared = [*project["dependencies"], *project["optional-dependencies"]["science"]]
    expected_provider_requirements = {
        "calm-chgnet.yml": project["optional-dependencies"]["chgnet"],
        "calm-grace.yml": project["optional-dependencies"]["grace"],
        "calm-mace.yml": project["optional-dependencies"]["mace"],
        "calm-science.yml": [],
    }

    for recipe_name, provider_requirements in expected_provider_requirements.items():
        text = (ENVIRONMENTS / recipe_name).read_text(encoding="utf-8")
        assert f"  - python{project['requires-python']}" in text
        assert "  - conda-forge\n  - nodefaults\n" in text
        for requirement in shared:
            assert f"  - {requirement}\n" in text
        for requirement in provider_requirements:
            assert f"      - {requirement}\n" in text
        for excluded in (
            "jupyter",
            "mkdocs",
            "notebook",
            "pytest",
            "matplotlib",
            "pandas",
        ):
            assert excluded not in text


def test_retired_and_unregistered_environment_recipes_are_absent() -> None:
    retired = {
        "calm-base.yml",
        "calm-full.yml",
        "calm-grace-gpu.yml",
        "calm-m3gnet.yml",
        "calm-mattersim.yml",
        "calm-nequip.yml",
        "calm-orb.yml",
        "calm-sevennet.yml",
        "calm-universal.yml",
    }
    duplicate_guides = {"PLATFORMS.md", "POSTINSTALL.md", "QUICKSTART.md"}

    assert all(not (ENVIRONMENTS / name).exists() for name in retired)
    assert all(not (ENVIRONMENTS / name).exists() for name in duplicate_guides)


def test_environment_validator_uses_profile_selection_not_name_inference() -> None:
    source = (ENVIRONMENTS / "validate_environment.py").read_text(encoding="utf-8")

    assert 'choices=("base", "science")' in source
    assert '"--provider"' in source
    assert 'validation["default_profile"]' in source
    assert "CONDA_DEFAULT_ENV" in source
    assert "permitted, so this is informational." in source
    assert "JUPYTER" not in source.upper()
