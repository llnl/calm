"""Repository contracts for Python distribution and approved MIT licensing."""

from __future__ import annotations

import json
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from engineering.qualification.check_packaging_contract import validate


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    ROOT / "engineering" / "architecture" / "current-python-distribution.json"
)


def _job_body(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}:\n(?P<body>.*?)(?=^[^ #\n][^\n]*:\n|\Z)",
        text,
    )
    assert match is not None, name
    return match.group("body")


def test_distribution_contract_owns_profiles_and_mit_license_status() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "calm.python_distribution.v2"
    assert payload["license_policy"] == {
        "copyright_holder": "Lawrence Livermore National Security, LLC",
        "copyright_year": 2026,
        "expression": "MIT",
        "files": {
            "LICENSE": (
                "41e565493bf7098b65db9896b21a02a7ad55cea63e542dfc1d337c5362623e81"
            ),
            "NOTICE": (
                "1c03a03406e4fc284f812456ef8a4866b8d5a94f57a85a8be7295a91b75c1918"
            ),
        },
        "status": "approved",
    }
    assert payload["wheel"]["profile"] == "installable_package_only"
    assert payload["wheel"]["package_file_suffixes"] == [".json", ".py"]
    assert payload["sdist"]["profile"] == "minimal_installation_source"
    assert payload["sdist"]["manifest_directives"] == [
        ["include", "LICENSE"],
        ["include", "NOTICE"],
        ["include", "README.md"],
        ["prune", "tests"],
    ]
    assert payload["sdist"]["root_directories"] == ["calm", "calm.egg-info"]
    assert payload["sdist"]["source_root_files"] == [
        "LICENSE",
        "MANIFEST.in",
        "NOTICE",
        "README.md",
        "pyproject.toml",
    ]
    assert payload["wheel"]["dist_info_files"] == [
        "METADATA",
        "RECORD",
        "WHEEL",
        "licenses/LICENSE",
        "licenses/NOTICE",
        "top_level.txt",
    ]


def test_project_and_conda_metadata_publish_the_same_mit_license() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    assert not any(
        classifier.startswith("License ::")
        for classifier in project.get("classifiers", ())
    )
    assert pyproject["tool"]["setuptools"]["include-package-data"] is False
    assert pyproject["tool"]["setuptools"]["package-data"] == {
        "calm": ["data/tutorials/*.json"]
    }

    conda = (ROOT / "conda-recipe" / "meta.yaml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*license:\s+MIT$", conda)
    assert re.search(r"(?m)^\s*license_family:\s+MIT$", conda)
    assert "  license_file:\n    - LICENSE\n    - NOTICE\n" in conda
    conda_readme = (ROOT / "conda-recipe" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "licensed under the mit license" in conda_readme.lower()

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: MIT" in readme
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "NOTICE").is_file()


def test_manifest_declares_only_the_owned_minimal_source_directives() -> None:
    text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    directives = [
        line
        for line in text.splitlines()
        if line and not line.startswith("#")
    ]

    assert directives == [
        "include LICENSE",
        "include NOTICE",
        "include README.md",
        "prune tests",
    ]
    assert "include public_api.md" not in text
    assert "recursive-include docs" not in text


def test_packaging_checker_projects_the_distribution_policy() -> None:
    result = validate()

    assert result["errors"] == []
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


def test_ci_cleans_build_outputs_and_checks_contents_before_twine() -> None:
    text = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    static = (
        "$CALM_CI_PYTHON "
        "engineering/qualification/check_packaging_contract.py"
    )
    build = "$CALM_CI_PYTHON -m build"
    artifact = (
        "$CALM_CI_PYTHON engineering/qualification/"
        "check_python_distribution_artifacts.py --dist-dir dist"
    )
    twine = "$CALM_CI_PYTHON -m twine check dist/*"

    for job in ("build:dist", "dist:release"):
        body = _job_body(text, job)
        assert "rm -rf build dist calm.egg-info" in body
        for command in (static, build, artifact, twine):
            assert command in body
        assert body.index(static) < body.index(build)
        assert body.index(build) < body.index(artifact) < body.index(twine)


def test_packaging_profile_names_exact_content_validation() -> None:
    matrix = json.loads(
        (ROOT / "engineering" / "qualification" / "qualification-matrix.json")
        .read_text(encoding="utf-8")
    )

    assert "exact-content validation" in matrix["profiles"]["packaging"][
        "description"
    ]


def test_install_artifact_qualification_runs_the_same_content_checker() -> None:
    text = (
        ROOT / "engineering" / "qualification" / "check_install_artifacts.py"
    ).read_text(encoding="utf-8")

    assert "check_python_distribution_artifacts.py" in text
    assert '"schema": "calm.install_artifact_qualification.v3"' in text
    assert 'report["distribution_artifacts"]' in text
