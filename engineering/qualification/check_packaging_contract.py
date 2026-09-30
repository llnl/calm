#!/usr/bin/env python3
"""Verify CALM stable packaging metadata and distribution-boundary ownership."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

try:
    from engineering.qualification.check_conda_recipe import (
        validate as validate_conda_recipe,
    )
    from engineering.qualification.check_source_environments import (
        validate as validate_source_environments,
    )
except ModuleNotFoundError:  # Direct script execution from this directory.
    from check_conda_recipe import validate as validate_conda_recipe
    from check_source_environments import validate as validate_source_environments


REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
MANIFEST = REPO_ROOT / "MANIFEST.in"
DISTRIBUTION_CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-python-distribution.json"
)
QUALIFICATION_MATRIX = (
    REPO_ROOT / "engineering" / "qualification" / "qualification-matrix.json"
)
MINIMUM_CONSTRAINTS = (
    REPO_ROOT
    / "engineering"
    / "qualification"
    / "constraints"
    / "minimum-py310-py312.txt"
)
EXPECTED_PYTHON = ">=3.10,<3.13"
EXPECTED_BASE = {"numpy", "sqlalchemy"}
EXPECTED_BASE_REQUIREMENTS = {"numpy>=1.26,<3", "sqlalchemy>=2.0,<3"}
EXPECTED_SCIENCE_REQUIREMENTS = {
    "scipy>=1.11.2,<2",
    "ase>=3.25,<4",
    "spglib>=2.6,<3",
}
EXPECTED_MINIMUM_REQUIREMENTS = {
    "numpy==1.26.0",
    "sqlalchemy==2.0.0",
    "scipy==1.11.2",
    "ase==3.25.0",
    "spglib==2.6.0",
}
EXPECTED_EXTRAS = {
    "science",
    "dataframe",
    "plot",
    "viz",
    "docs",
    "dev",
    "grace",
    "mace",
    "chgnet",
}
EXTRA_DEPENDENCIES = {
    "science": {"scipy", "ase", "spglib"},
    "dataframe": {"pandas"},
    "plot": {"matplotlib"},
    "viz": {"matplotlib", "seaborn", "plotly"},
    "grace": {"tensorpotential"},
    "mace": {"mace-torch"},
    "chgnet": {"chgnet"},
}
FORBIDDEN_DISTRIBUTIONS = {"lammps", "m3gnet", "m3gnet-torch", "matgl"}
FORBIDDEN_LEGACY_ROOT_FILES = (".flake8", "setup.py")
REQUIRED_DEV_DISTRIBUTIONS = {
    "pytest",
    "pytest-timeout",
    "ruff",
    "build",
    "twine",
    "tomli",
}
DISTRIBUTION_SCHEMA = "calm.python_distribution.v2"
EXPECTED_LICENSE_POLICY = {
    "copyright_holder": "Lawrence Livermore National Security, LLC",
    "copyright_year": 2026,
    "expression": "MIT",
    "status": "approved",
}
EXPECTED_LICENSE_FILES = ("LICENSE", "NOTICE")
_MANIFEST_DIRECTIVE_NAMES = frozenset(
    {"exclude", "global-exclude", "include", "prune", "recursive-exclude"}
)
_LICENSE_FILE_RE = re.compile(
    r"^(?:license|copying|notice)(?:\..*)?$", re.IGNORECASE
)


def _distribution_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"invalid dependency declaration: {requirement!r}")
    return match.group(1).lower().replace("_", "-")


def _names(requirements: list[str]) -> set[str]:
    return {_distribution_name(item) for item in requirements}


def _minimum_constraints() -> set[str]:
    return {
        line.strip()
        for line in MINIMUM_CONSTRAINTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _minimum_names(requirements: set[str]) -> set[str]:
    return _names(list(requirements))


def _manifest_directives(
    expected: list[tuple[str, ...]], errors: list[str]
) -> list[tuple[str, ...]]:
    observed: list[tuple[str, ...]] = []
    for line_number, raw_line in enumerate(
        MANIFEST.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            parts = shlex.split(raw_line, comments=True, posix=True)
        except ValueError as exc:
            errors.append(f"MANIFEST.in line {line_number} is invalid: {exc}")
            continue
        if not parts:
            continue
        row = tuple(parts)
        if row[0] not in _MANIFEST_DIRECTIVE_NAMES:
            errors.append(
                f"MANIFEST.in uses unsupported directive {row[0]!r} "
                f"on line {line_number}"
            )
            continue
        if len(row) < 2:
            errors.append(
                f"MANIFEST.in directive {row[0]!r} on line {line_number} "
                "requires at least one argument"
            )
            continue
        if row in observed:
            errors.append(f"MANIFEST.in repeats directive {row!r}")
        observed.append(row)
    if observed != expected:
        errors.append(
            "MANIFEST.in directives must exactly match the Python distribution "
            f"contract: expected {expected}, observed {observed}"
        )
    return observed


def _effective_license_files(errors: list[str]) -> list[str]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        errors.append(f"could not enumerate effective license files: {detail}")
        return []
    tracked: list[str] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        if _LICENSE_FILE_RE.fullmatch(Path(relative).name):
            tracked.append(relative)
    return sorted(tracked)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_license_policy(
    license_policy: Any,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(license_policy, dict):
        errors.append("Python distribution contract must define license_policy")
        return {}
    expected_keys = {*EXPECTED_LICENSE_POLICY, "files"}
    if set(license_policy) != expected_keys:
        errors.append(
            "Python distribution license policy keys must be exactly "
            f"{sorted(expected_keys)}, observed {sorted(license_policy)}"
        )
    for name, expected in EXPECTED_LICENSE_POLICY.items():
        if license_policy.get(name) != expected:
            errors.append(
                f"Python distribution license policy {name} must be {expected!r}"
            )

    files = license_policy.get("files")
    if not isinstance(files, dict):
        errors.append("Python distribution license policy files must be an object")
        files = {}
    if list(files) != list(EXPECTED_LICENSE_FILES):
        errors.append(
            "Python distribution license files must be exactly "
            f"{list(EXPECTED_LICENSE_FILES)}, observed {list(files)}"
        )
    for relative, expected_digest in files.items():
        if not isinstance(expected_digest, str) or re.fullmatch(
            r"[0-9a-f]{64}", expected_digest
        ) is None:
            errors.append(
                f"Python distribution license digest for {relative!r} "
                "must be lowercase SHA-256"
            )
            continue
        path = REPO_ROOT / relative
        if not path.is_file():
            errors.append(f"required license file is missing: {relative}")
            continue
        observed = _sha256(path)
        if observed != expected_digest:
            errors.append(
                f"license file digest mismatch for {relative}: "
                f"expected {expected_digest}, observed {observed}"
            )
    return license_policy


def _string_list(
    payload: Mapping[str, Any], name: str, errors: list[str]
) -> list[str]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"distribution contract {name} must be a string list")
        return []
    if value != sorted(value):
        errors.append(f"distribution contract {name} must be sorted")
    if len(value) != len(set(value)):
        errors.append(f"distribution contract {name} must not contain duplicates")
    return list(value)


def _token_rows(
    payload: Mapping[str, Any], name: str, errors: list[str]
) -> list[tuple[str, ...]]:
    value = payload.get(name)
    if not isinstance(value, list):
        errors.append(f"distribution contract {name} must be a list")
        return []
    rows: list[tuple[str, ...]] = []
    for index, row in enumerate(value):
        if not isinstance(row, list) or len(row) < 2 or any(
            not isinstance(item, str) or not item for item in row
        ):
            errors.append(
                f"distribution contract {name}[{index}] must contain at least "
                "two nonempty strings"
            )
            continue
        token_row = tuple(row)
        if token_row[0] not in _MANIFEST_DIRECTIVE_NAMES:
            errors.append(
                f"distribution contract {name}[{index}] uses unsupported "
                f"directive {token_row[0]!r}"
            )
        rows.append(token_row)
    if rows != sorted(rows):
        errors.append(f"distribution contract {name} must be sorted")
    if len(rows) != len(set(rows)):
        errors.append(f"distribution contract {name} must not contain duplicates")
    return rows


def _distribution_policy(errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(DISTRIBUTION_CONTRACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"could not read Python distribution contract: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("Python distribution contract must be a JSON object")
        return {}
    if payload.get("schema_version") != DISTRIBUTION_SCHEMA:
        errors.append(
            f"Python distribution contract schema must be {DISTRIBUTION_SCHEMA!r}"
        )
    _validate_license_policy(payload.get("license_policy"), errors)
    sdist = payload.get("sdist")
    if not isinstance(sdist, dict):
        errors.append("Python distribution contract must define sdist")
        sdist = {}
    if sdist.get("profile") != "minimal_installation_source":
        errors.append("sdist profile must be minimal_installation_source")
    for name in (
        "egg_info_files",
        "generated_root_files",
        "root_directories",
        "source_root_files",
    ):
        _string_list(sdist, name, errors)
    wheel = payload.get("wheel")
    if not isinstance(wheel, dict):
        errors.append("Python distribution contract must define wheel")
        wheel = {}
    if wheel.get("profile") != "installable_package_only":
        errors.append("wheel profile must be installable_package_only")
    if wheel.get("package_root") != "calm":
        errors.append("wheel package_root must be 'calm'")
    for name in ("dist_info_files", "package_file_suffixes"):
        _string_list(wheel, name, errors)
    return payload


def validate() -> dict[str, object]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    errors: list[str] = []
    distribution_policy = _distribution_policy(errors)

    version = str(project.get("version", ""))
    stable_version = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    if re.fullmatch(stable_version, version) is None:
        errors.append(
            "project.version must be an explicit stable PEP 440 version such as 1.0.0"
        )
    if project.get("requires-python") != EXPECTED_PYTHON:
        errors.append(
            f"project.requires-python must be exactly {EXPECTED_PYTHON!r}"
        )

    if project.get("license") != EXPECTED_LICENSE_POLICY["expression"]:
        errors.append("project.license must be the SPDX expression 'MIT'")
    if project.get("license-files") != list(EXPECTED_LICENSE_FILES):
        errors.append(
            "project.license-files must be exactly "
            f"{list(EXPECTED_LICENSE_FILES)}"
        )
    license_classifiers = [
        item
        for item in project.get("classifiers", ())
        if isinstance(item, str) and item.startswith("License ::")
    ]
    if license_classifiers:
        errors.append(
            "project classifiers must not duplicate the PEP 639 license expression"
        )
    effective_license_files = _effective_license_files(errors)
    if effective_license_files != list(EXPECTED_LICENSE_FILES):
        errors.append(
            "effective legal files must be exactly "
            f"{list(EXPECTED_LICENSE_FILES)}, observed {effective_license_files}"
        )

    base_requirements = set(project.get("dependencies", ()))
    base = _names(list(base_requirements))
    if base != EXPECTED_BASE:
        errors.append(
            "base dependencies must be "
            f"{sorted(EXPECTED_BASE)}, observed {sorted(base)}"
        )
    if base_requirements != EXPECTED_BASE_REQUIREMENTS:
        errors.append(
            "base dependency bounds must be exact: "
            f"expected {sorted(EXPECTED_BASE_REQUIREMENTS)}, "
            f"observed {sorted(base_requirements)}"
        )

    extras = project.get("optional-dependencies", {})
    if set(extras) != EXPECTED_EXTRAS:
        errors.append(
            "optional dependency groups must match the reviewed set: "
            f"expected {sorted(EXPECTED_EXTRAS)}, observed {sorted(extras)}"
        )
    for extra, expected in EXTRA_DEPENDENCIES.items():
        observed = _names(list(extras.get(extra, ())))
        if observed != expected:
            errors.append(
                f"extra {extra!r} must own {sorted(expected)}, "
                f"observed {sorted(observed)}"
            )
    dev_distributions = _names(list(extras.get("dev", ())))
    missing_dev = sorted(REQUIRED_DEV_DISTRIBUTIONS - dev_distributions)
    if missing_dev:
        errors.append(
            "dev extra is missing release qualification prerequisites: "
            + ", ".join(missing_dev)
        )
    if set(extras.get("science", ())) != EXPECTED_SCIENCE_REQUIREMENTS:
        errors.append(
            "science dependency bounds must be exact: "
            f"expected {sorted(EXPECTED_SCIENCE_REQUIREMENTS)}, "
            f"observed {sorted(extras.get('science', ()))}"
        )

    build_requirements = set(data.get("build-system", {}).get("requires", ()))
    if build_requirements != {"setuptools>=77", "wheel"}:
        errors.append(
            "build-system requirements must be exactly setuptools>=77 and wheel"
        )
    setuptools_config = data.get("tool", {}).get("setuptools", {})
    if setuptools_config.get("include-package-data") is not False:
        errors.append(
            "tool.setuptools.include-package-data must be false; CALM currently "
            "ships Python package sources only"
        )
    if setuptools_config.get("zip-safe") is not False:
        errors.append("tool.setuptools.zip-safe must be false")

    all_distributions = set(base)
    for requirements in extras.values():
        all_distributions.update(_names(list(requirements)))
    forbidden = sorted(all_distributions & FORBIDDEN_DISTRIBUTIONS)
    if forbidden:
        errors.append(
            "deferred or externally provisioned runtimes must not be package "
            f"dependencies: {forbidden}"
        )

    minimum_requirements = _minimum_constraints()
    minimum = _minimum_names(minimum_requirements)
    required_minimum = EXPECTED_BASE | EXTRA_DEPENDENCIES["science"]
    if minimum != required_minimum:
        errors.append(
            "minimum dependency constraints must cover exactly base + science: "
            f"expected {sorted(required_minimum)}, observed {sorted(minimum)}"
        )
    if minimum_requirements != EXPECTED_MINIMUM_REQUIREMENTS:
        errors.append(
            "minimum dependency pins must match the reviewed versions: "
            f"expected {sorted(EXPECTED_MINIMUM_REQUIREMENTS)}, "
            f"observed {sorted(minimum_requirements)}"
        )

    for name in FORBIDDEN_LEGACY_ROOT_FILES:
        if (REPO_ROOT / name).exists():
            errors.append(f"legacy packaging or lint shim must be removed: {name}")

    ruff = data.get("tool", {}).get("ruff", {})
    excluded = set(ruff.get("extend-exclude", ()))
    per_file_ignores = ruff.get("lint", {}).get("per-file-ignores", {})
    redundant_ignores = sorted(set(per_file_ignores) & excluded)
    if redundant_ignores:
        errors.append(
            "Ruff per-file ignores must not target globally excluded paths: "
            + ", ".join(redundant_ignores)
        )

    sdist_policy = distribution_policy.get("sdist", {})
    expected_manifest = (
        _token_rows(sdist_policy, "manifest_directives", errors)
        if isinstance(sdist_policy, dict)
        else []
    )
    _manifest_directives(expected_manifest, errors)

    conda_result = validate_conda_recipe(repo_root=REPO_ROOT)
    errors.extend(
        f"conda recipe: {error}" for error in conda_result["errors"]
    )
    environment_result = validate_source_environments(repo_root=REPO_ROOT)
    errors.extend(
        f"source environments: {error}"
        for error in environment_result["errors"]
    )

    matrix = json.loads(QUALIFICATION_MATRIX.read_text(encoding="utf-8"))
    matrix_contract = matrix.get("qualification_contract", {})
    if matrix_contract.get("package_version") != version:
        errors.append("qualification matrix package_version must match project.version")
    if matrix_contract.get("requires_python") != EXPECTED_PYTHON:
        errors.append(
            "qualification matrix requires_python must match project.requires-python"
        )

    result: dict[str, object] = {
        "schema": "calm.packaging_contract.v5",
        "version": version,
        "requires_python": project.get("requires-python"),
        "base_dependencies": sorted(base),
        "optional_extras": sorted(extras),
        "minimum_dependency_track": sorted(minimum),
        "license_status": distribution_policy.get("license_policy", {}).get(
            "status"
        ),
        "license_expression": distribution_policy.get("license_policy", {}).get(
            "expression"
        ),
        "sdist_profile": distribution_policy.get("sdist", {}).get("profile"),
        "wheel_profile": distribution_policy.get("wheel", {}).get("profile"),
        "conda_profile": conda_result.get("profile"),
        "conda_source_kind": conda_result.get("source_kind"),
        "source_environment_schema": environment_result.get("schema"),
        "source_environment_recipe_count": len(
            environment_result.get("recipes", [])
        ),
        "source_environment_provider_count": len(
            environment_result.get("provider_families", [])
        ),
        "errors": errors,
    }
    return result


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    errors = result["errors"]
    if errors:
        for error in errors:
            print(f"Packaging contract error: {error}")
        return 1
    print("CALM stable packaging and distribution contract is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
