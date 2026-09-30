#!/usr/bin/env python3
"""Verify CALM's reviewed package-ownership and retirement contract."""

from __future__ import annotations

import argparse
import ast
import importlib
from importlib.util import resolve_name
import json
from pathlib import Path
import sys
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "calm"
CONTRACT = (
    REPO_ROOT / "engineering" / "architecture" / "current-package-ownership.json"
)
_SCHEMA_VERSION = "calm.package_ownership.v2"
_RETIREMENT_LIST_FIELDS = (
    "retired_modules",
    "additional_prohibited_import_prefixes",
    "retired_files",
    "retired_source_trees",
    "runtime_import_probes",
)
_RETIREMENT_MAPPING_FIELDS = (
    "retired_source_symbols",
    "retired_attributes",
)


def _sorted_unique_strings(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"{field} must be a list of nonempty strings")
    if value != sorted(value):
        raise ValueError(f"{field} must be sorted")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} contains duplicate values")
    return value


def _string_list_mapping(value: Any, *, field: str) -> dict[str, list[str]]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and key for key in value
    ):
        raise ValueError(f"{field} must be an object keyed by nonempty strings")
    if list(value) != sorted(value):
        raise ValueError(f"{field} keys must be sorted")
    normalized: dict[str, list[str]] = {}
    for key, items in value.items():
        normalized[key] = _sorted_unique_strings(items, field=f"{field}.{key}")
    return normalized


def _validate_relative_path(value: str, *, field: str) -> None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./"):
        raise ValueError(f"{field} must be a repository-relative path: {value!r}")


def _validate_calm_module(value: str, *, field: str) -> None:
    if value != "calm" and not value.startswith("calm."):
        raise ValueError(f"{field} must name a CALM module: {value!r}")


def _validate_retirement_contract(contract: dict[str, Any]) -> None:
    retirement = contract.get("retirement")
    if not isinstance(retirement, dict):
        raise ValueError("retirement must be an object")
    expected_fields = set(_RETIREMENT_LIST_FIELDS) | set(
        _RETIREMENT_MAPPING_FIELDS
    )
    if set(retirement) != expected_fields:
        raise ValueError(
            "retirement fields differ from the reviewed schema: "
            f"expected={sorted(expected_fields)!r}, "
            f"actual={sorted(retirement)!r}"
        )

    lists = {
        field: _sorted_unique_strings(retirement[field], field=f"retirement.{field}")
        for field in _RETIREMENT_LIST_FIELDS
    }
    mappings = {
        field: _string_list_mapping(retirement[field], field=f"retirement.{field}")
        for field in _RETIREMENT_MAPPING_FIELDS
    }

    for field in ("retired_modules", "additional_prohibited_import_prefixes"):
        for module in lists[field]:
            _validate_calm_module(module, field=f"retirement.{field}")
    overlap = set(lists["retired_modules"]) & set(
        lists["additional_prohibited_import_prefixes"]
    )
    if overlap:
        raise ValueError(
            "additional_prohibited_import_prefixes duplicates retired_modules: "
            + ", ".join(sorted(overlap))
        )

    retired_imports = set(lists["retired_modules"]) | set(
        lists["additional_prohibited_import_prefixes"]
    )
    probes = set(lists["runtime_import_probes"])
    if not probes <= retired_imports:
        raise ValueError(
            "runtime_import_probes must be retired import paths: "
            + ", ".join(sorted(probes - retired_imports))
        )
    for module in lists["runtime_import_probes"]:
        _validate_calm_module(module, field="retirement.runtime_import_probes")

    for field in ("retired_files", "retired_source_trees"):
        for relative in lists[field]:
            _validate_relative_path(relative, field=f"retirement.{field}")
    for relative in mappings["retired_source_symbols"]:
        _validate_relative_path(
            relative,
            field="retirement.retired_source_symbols",
        )
    for module in mappings["retired_attributes"]:
        _validate_calm_module(module, field="retirement.retired_attributes")


def _load_contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("Unsupported package-ownership contract schema")
    _validate_retirement_contract(payload)
    return payload


def _retirement(contract: dict[str, Any]) -> dict[str, Any]:
    retirement = contract["retirement"]
    if not isinstance(retirement, dict):
        raise TypeError("retirement contract is not a mapping")
    return retirement


def _retired_import_prefixes(retirement: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(retirement["retired_modules"])
            | set(retirement["additional_prohibited_import_prefixes"])
        )
    )


def _python_source_files(root: Path) -> list[Path]:
    if root.is_file() and root.suffix in {".py", ".pyi"}:
        return [root]
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".pyi"}
        and "__pycache__" not in path.parts
    )


def _module_name(path: Path) -> tuple[str, bool]:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    is_package = relative.name == "__init__"
    parts = relative.parts[:-1] if is_package else relative.parts
    return ".".join(parts), is_package


def _imported_modules(path: Path) -> Iterable[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_name, is_package = _module_name(path)
    package = module_name if is_package else module_name.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = "." * node.level + (node.module or "")
                try:
                    target = resolve_name(relative, package)
                except (ImportError, ValueError) as exc:
                    raise AssertionError(
                        f"{path.relative_to(REPO_ROOT)}:{node.lineno}: "
                        f"invalid relative import {relative!r}"
                    ) from exc
            else:
                target = node.module or ""
            if target:
                yield node.lineno, target


def _module_exists(module: str) -> bool:
    if module == "calm":
        return (PACKAGE_ROOT / "__init__.py").is_file()
    if not module.startswith("calm."):
        return True
    relative = Path(*module.split(".")[1:])
    base = PACKAGE_ROOT / relative
    return any(
        candidate.is_file()
        for candidate in (
            base.with_suffix(".py"),
            base.with_suffix(".pyi"),
            base / "__init__.py",
            base / "__init__.pyi",
        )
    )


def _retired_module_locations(module: str) -> tuple[Path, ...]:
    relative = Path(*module.split("."))
    base = REPO_ROOT / relative
    return (
        base.with_suffix(".py"),
        base.with_suffix(".pyi"),
        base / "__init__.py",
        base / "__init__.pyi",
        base,
    )


def _verify_root_topology(contract: dict[str, Any]) -> None:
    actual_files = sorted(path.name for path in PACKAGE_ROOT.glob("*.py"))
    expected_files = sorted(contract["package_root_files"])
    if actual_files != expected_files:
        raise AssertionError(
            "calm package-root Python files differ from the reviewed map:\n"
            f"expected={expected_files!r}\nactual={actual_files!r}"
        )

    actual_packages = sorted(
        path.name
        for path in PACKAGE_ROOT.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    )
    expected_packages = sorted(contract["top_level_packages"])
    if actual_packages != expected_packages:
        raise AssertionError(
            "Top-level source packages differ from the reviewed map:\n"
            f"expected={expected_packages!r}\nactual={actual_packages!r}"
        )


def _verify_retired_modules(retirement: dict[str, Any]) -> None:
    offenders: list[str] = []
    for module in retirement["retired_modules"]:
        existing = next(
            (path for path in _retired_module_locations(module) if path.exists()),
            None,
        )
        if existing is not None:
            offenders.append(f"{module}: {existing.relative_to(REPO_ROOT)}")
    if offenders:
        raise AssertionError(
            "Retired module paths exist in the source tree:\n" + "\n".join(offenders)
        )


def _verify_retired_files(retirement: dict[str, Any]) -> None:
    offenders = [
        relative
        for relative in retirement["retired_files"]
        if (REPO_ROOT / relative).exists()
    ]
    if offenders:
        raise AssertionError("Retired files exist:\n" + "\n".join(offenders))


def _verify_retired_source_trees(retirement: dict[str, Any]) -> None:
    offenders: list[str] = []
    for relative in retirement["retired_source_trees"]:
        offenders.extend(
            str(path.relative_to(REPO_ROOT))
            for path in _python_source_files(REPO_ROOT / relative)
        )
    if offenders:
        raise AssertionError(
            "Retired source trees contain Python files:\n" + "\n".join(offenders)
        )


def _verify_retired_source_symbols(retirement: dict[str, Any]) -> None:
    missing: list[str] = []
    offenders: list[str] = []
    for relative, symbols in retirement["retired_source_symbols"].items():
        path = REPO_ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        source = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{relative}: {symbol!r}" for symbol in symbols if symbol in source
        )
    if missing:
        raise AssertionError(
            "Retired-symbol contract references missing active source files:\n"
            + "\n".join(missing)
        )
    if offenders:
        raise AssertionError(
            "Retired source symbols remain present:\n" + "\n".join(offenders)
        )


def _verify_retired_attributes(retirement: dict[str, Any]) -> None:
    source_root = str(REPO_ROOT)
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    import_failures: list[str] = []
    offenders: list[str] = []
    for module_name, attributes in retirement["retired_attributes"].items():
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - reported with module context
            import_failures.append(
                f"{module_name}: {type(exc).__name__}: {exc}"
            )
            continue
        offenders.extend(
            f"{module_name}.{attribute}"
            for attribute in attributes
            if hasattr(module, attribute)
        )
    if import_failures:
        raise AssertionError(
            "Could not import active runtime owners for retirement checks:\n"
            + "\n".join(import_failures)
        )
    if offenders:
        raise AssertionError(
            "Retired runtime attributes remain present:\n" + "\n".join(offenders)
        )


def _verify_active_imports(contract: dict[str, Any]) -> None:
    retired = _retired_import_prefixes(_retirement(contract))
    missing: list[str] = []
    retired_imports: list[str] = []
    seen: set[Path] = set()
    for relative in contract["active_import_roots"]:
        for path in _python_source_files(REPO_ROOT / relative):
            if path in seen:
                continue
            seen.add(path)
            for line, module in _imported_modules(path):
                if not module.startswith("calm"):
                    continue
                location = f"{path.relative_to(REPO_ROOT)}:{line}: {module}"
                if any(
                    module == prefix or module.startswith(f"{prefix}.")
                    for prefix in retired
                ):
                    retired_imports.append(location)
                if not _module_exists(module):
                    missing.append(location)
    if retired_imports:
        raise AssertionError(
            "Active source imports retired CALM paths:\n" + "\n".join(retired_imports)
        )
    if missing:
        raise AssertionError(
            "Active source imports missing CALM modules:\n" + "\n".join(missing)
        )


def _verify_top_level_dependencies(contract: dict[str, Any]) -> None:
    violations: list[str] = []
    owners = contract["top_level_packages"]
    for owner, metadata in owners.items():
        allowed = set(metadata["allowed_calm_import_roots"])
        for path in _python_source_files(PACKAGE_ROOT / owner):
            for line, module in _imported_modules(path):
                if not module.startswith("calm."):
                    continue
                target = module.split(".", 2)[1]
                if target == owner:
                    continue
                if target not in allowed:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{line}: "
                        f"{owner} -> {target} via {module}"
                    )
    if violations:
        raise AssertionError(
            "Top-level package dependency violations:\n" + "\n".join(violations)
        )


def _verify_internal_layers(
    *, package: str, layers: dict[str, list[str]]
) -> None:
    violations: list[str] = []
    root = PACKAGE_ROOT / package
    for owner, allowed_values in layers.items():
        allowed = set(allowed_values)
        for path in _python_source_files(root / owner):
            for line, module in _imported_modules(path):
                prefix = f"calm.{package}."
                if not module.startswith(prefix):
                    continue
                remainder = module[len(prefix) :]
                target = remainder.split(".", 1)[0]
                if target == owner:
                    continue
                if target not in allowed:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{line}: "
                        f"{package}.{owner} -> {package}.{target} via {module}"
                    )
    if violations:
        raise AssertionError(
            f"{package} internal-layer dependency violations:\n"
            + "\n".join(violations)
        )


def _retirement_projection(retirement: dict[str, Any]) -> dict[str, int]:
    return {
        "retired_module_count": len(retirement["retired_modules"]),
        "additional_prohibited_import_prefix_count": len(
            retirement["additional_prohibited_import_prefixes"]
        ),
        "prohibited_import_prefix_count": len(
            _retired_import_prefixes(retirement)
        ),
        "retired_file_count": len(retirement["retired_files"]),
        "retired_source_tree_count": len(retirement["retired_source_trees"]),
        "retired_source_symbol_count": sum(
            len(symbols)
            for symbols in retirement["retired_source_symbols"].values()
        ),
        "retired_attribute_count": sum(
            len(attributes)
            for attributes in retirement["retired_attributes"].values()
        ),
        "runtime_import_probe_count": len(retirement["runtime_import_probes"]),
    }


def current_projection() -> dict[str, Any]:
    contract = _load_contract()
    return {
        "schema_version": contract["schema_version"],
        "package_root_files": sorted(path.name for path in PACKAGE_ROOT.glob("*.py")),
        "top_level_packages": sorted(
            path.name
            for path in PACKAGE_ROOT.iterdir()
            if path.is_dir() and (path / "__init__.py").is_file()
        ),
        "retirement": _retirement_projection(_retirement(contract)),
    }


def verify() -> None:
    contract = _load_contract()
    retirement = _retirement(contract)
    _verify_root_topology(contract)
    _verify_retired_modules(retirement)
    _verify_retired_files(retirement)
    _verify_retired_source_trees(retirement)
    _verify_retired_source_symbols(retirement)
    _verify_active_imports(contract)
    _verify_top_level_dependencies(contract)
    _verify_internal_layers(package="project", layers=contract["project_layers"])
    _verify_internal_layers(package="public", layers=contract["public_layers"])
    _verify_retired_attributes(retirement)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-current", action="store_true")
    args = parser.parse_args()
    try:
        if args.show_current:
            print(json.dumps(current_projection(), indent=2, sort_keys=True))
            return 0
        verify()
    except Exception as exc:
        print(f"Package organization check failed: {exc}", file=sys.stderr)
        return 1
    projection = current_projection()
    retirement = projection["retirement"]
    print(
        "Package organization verified: "
        f"{len(projection['package_root_files'])} root modules, "
        f"{len(projection['top_level_packages'])} top-level packages, "
        f"{retirement['prohibited_import_prefix_count']} retired import prefixes, "
        "reviewed dependency, layer, and retirement boundaries."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
