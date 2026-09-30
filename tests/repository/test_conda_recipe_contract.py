"""Repository contracts for the internal CALM conda package recipe."""

from __future__ import annotations

import json
from pathlib import Path

from engineering.qualification.check_conda_recipe import validate


ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "conda-recipe"
CONTRACT = (
    ROOT / "engineering" / "architecture" / "current-conda-package.json"
)


def test_conda_recipe_contract_is_exact_and_current() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    result = validate()

    assert result["errors"] == []
    assert result["schema"] == "calm.conda_package.v1"
    assert result["profile"] == "local_source_base_package"
    assert result["source_kind"] == "local_path"
    assert result["build_authority"] == "meta_yaml_script"
    assert result["build_number"] == 0
    assert result["license_expression"] == "MIT"
    assert result["license_files"] == ["LICENSE", "NOTICE"]
    assert result["run_requirements"] == [
        "python >=3.10,<3.13",
        "numpy >=1.26,<3",
        "sqlalchemy >=2.0,<3",
    ]
    assert payload["dependency_policy"]["science"] == "not_bundled"
    assert payload["publication"] == {
        "release_recipe_required": True,
        "source_digest_required": True,
        "status": "internal_qualification_only",
    }


def test_conda_recipe_has_one_build_authority_and_exact_files() -> None:
    assert sorted(path.name for path in RECIPE.iterdir() if path.is_file()) == [
        "README.md",
        "meta.yaml",
        "run_test.py",
    ]
    assert not (RECIPE / "build.sh").exists()
    assert not (RECIPE / "bld.bat").exists()

    metadata = (RECIPE / "meta.yaml").read_text(encoding="utf-8")
    assert metadata.count("script:") == 1
    assert "  number: 0\n" in metadata
    assert "--no-deps --no-build-isolation" in metadata
    assert "\n    - scipy " not in metadata
    assert "\n    - ase " not in metadata
    assert "\n    - spglib " not in metadata
    assert "pytest" not in metadata
    assert "mkdocs" not in metadata
    assert "  license: MIT\n" in metadata
    assert "  license_family: MIT\n" in metadata
    assert "  license_file:\n    - LICENSE\n    - NOTICE\n" in metadata


def test_conda_package_smoke_is_recipe_owned_and_dependency_light() -> None:
    source = (RECIPE / "run_test.py").read_text(encoding="utf-8")

    assert "conda-meta" in source
    assert "from __future__ import" not in source
    assert "EXPECTED_DEPENDENCIES" in source
    assert "EXPECTED_BUILD_NUMBER = 0" in source
    assert "callable(calm.open_project)" in source
    assert "project.path is not None" in source
    assert "pytest" not in source


def test_conda_readme_marks_local_and_publication_boundaries() -> None:
    text = " ".join(
        (RECIPE / "README.md").read_text(encoding="utf-8").split()
    ).lower()

    assert "internal local-source qualification recipe" in text
    assert "science dependencies are not bundled" in text
    assert "clean commit" in text
    assert "immutable source archive" in text
    assert "sha-256" in text
    assert "not a public conda-forge recipe" in text
    assert "licensed under the mit license" in text


def test_greenfield_contract_keeps_conda_maintenance_out_of_user_installation() -> None:
    documentation = json.loads(
        (ROOT / "engineering" / "architecture" / "current-documentation-site.json").read_text(
            encoding="utf-8"
        )
    )
    requirement = documentation["content_requirements"]["installation"]
    assert requirement["owner"] == "install.md"
    assert requirement["must_distinguish"] == [
        "base dependencies",
        "science dependencies",
        "calculator-provider environments",
    ]
    assert requirement["must_not_publish"] == [
        "conda-recipe maintainer procedure as a user installation path"
    ]
    assert "conda-recipe/" not in (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
