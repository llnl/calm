#!/usr/bin/env python3
"""Validate CALM's canonical local-source conda recipe."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-conda-package.json"
)
PYPROJECT = REPO_ROOT / "pyproject.toml"
DISTRIBUTION_CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-python-distribution.json"
)
_SCHEMA_VERSION = "calm.conda_package.v1"
_CONTRACT_KEYS = frozenset(
    {
        "about",
        "build",
        "dependency_policy",
        "license_policy_authority",
        "maintainers",
        "owned_files",
        "package_name",
        "profile",
        "publication",
        "recipe_path",
        "schema_version",
        "source",
        "test",
    }
)
_ABOUT_KEYS = frozenset(
    {"description_lines", "dev_url", "doc_url", "home", "summary"}
)
_BUILD_KEYS = frozenset(
    {"authority", "noarch", "number", "script", "subdir"}
)
_DEPENDENCY_POLICY_KEYS = frozenset({"host", "run", "science"})
_PUBLICATION_KEYS = frozenset(
    {"release_recipe_required", "source_digest_required", "status"}
)
_SOURCE_KEYS = frozenset({"kind", "path", "working_tree_policy"})
_TEST_KEYS = frozenset({"imports", "run_test", "test_requirements"})
_REQUIRED_README_FRAGMENTS = (
    "internal local-source qualification recipe",
    "science dependencies are not bundled",
    "git status --short",
    "engineering/qualification/check_conda_recipe.py",
    "--no-anaconda-upload",
    "--output-folder",
    "immutable source archive",
    "sha-256",
    "licensed under the mit license",
)
_REQUIREMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)(.*)$")
_RUN_TEST_CONSTANT_NAMES = frozenset(
    {
        "EXPECTED_BUILD_NUMBER",
        "EXPECTED_DEPENDENCIES",
        "EXPECTED_NAME",
        "EXPECTED_SUBDIR",
    }
)


def _mapping(
    payload: Mapping[str, Any],
    name: str,
    expected_keys: frozenset[str],
    errors: list[str],
) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        errors.append(f"{name} must be a JSON object")
        return {}
    observed = set(value)
    if observed != expected_keys:
        errors.append(
            f"{name} keys must be exactly {sorted(expected_keys)}, "
            f"observed {sorted(observed)}"
        )
    if list(value) != sorted(value):
        errors.append(f"{name} keys must be sorted")
    return value


def _string_list(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
    *,
    allow_empty: bool = False,
    require_sorted: bool = True,
) -> list[str]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"{name} must be a list of nonempty strings")
        return []
    if not allow_empty and not value:
        errors.append(f"{name} must not be empty")
    if require_sorted and value != sorted(value):
        errors.append(f"{name} must be sorted")
    if len(value) != len(set(value)):
        errors.append(f"{name} must not contain duplicates")
    return list(value)


def _repository_relative(value: Any, name: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value:
        errors.append(f"{name} must be a nonempty repository-relative path")
        return ""
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./"):
        errors.append(f"{name} must be a safe repository-relative path")
        return ""
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _requirement_name(requirement: str) -> str:
    match = _REQUIREMENT_RE.fullmatch(requirement)
    if match is None:
        raise ValueError(f"unsupported requirement declaration: {requirement!r}")
    return match.group(1).lower().replace("_", "-")


def _conda_requirement(requirement: str) -> str:
    match = _REQUIREMENT_RE.fullmatch(requirement)
    if match is None:
        raise ValueError(f"unsupported requirement declaration: {requirement!r}")
    name, suffix = match.groups()
    if any(token in suffix for token in (";", "@", "[", "]")):
        raise ValueError(
            "conda base and build requirements must be simple named "
            f"requirements: {requirement!r}"
        )
    return name.lower().replace("_", "-") + (f" {suffix}" if suffix else "")


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"could not read {label}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _load_pyproject(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"could not read pyproject.toml: {exc}")
        return {}
    project = payload.get("project")
    build_system = payload.get("build-system")
    if not isinstance(project, dict):
        errors.append("pyproject.toml must define [project]")
    if not isinstance(build_system, dict):
        errors.append("pyproject.toml must define [build-system]")
    return payload


def _run_test_constants(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        errors.append(f"could not parse conda run_test.py: {exc}")
        return {}

    future_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "__future__"
    ]
    if future_imports:
        errors.append(
            "conda run_test.py must not contain __future__ imports because "
            "conda-build may prepend generated import checks"
        )

    constants: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or not target.id.startswith("EXPECTED_"):
            continue
        if target.id in constants:
            errors.append(f"conda run_test.py assigns {target.id} more than once")
            continue
        try:
            constants[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            errors.append(
                f"conda run_test.py {target.id} must be a literal projection"
            )
    observed = set(constants)
    if observed != _RUN_TEST_CONSTANT_NAMES:
        errors.append(
            "conda run_test.py expected constants must be exactly "
            f"{sorted(_RUN_TEST_CONSTANT_NAMES)}, observed {sorted(observed)}"
        )
    return constants


def _effective_recipe_files(repo_root: Path, recipe_directory: Path) -> list[str]:
    relative_directory = recipe_directory.relative_to(repo_root).as_posix()
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            relative_directory,
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode == 0:
        files: list[str] = []
        for raw in completed.stdout.split(b"\0"):
            if not raw:
                continue
            relative = Path(raw.decode("utf-8"))
            absolute = repo_root / relative
            if absolute.is_file():
                files.append(absolute.relative_to(recipe_directory).as_posix())
        return sorted(files)
    return sorted(
        path.relative_to(recipe_directory).as_posix()
        for path in recipe_directory.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )


def _render_recipe(
    *,
    name: str,
    version: str,
    requires_python: str,
    build_requirements: list[str],
    run_requirements: list[str],
    license_expression: str,
    license_files: list[str],
    maintainers: list[str],
    contract: Mapping[str, Any],
) -> str:
    build = contract["build"]
    source = contract["source"]
    test = contract["test"]
    about = contract["about"]

    host = [f"python {requires_python}", "pip", *build_requirements]
    run = [f"python {requires_python}", *run_requirements]
    lines = [
        f'{{% set name = "{name}" %}}',
        f'{{% set version = "{version}" %}}',
        "",
        "package:",
        "  name: {{ name|lower }}",
        "  version: {{ version }}",
        "",
        "source:",
        f"  path: {source['path']}",
        "",
        "build:",
        f"  number: {build['number']}",
        f"  noarch: {build['noarch']}",
        f"  script: {build['script']}",
        "",
        "requirements:",
        "  host:",
        *[f"    - {item}" for item in host],
        "  run:",
        *[f"    - {item}" for item in run],
        "",
        "test:",
        "  imports:",
        *[f"    - {item}" for item in test["imports"]],
        "",
        "about:",
        f"  home: {about['home']}",
        f"  license: {license_expression}",
        f"  license_family: {license_expression}",
        "  license_file:",
        *[f"    - {item}" for item in license_files],
        f"  summary: {about['summary']}",
        "  description: |",
        *[f"    {line}" for line in about["description_lines"]],
        f"  doc_url: {about['doc_url']}",
        f"  dev_url: {about['dev_url']}",
        "",
        "extra:",
        "  recipe-maintainers:",
        *[f"    - {item}" for item in maintainers],
        "",
    ]
    return "\n".join(lines)


def validate(
    *,
    repo_root: Path = REPO_ROOT,
    contract_path: Path | None = None,
) -> dict[str, object]:
    root = repo_root.resolve()
    errors: list[str] = []
    contract_file = (
        contract_path.resolve()
        if contract_path is not None
        else root
        / "engineering"
        / "architecture"
        / "current-conda-package.json"
    )
    contract = _load_json(contract_file, "conda package contract", errors)
    observed_keys = set(contract)
    if observed_keys != _CONTRACT_KEYS:
        errors.append(
            "conda package contract keys must be exactly "
            f"{sorted(_CONTRACT_KEYS)}, observed {sorted(observed_keys)}"
        )
    if list(contract) != sorted(contract):
        errors.append("conda package contract keys must be sorted")
    if contract.get("schema_version") != _SCHEMA_VERSION:
        errors.append(f"schema_version must be {_SCHEMA_VERSION!r}")

    about = _mapping(contract, "about", _ABOUT_KEYS, errors)
    build = _mapping(contract, "build", _BUILD_KEYS, errors)
    dependency_policy = _mapping(
        contract, "dependency_policy", _DEPENDENCY_POLICY_KEYS, errors
    )
    publication = _mapping(
        contract, "publication", _PUBLICATION_KEYS, errors
    )
    source = _mapping(contract, "source", _SOURCE_KEYS, errors)
    test = _mapping(contract, "test", _TEST_KEYS, errors)

    description_lines = _string_list(
        about,
        "description_lines",
        errors,
        require_sorted=False,
    )
    maintainers = _string_list(contract, "maintainers", errors)
    owned_files = _string_list(contract, "owned_files", errors)
    test_imports = _string_list(test, "imports", errors)
    test_requirements = _string_list(
        test, "test_requirements", errors, allow_empty=True
    )
    if test_requirements:
        errors.append("conda package test_requirements must remain empty")

    if contract.get("profile") != "local_source_base_package":
        errors.append("profile must be 'local_source_base_package'")
    if contract.get("package_name") != "calm":
        errors.append("package_name must be 'calm'")
    if contract.get("license_policy_authority") != (
        "engineering/architecture/current-python-distribution.json#license_policy"
    ):
        errors.append("license_policy_authority must name the distribution contract")
    if build != {
        "authority": "meta_yaml_script",
        "number": 0,
        "noarch": "python",
        "script": (
            "{{ PYTHON }} -m pip install . -vv --no-deps "
            "--no-build-isolation"
        ),
        "subdir": "noarch",
    }:
        errors.append("build must define the reviewed single-script authority")
    if dependency_policy != {
        "host": "python + pip + pyproject.build-system.requires",
        "run": "python + pyproject.project.dependencies",
        "science": "not_bundled",
    }:
        errors.append("dependency_policy must mirror the Python base distribution")
    if publication != {
        "release_recipe_required": True,
        "source_digest_required": True,
        "status": "internal_qualification_only",
    }:
        errors.append("publication must remain internal qualification only")
    if source != {
        "kind": "local_path",
        "path": "..",
        "working_tree_policy": "clean_commit_required_for_qualification",
    }:
        errors.append("source must remain the reviewed local clean-commit profile")
    if test_imports != ["calm"]:
        errors.append("test.imports must contain only 'calm'")
    if description_lines and any(
        line != line.strip() or len(line) > 78 for line in description_lines
    ):
        errors.append(
            "about.description_lines must have no surrounding whitespace and "
            "must not exceed 78 characters"
        )

    recipe_relative = _repository_relative(
        contract.get("recipe_path"), "recipe_path", errors
    )
    run_test_relative = _repository_relative(
        test.get("run_test"), "test.run_test", errors
    )
    for name in owned_files:
        if PurePosixPath(name).name != name or name in {".", ".."}:
            errors.append(f"owned_files entries must be direct recipe files: {name!r}")

    distribution = _load_json(
        root
        / "engineering"
        / "architecture"
        / "current-python-distribution.json",
        "Python distribution contract",
        errors,
    )
    license_policy = distribution.get("license_policy")
    license_expression = ""
    license_files: list[str] = []
    if not isinstance(license_policy, dict):
        errors.append("Python distribution contract must define license_policy")
    else:
        if license_policy.get("status") != "approved":
            errors.append("license status must be approved")
        if license_policy.get("copyright_holder") != (
            "Lawrence Livermore National Security, LLC"
        ):
            errors.append("license copyright holder must match the LLNL template")
        if license_policy.get("copyright_year") != 2026:
            errors.append("license copyright year must be 2026")
        expression = license_policy.get("expression")
        if expression != "MIT":
            errors.append("conda license policy must use the MIT expression")
        elif isinstance(expression, str):
            license_expression = expression
        files = license_policy.get("files")
        if not isinstance(files, dict) or list(files) != ["LICENSE", "NOTICE"]:
            errors.append(
                "conda license files must be exactly ['LICENSE', 'NOTICE']"
            )
        else:
            license_files = list(files)
            for filename, expected_digest in files.items():
                path = root / filename
                if not isinstance(expected_digest, str) or re.fullmatch(
                    r"[0-9a-f]{64}", expected_digest
                ) is None:
                    errors.append(
                        f"conda license file digest must be SHA-256: {filename}"
                    )
                    continue
                if not path.is_file():
                    errors.append(f"conda license file is missing: {filename}")
                    continue
                observed_digest = _sha256(path)
                if observed_digest != expected_digest:
                    errors.append(
                        "conda license file digest mismatch for "
                        f"{filename}: expected {expected_digest}, "
                        f"observed {observed_digest}"
                    )

    pyproject = _load_pyproject(root / "pyproject.toml", errors)
    project = pyproject.get("project", {})
    build_system = pyproject.get("build-system", {})
    package_name = project.get("name") if isinstance(project, dict) else None
    version = project.get("version") if isinstance(project, dict) else None
    requires_python = (
        project.get("requires-python") if isinstance(project, dict) else None
    )
    dependencies = (
        project.get("dependencies", []) if isinstance(project, dict) else []
    )
    build_requirements = (
        build_system.get("requires", [])
        if isinstance(build_system, dict)
        else []
    )
    if package_name != contract.get("package_name"):
        errors.append("conda package name must match pyproject project.name")
    for field_name, value in (
        ("project.version", version),
        ("project.requires-python", requires_python),
    ):
        if not isinstance(value, str) or not value:
            errors.append(f"{field_name} must be a nonempty string")
    if not isinstance(dependencies, list) or any(
        not isinstance(item, str) for item in dependencies
    ):
        errors.append("project.dependencies must be a string list")
        dependencies = []
    if not isinstance(build_requirements, list) or any(
        not isinstance(item, str) for item in build_requirements
    ):
        errors.append("build-system.requires must be a string list")
        build_requirements = []

    normalized_build: list[str] = []
    normalized_run: list[str] = []
    try:
        normalized_build = [
            _conda_requirement(item) for item in build_requirements
        ]
        normalized_run = [_conda_requirement(item) for item in dependencies]
    except ValueError as exc:
        errors.append(str(exc))
    run_names = {_requirement_name(item) for item in dependencies}
    if run_names != {"numpy", "sqlalchemy"}:
        errors.append(
            "conda run dependencies must be derived from the import-light "
            "base package only"
        )

    recipe_path = root / recipe_relative if recipe_relative else root / "missing"
    recipe_directory = recipe_path.parent
    observed_files = (
        _effective_recipe_files(root, recipe_directory)
        if recipe_directory.is_dir()
        else []
    )
    if observed_files != owned_files:
        errors.append(
            "conda recipe files must exactly match owned_files: "
            f"expected {owned_files}, observed {observed_files}"
        )
    if run_test_relative:
        run_test_path = root / run_test_relative
        if not run_test_path.is_file():
            errors.append(f"conda test script is missing: {run_test_relative}")
        else:
            if run_test_path.parent != recipe_directory:
                errors.append("conda test script must live beside meta.yaml")
            observed_constants = _run_test_constants(run_test_path, errors)
            expected_constants = {
                "EXPECTED_BUILD_NUMBER": build.get("number"),
                "EXPECTED_DEPENDENCIES": {"python", *run_names},
                "EXPECTED_NAME": package_name,
                "EXPECTED_SUBDIR": build.get("subdir"),
            }
            if observed_constants and observed_constants != expected_constants:
                errors.append(
                    "conda run_test.py constants must project the current "
                    "package, build, and runtime dependency contract"
                )

    expected_recipe = ""
    if (
        isinstance(package_name, str)
        and isinstance(version, str)
        and isinstance(requires_python, str)
        and normalized_build
    ):
        expected_recipe = _render_recipe(
            name=package_name,
            version=version,
            requires_python=requires_python,
            build_requirements=normalized_build,
            run_requirements=normalized_run,
            license_expression=license_expression,
            license_files=license_files,
            maintainers=maintainers,
            contract=contract,
        )
    try:
        observed_recipe = recipe_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"could not read conda recipe: {exc}")
        observed_recipe = ""
    if expected_recipe and observed_recipe != expected_recipe:
        errors.append(
            "conda-recipe/meta.yaml must exactly match the canonical "
            "local-source base-package projection"
        )

    readme_path = recipe_directory / "README.md"
    try:
        readme = readme_path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"could not read conda recipe README: {exc}")
        readme = ""
    normalized_readme = " ".join(readme.split()).lower()
    missing_fragments = [
        fragment
        for fragment in _REQUIRED_README_FRAGMENTS
        if fragment not in normalized_readme
    ]
    if missing_fragments:
        errors.append(
            "conda recipe README is missing required policy text: "
            + ", ".join(missing_fragments)
        )

    return {
        "schema": _SCHEMA_VERSION,
        "profile": contract.get("profile"),
        "package_name": package_name,
        "package_version": version,
        "source_kind": source.get("kind"),
        "build_authority": build.get("authority"),
        "build_number": build.get("number"),
        "license_expression": license_expression or None,
        "license_files": license_files,
        "host_requirements": (
            [f"python {requires_python}", "pip", *normalized_build]
            if isinstance(requires_python, str)
            else []
        ),
        "run_requirements": (
            [f"python {requires_python}", *normalized_run]
            if isinstance(requires_python, str)
            else []
        ),
        "owned_files": observed_files,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-current",
        action="store_true",
        help="print the validated conda recipe projection",
    )
    args = parser.parse_args(argv)
    result = validate()
    if args.show_current or result["errors"]:
        print(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        print("CALM conda recipe contract is inconsistent.")
        return 1
    print(
        "CALM conda recipe contract is consistent: "
        f"{result['profile']} with {len(result['run_requirements'])} "
        "runtime requirements."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
