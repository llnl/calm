#!/usr/bin/env python3
"""Validate CALM's source-checkout environment ownership and recipes."""

from __future__ import annotations

import argparse
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
    / "current-source-environments.json"
)
PYPROJECT = REPO_ROOT / "pyproject.toml"
QUALIFICATION_MATRIX = (
    REPO_ROOT / "engineering" / "qualification" / "qualification-matrix.json"
)
_SCHEMA_VERSION = "calm.source_environments.v1"
_CONTRACT_KEYS = frozenset(
    {
        "dependency_profiles",
        "owned_files",
        "provider_profiles",
        "recipe_policy",
        "recipes",
        "schema_version",
        "validation",
    }
)
_DEPENDENCY_PROFILE_KEYS = frozenset({"imports", "source"})
_PROVIDER_PROFILE_KEYS = frozenset(
    {
        "distribution_imports",
        "environment_name",
        "external_runtime_required",
        "extra",
        "import_any",
        "recipe",
        "required_imports",
        "runtime_scope",
    }
)
_RECIPE_POLICY_KEYS = frozenset(
    {
        "channels",
        "include_pip",
        "provider_dependency_source",
        "shared_dependency_profiles",
    }
)
_RECIPE_KEYS = frozenset({"environment_name", "provider_extra"})
_VALIDATION_KEYS = frozenset(
    {
        "default_profile",
        "project_smoke",
        "python_maximum_exclusive",
        "python_minimum",
        "supported_profiles",
    }
)
_REQUIREMENT_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_EXPECTED_OWNED_FILES = [
    "README.md",
    "calm-chgnet.yml",
    "calm-grace.yml",
    "calm-mace.yml",
    "calm-science.yml",
    "validate_environment.py",
]
_EXPECTED_RECIPES = {
    "calm-chgnet.yml",
    "calm-grace.yml",
    "calm-mace.yml",
    "calm-science.yml",
}
_REQUIRED_VALIDATOR_FRAGMENTS = (
    "calm.source_environment_validation.v1",
    "current-source-environments.json",
    "--profile",
    "--provider",
    "conda_default_env",
    "default_profile",
    "default_registry",
    "project-smoke",
)
_FORBIDDEN_VALIDATOR_FRAGMENTS = (
    "calm-base",
    "calm-full",
    "check_interactive_tools",
    "detect_environment",
    "jupyter",
    "postinstall.md",
)
_REQUIRED_README_FRAGMENTS = (
    "one primary provider",
    "calm-science.yml",
    "calm-chgnet.yml",
    "calm-grace.yml",
    "calm-mace.yml",
    "python -m pip install -e . --no-deps",
    "python environments/validate_environment.py --profile science",
    "python environments/validate_environment.py --provider",
    "external lammps runtime",
    "not lock files",
)
_FORBIDDEN_README_FRAGMENTS = (
    "calm-base.yml",
    "calm-full.yml",
    "calm-grace-gpu.yml",
    "calm-m3gnet.yml",
    "calm-mattersim.yml",
    "calm-nequip.yml",
    "calm-orb.yml",
    "calm-sevennet.yml",
    "calm-universal.yml",
)


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


def _mapping(
    payload: Mapping[str, Any],
    name: str,
    expected_keys: frozenset[str] | None,
    errors: list[str],
) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        errors.append(f"{name} must be a JSON object")
        return {}
    if expected_keys is not None and set(value) != expected_keys:
        errors.append(
            f"{name} keys must be exactly {sorted(expected_keys)}, "
            f"observed {sorted(value)}"
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
) -> list[str]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"{name} must be a list of nonempty strings")
        return []
    if not allow_empty and not value:
        errors.append(f"{name} must not be empty")
    if value != sorted(value):
        errors.append(f"{name} must be sorted")
    if len(value) != len(set(value)):
        errors.append(f"{name} must not contain duplicates")
    return list(value)


def _string_map(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
    *,
    allow_empty: bool = False,
) -> dict[str, str]:
    value = payload.get(name)
    if not isinstance(value, dict) or any(
        not isinstance(key, str)
        or not key
        or not isinstance(item, str)
        or not item
        for key, item in value.items()
    ):
        errors.append(f"{name} must be a string-to-string JSON object")
        return {}
    if not allow_empty and not value:
        errors.append(f"{name} must not be empty")
    if list(value) != sorted(value):
        errors.append(f"{name} keys must be sorted")
    return dict(value)


def _requirement_name(requirement: str) -> str:
    match = _REQUIREMENT_RE.match(requirement)
    if match is None:
        raise ValueError(f"invalid requirement {requirement!r}")
    return match.group(1).lower().replace("_", "-")


def _requirements_for_source(
    project: Mapping[str, Any],
    source: str,
    errors: list[str],
) -> list[str]:
    if source == "project.dependencies":
        value = project.get("dependencies")
    elif source.startswith("project.optional-dependencies."):
        extra = source.rsplit(".", 1)[-1]
        optional = project.get("optional-dependencies", {})
        value = optional.get(extra) if isinstance(optional, dict) else None
    else:
        errors.append(f"unsupported dependency source {source!r}")
        return []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"dependency source {source!r} must resolve to strings")
        return []
    return list(value)


def _effective_environment_entries(
    repo_root: Path,
) -> tuple[set[str], set[str]]:
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
            "environments",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    files: set[str] = set()
    directories: set[str] = set()
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative_text = raw.decode("utf-8")
        if not (repo_root / relative_text).exists():
            continue
        relative = PurePosixPath(relative_text)
        if not relative.parts or relative.parts[0] != "environments":
            continue
        if len(relative.parts) == 2:
            files.add(relative.parts[1])
        elif len(relative.parts) > 2:
            directories.add(relative.parts[1])
    return files, directories


def _expected_recipe(
    *,
    environment_name: str,
    channels: list[str],
    python_spec: str,
    shared_requirements: list[str],
    provider_requirements: list[str],
    include_pip: bool,
) -> str:
    lines = [
        f"name: {environment_name}",
        "channels:",
        *[f"  - {channel}" for channel in channels],
        "dependencies:",
        f"  - python{python_spec}",
        *[f"  - {requirement}" for requirement in shared_requirements],
    ]
    if include_pip:
        lines.append("  - pip")
    if provider_requirements:
        lines.append("  - pip:")
        lines.extend(f"      - {requirement}" for requirement in provider_requirements)
    return "\n".join(lines) + "\n"


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
        / "current-source-environments.json"
    )
    contract = _load_json(contract_file, "source environment contract", errors)
    if set(contract) != _CONTRACT_KEYS:
        errors.append(
            "source environment contract keys must be exactly "
            f"{sorted(_CONTRACT_KEYS)}, observed {sorted(contract)}"
        )
    if list(contract) != sorted(contract):
        errors.append("source environment contract keys must be sorted")
    if contract.get("schema_version") != _SCHEMA_VERSION:
        errors.append(f"schema_version must be {_SCHEMA_VERSION!r}")

    owned_files = _string_list(contract, "owned_files", errors)
    if owned_files != _EXPECTED_OWNED_FILES:
        errors.append(
            "owned_files must contain exactly the maintained source-environment "
            f"surfaces: expected {_EXPECTED_OWNED_FILES}, observed {owned_files}"
        )
    dependency_profiles = _mapping(
        contract, "dependency_profiles", None, errors
    )
    provider_profiles = _mapping(contract, "provider_profiles", None, errors)
    recipe_policy = _mapping(
        contract, "recipe_policy", _RECIPE_POLICY_KEYS, errors
    )
    recipes = _mapping(contract, "recipes", None, errors)
    validation = _mapping(contract, "validation", _VALIDATION_KEYS, errors)

    if set(dependency_profiles) != {"base", "science"}:
        errors.append("dependency_profiles must contain exactly base and science")
    if set(recipes) != _EXPECTED_RECIPES:
        errors.append("recipes must contain only science and registered ML providers")

    pyproject_path = root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"could not read pyproject.toml: {exc}")
        pyproject = {}
    project = pyproject.get("project", {})
    if not isinstance(project, dict):
        errors.append("pyproject.toml project table must be a mapping")
        project = {}
    python_spec = project.get("requires-python")
    if not isinstance(python_spec, str) or not python_spec:
        errors.append("project.requires-python must be a nonempty string")
        python_spec = ""

    resolved_requirements: dict[str, list[str]] = {}
    for profile_name, raw_profile in dependency_profiles.items():
        if not isinstance(raw_profile, dict):
            errors.append(f"dependency profile {profile_name!r} must be an object")
            continue
        if set(raw_profile) != _DEPENDENCY_PROFILE_KEYS:
            errors.append(
                f"dependency profile {profile_name!r} keys must be exactly "
                f"{sorted(_DEPENDENCY_PROFILE_KEYS)}"
            )
        if list(raw_profile) != sorted(raw_profile):
            errors.append(
                f"dependency profile {profile_name!r} keys must be sorted"
            )
        source = raw_profile.get("source")
        if not isinstance(source, str) or not source:
            errors.append(
                f"dependency profile {profile_name!r} source must be a string"
            )
            continue
        requirements = _requirements_for_source(project, source, errors)
        resolved_requirements[profile_name] = requirements
        imports = _string_map(raw_profile, "imports", errors)
        try:
            names = {_requirement_name(item) for item in requirements}
        except ValueError as exc:
            errors.append(str(exc))
            names = set()
        if set(imports) != names:
            errors.append(
                f"dependency profile {profile_name!r} imports must cover exactly "
                f"{sorted(names)}, observed {sorted(imports)}"
            )

    channels = _string_list(recipe_policy, "channels", errors)
    if channels != ["conda-forge", "nodefaults"]:
        errors.append(
            "recipe_policy.channels must be exactly conda-forge and nodefaults"
        )
    shared_profiles = _string_list(
        recipe_policy, "shared_dependency_profiles", errors
    )
    if shared_profiles != ["base", "science"]:
        errors.append(
            "recipe_policy.shared_dependency_profiles must be ['base', 'science']"
        )
    if recipe_policy.get("include_pip") is not True:
        errors.append("recipe_policy.include_pip must be true")
    if recipe_policy.get("provider_dependency_source") != (
        "project.optional-dependencies"
    ):
        errors.append(
            "recipe_policy.provider_dependency_source must name project extras"
        )

    matrix = _load_json(
        root / "engineering" / "qualification" / "qualification-matrix.json",
        "qualification matrix",
        errors,
    )
    matrix_providers = matrix.get("providers", [])
    if not isinstance(matrix_providers, list):
        errors.append("qualification matrix providers must be a list")
        registered_families: set[str] = set()
    else:
        registered_families = {
            item.get("family")
            for item in matrix_providers
            if isinstance(item, dict) and isinstance(item.get("family"), str)
        }
    if set(provider_profiles) != registered_families:
        errors.append(
            "provider profiles must match registered qualification families: "
            f"expected {sorted(registered_families)}, "
            f"observed {sorted(provider_profiles)}"
        )

    optional = project.get("optional-dependencies", {})
    if not isinstance(optional, dict):
        optional = {}
    for family, raw_profile in provider_profiles.items():
        if not isinstance(raw_profile, dict):
            errors.append(f"provider profile {family!r} must be an object")
            continue
        if set(raw_profile) != _PROVIDER_PROFILE_KEYS:
            errors.append(
                f"provider profile {family!r} keys must be exactly "
                f"{sorted(_PROVIDER_PROFILE_KEYS)}"
            )
        if list(raw_profile) != sorted(raw_profile):
            errors.append(f"provider profile {family!r} keys must be sorted")
        distribution_imports = _string_map(
            raw_profile,
            "distribution_imports",
            errors,
            allow_empty=True,
        )
        required_imports = _string_list(
            raw_profile, "required_imports", errors, allow_empty=True
        )
        import_any = _string_list(
            raw_profile, "import_any", errors, allow_empty=True
        )
        extra = raw_profile.get("extra")
        if extra is not None and (not isinstance(extra, str) or not extra):
            errors.append(f"provider profile {family!r} extra must be null or a string")
            extra = None
        if extra is None:
            if distribution_imports:
                errors.append(
                    f"provider profile {family!r} without an extra must not "
                    "declare distribution_imports"
                )
        else:
            requirements = optional.get(extra)
            if not isinstance(requirements, list) or any(
                not isinstance(item, str) for item in requirements
            ):
                errors.append(
                    f"provider profile {family!r} extra {extra!r} is missing"
                )
                requirements = []
            try:
                names = {_requirement_name(item) for item in requirements}
            except ValueError as exc:
                errors.append(str(exc))
                names = set()
            if set(distribution_imports) != names:
                errors.append(
                    f"provider profile {family!r} distribution imports must "
                    f"cover extra {extra!r}: expected {sorted(names)}, "
                    f"observed {sorted(distribution_imports)}"
                )
        if not required_imports and not import_any and not distribution_imports:
            errors.append(
                f"provider profile {family!r} must declare an import check"
            )
        recipe_name = raw_profile.get("recipe")
        environment_name = raw_profile.get("environment_name")
        if recipe_name not in recipes:
            errors.append(
                f"provider profile {family!r} references unknown recipe "
                f"{recipe_name!r}"
            )
        elif isinstance(recipes[recipe_name], dict):
            recipe_environment = recipes[recipe_name].get("environment_name")
            if environment_name != recipe_environment:
                errors.append(
                    f"provider profile {family!r} environment_name must match "
                    f"recipe {recipe_name!r}"
                )
        if not isinstance(raw_profile.get("external_runtime_required"), bool):
            errors.append(
                f"provider profile {family!r} external_runtime_required "
                "must be boolean"
            )
        if not isinstance(raw_profile.get("runtime_scope"), str):
            errors.append(
                f"provider profile {family!r} runtime_scope must be a string"
            )

    environment_dir = root / "environments"
    try:
        effective_files, effective_directories = _effective_environment_entries(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"unable to inspect effective environment paths: {exc}")
        effective_files, effective_directories = set(), set()
    actual_files = sorted(effective_files)
    actual_directories = sorted(effective_directories)
    if actual_files != owned_files:
        errors.append(
            "environments/ files must exactly match ownership: "
            f"expected {owned_files}, observed {actual_files}"
        )
    if actual_directories:
        errors.append(
            "environments/ must not contain subdirectories: "
            + ", ".join(actual_directories)
        )

    shared_requirements = [
        requirement
        for profile_name in shared_profiles
        for requirement in resolved_requirements.get(profile_name, [])
    ]
    for recipe_name, raw_recipe in recipes.items():
        if not isinstance(raw_recipe, dict):
            errors.append(f"recipe {recipe_name!r} must be an object")
            continue
        if set(raw_recipe) != _RECIPE_KEYS:
            errors.append(
                f"recipe {recipe_name!r} keys must be exactly "
                f"{sorted(_RECIPE_KEYS)}"
            )
        if list(raw_recipe) != sorted(raw_recipe):
            errors.append(f"recipe {recipe_name!r} keys must be sorted")
        environment_name = raw_recipe.get("environment_name")
        provider_extra = raw_recipe.get("provider_extra")
        if not isinstance(environment_name, str) or not environment_name:
            errors.append(f"recipe {recipe_name!r} environment_name is invalid")
            continue
        if provider_extra is None:
            provider_requirements: list[str] = []
        elif isinstance(provider_extra, str) and provider_extra:
            raw_requirements = optional.get(provider_extra)
            if not isinstance(raw_requirements, list) or any(
                not isinstance(item, str) for item in raw_requirements
            ):
                errors.append(
                    f"recipe {recipe_name!r} references missing provider extra "
                    f"{provider_extra!r}"
                )
                provider_requirements = []
            else:
                provider_requirements = list(raw_requirements)
        else:
            errors.append(
                f"recipe {recipe_name!r} provider_extra must be null or a string"
            )
            provider_requirements = []
        expected_text = _expected_recipe(
            environment_name=environment_name,
            channels=channels,
            python_spec=python_spec,
            shared_requirements=shared_requirements,
            provider_requirements=provider_requirements,
            include_pip=recipe_policy.get("include_pip") is True,
        )
        recipe_path = environment_dir / recipe_name
        try:
            observed_text = recipe_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"could not read {recipe_name}: {exc}")
            continue
        if observed_text != expected_text:
            errors.append(
                f"{recipe_name} must be the exact pyproject-derived recipe"
            )

    if validation.get("default_profile") != "base":
        errors.append("validation.default_profile must be 'base'")
    if validation.get("project_smoke") is not True:
        errors.append("validation.project_smoke must be true")
    if validation.get("python_minimum") != "3.10":
        errors.append("validation.python_minimum must be '3.10'")
    if validation.get("python_maximum_exclusive") != "3.13":
        errors.append(
            "validation.python_maximum_exclusive must be '3.13'"
        )
    if python_spec != (
        f">={validation.get('python_minimum')},"
        f"<{validation.get('python_maximum_exclusive')}"
    ):
        errors.append(
            "validation Python projection must match project.requires-python"
        )
    supported_profiles = _string_list(
        validation, "supported_profiles", errors
    )
    if supported_profiles != ["base", "provider", "science"]:
        errors.append(
            "validation.supported_profiles must be base, provider, and science"
        )

    validator_path = environment_dir / "validate_environment.py"
    try:
        validator_source = validator_path.read_text(encoding="utf-8").lower()
    except OSError as exc:
        errors.append(f"could not read environments/validate_environment.py: {exc}")
        validator_source = ""
    for fragment in _REQUIRED_VALIDATOR_FRAGMENTS:
        if fragment not in validator_source:
            errors.append(
                "environments/validate_environment.py must contain "
                f"{fragment!r}"
            )
    for fragment in _FORBIDDEN_VALIDATOR_FRAGMENTS:
        if fragment in validator_source:
            errors.append(
                "environments/validate_environment.py must not retain "
                f"legacy marker {fragment!r}"
            )

    readme_path = environment_dir / "README.md"
    try:
        readme = " ".join(
            readme_path.read_text(encoding="utf-8").lower().split()
        )
    except OSError as exc:
        errors.append(f"could not read environments/README.md: {exc}")
        readme = ""
    for fragment in _REQUIRED_README_FRAGMENTS:
        if fragment not in readme:
            errors.append(
                f"environments/README.md must contain {fragment!r}"
            )
    for fragment in _FORBIDDEN_README_FRAGMENTS:
        if fragment in readme:
            errors.append(
                f"environments/README.md must not reference retired {fragment!r}"
            )

    result: dict[str, object] = {
        "schema": contract.get("schema_version"),
        "owned_files": actual_files,
        "recipes": sorted(recipes),
        "provider_families": sorted(provider_profiles),
        "errors": errors,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-current",
        action="store_true",
        help="Print the complete current projection as JSON.",
    )
    args = parser.parse_args()
    result = validate()
    if args.show_current or result["errors"]:
        print(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        print("CALM source environment ownership is inconsistent.")
        return 1
    print(
        "CALM source environments are exact: "
        f"{len(result['recipes'])} recipes, "
        f"{len(result['provider_families'])} registered providers."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
