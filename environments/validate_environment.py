#!/usr/bin/env python3
"""Validate one explicit CALM source-checkout environment profile."""

from __future__ import annotations

import argparse
from importlib import metadata, util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-source-environments.json"
)
_REPORT_SCHEMA = "calm.source_environment_validation.v1"


def _load_contract(path: Path = CONTRACT) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("source environment contract must be a JSON object")
    return payload


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = value.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError(f"invalid numeric version projection {value!r}")
    return tuple(int(part) for part in parts)


def _module_available(name: str) -> bool:
    try:
        return util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _check(
    checks: list[dict[str, object]],
    *,
    name: str,
    passed: bool,
    detail: str,
) -> None:
    checks.append(
        {
            "detail": detail,
            "name": name,
            "passed": bool(passed),
        }
    )


def _check_distribution_imports(
    checks: list[dict[str, object]],
    imports: Mapping[str, str],
) -> None:
    for distribution, import_name in imports.items():
        try:
            version = metadata.version(distribution)
        except metadata.PackageNotFoundError:
            _check(
                checks,
                name=f"distribution:{distribution}",
                passed=False,
                detail="distribution metadata is not installed",
            )
            continue
        available = _module_available(import_name)
        _check(
            checks,
            name=f"distribution:{distribution}",
            passed=available,
            detail=(
                f"{version}; import {import_name!r} is available"
                if available
                else f"{version}; import {import_name!r} is unavailable"
            ),
        )


def _check_required_imports(
    checks: list[dict[str, object]],
    imports: list[str],
) -> None:
    for import_name in imports:
        available = _module_available(import_name)
        _check(
            checks,
            name=f"import:{import_name}",
            passed=available,
            detail=(
                "import is available" if available else "import is unavailable"
            ),
        )


def _check_any_import(
    checks: list[dict[str, object]],
    imports: list[str],
) -> None:
    if not imports:
        return
    available = [name for name in imports if _module_available(name)]
    _check(
        checks,
        name="import:any-provider-adapter",
        passed=bool(available),
        detail=(
            "available: " + ", ".join(available)
            if available
            else "none available from: " + ", ".join(imports)
        ),
    )


def _check_python(
    checks: list[dict[str, object]],
    validation: Mapping[str, Any],
) -> None:
    minimum = _version_tuple(str(validation["python_minimum"]))
    maximum = _version_tuple(
        str(validation["python_maximum_exclusive"])
    )
    observed = sys.version_info[:2]
    passed = minimum <= observed < maximum
    _check(
        checks,
        name="python",
        passed=passed,
        detail=(
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}; required >="
            f"{validation['python_minimum']},<"
            f"{validation['python_maximum_exclusive']}"
        ),
    )


def _check_calm_installation(
    checks: list[dict[str, object]],
    *,
    project_smoke: bool,
) -> None:
    try:
        installed_version = metadata.version("calm")
    except metadata.PackageNotFoundError:
        _check(
            checks,
            name="calm:distribution",
            passed=False,
            detail="CALM distribution metadata is not installed",
        )
        return

    try:
        import calm
    except Exception as exc:  # pragma: no cover - exercised in real environments.
        _check(
            checks,
            name="calm:import",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
        return

    module_version = str(getattr(calm, "__version__", ""))
    _check(
        checks,
        name="calm:version",
        passed=module_version == installed_version,
        detail=(
            f"module={module_version!r}; distribution={installed_version!r}"
        ),
    )

    module_path = Path(calm.__file__).resolve()
    expected_root = (REPO_ROOT / "calm").resolve()
    source_checkout = module_path == expected_root / "__init__.py"
    _check(
        checks,
        name="calm:source-checkout",
        passed=source_checkout,
        detail=f"imported from {module_path}",
    )

    if not project_smoke:
        return
    try:
        with tempfile.TemporaryDirectory(prefix="calm-environment-") as tmp:
            project_path = Path(tmp) / "environment-check.calm"
            created = calm.open_project(project_path)
            created.summary()
            reopened = calm.open_project(project_path)
            reopened.summary()
            passed = created.path == project_path and reopened.path == project_path
    except Exception as exc:  # pragma: no cover - exercised in real environments.
        _check(
            checks,
            name="calm:project-smoke",
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
    else:
        _check(
            checks,
            name="calm:project-smoke",
            passed=passed,
            detail="disposable project created and reopened",
        )


def _check_provider_registry(
    checks: list[dict[str, object]],
    family: str,
) -> None:
    try:
        from calm.calculators.registry import default_registry

        providers = {
            info.family: info for info in default_registry().info()
        }
    except Exception as exc:  # pragma: no cover - real environment failure.
        _check(
            checks,
            name=f"provider:{family}",
            passed=False,
            detail=f"could not inspect registry: {type(exc).__name__}: {exc}",
        )
        return
    info = providers.get(family)
    if info is None:
        _check(
            checks,
            name=f"provider:{family}",
            passed=False,
            detail="family is not registered",
        )
        return
    _check(
        checks,
        name=f"provider:{family}",
        passed=bool(info.available),
        detail=(
            "registered and dependency-visible"
            if info.available
            else "registered but required imports are unavailable"
        ),
    )


def validate_environment(
    *,
    profile: str | None = None,
    provider: str | None = None,
    contract_path: Path = CONTRACT,
) -> dict[str, object]:
    contract = _load_contract(contract_path)
    validation = contract["validation"]
    provider_profiles = contract["provider_profiles"]
    if profile is not None and provider is not None:
        raise ValueError("profile and provider are mutually exclusive")
    if profile is None and provider is None:
        profile = str(validation["default_profile"])
    if provider is not None:
        if provider not in provider_profiles:
            raise ValueError(
                f"unknown provider {provider!r}; choose from "
                f"{sorted(provider_profiles)}"
            )
        selected_profile = "provider"
    else:
        supported = set(validation["supported_profiles"])
        if profile not in supported - {"provider"}:
            raise ValueError(
                f"unknown profile {profile!r}; choose 'base' or 'science'"
            )
        selected_profile = str(profile)

    checks: list[dict[str, object]] = []
    notes: list[str] = []
    _check_python(checks, validation)

    dependency_profiles = contract["dependency_profiles"]
    _check_distribution_imports(
        checks, dependency_profiles["base"]["imports"]
    )
    if selected_profile in {"science", "provider"}:
        _check_distribution_imports(
            checks, dependency_profiles["science"]["imports"]
        )

    expected_environment: str | None = None
    if provider is not None:
        provider_profile = provider_profiles[provider]
        expected_environment = provider_profile["environment_name"]
        _check_distribution_imports(
            checks, provider_profile["distribution_imports"]
        )
        _check_required_imports(
            checks, provider_profile["required_imports"]
        )
        _check_any_import(checks, provider_profile["import_any"])

    _check_calm_installation(
        checks,
        project_smoke=bool(validation["project_smoke"]),
    )
    if provider is not None:
        _check_provider_registry(checks, provider)
        provider_profile = provider_profiles[provider]
        if provider_profile["external_runtime_required"]:
            notes.append(
                f"Provider {provider!r} requires an external runtime or files "
                "that this environment validator does not inspect."
            )

    conda_environment = os.environ.get("CONDA_DEFAULT_ENV") or None
    if expected_environment and conda_environment not in {
        None,
        expected_environment,
    }:
        notes.append(
            f"Active conda environment is {conda_environment!r}; the reviewed "
            f"recipe name is {expected_environment!r}. CLI name overrides are "
            "permitted, so this is informational."
        )

    passed = all(bool(item["passed"]) for item in checks)
    return {
        "checks": checks,
        "conda_environment": conda_environment,
        "notes": notes,
        "passed": passed,
        "profile": selected_profile,
        "provider": provider,
        "schema": _REPORT_SCHEMA,
    }


def _print_human(report: Mapping[str, object]) -> None:
    provider = report.get("provider")
    title = (
        f"CALM source environment: provider {provider}"
        if provider
        else f"CALM source environment: {report['profile']}"
    )
    print(title)
    print("=" * len(title))
    for raw in report["checks"]:
        item = raw
        marker = "PASS" if item["passed"] else "FAIL"
        print(f"[{marker}] {item['name']}: {item['detail']}")
    for note in report["notes"]:
        print(f"[NOTE] {note}")
    print()
    message = (
        "Environment validation passed."
        if report["passed"]
        else "Environment validation failed."
    )
    print(message)


def main() -> int:
    contract = _load_contract()
    providers = sorted(contract["provider_profiles"])
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--profile",
        choices=("base", "science"),
        help="Validate the import-light base or baseline science layer.",
    )
    group.add_argument(
        "--provider",
        choices=providers,
        help="Validate the science layer plus one registered provider.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the machine-readable validation report.",
    )
    args = parser.parse_args()
    report = validate_environment(
        profile=args.profile,
        provider=args.provider,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
