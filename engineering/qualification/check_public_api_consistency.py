#!/usr/bin/env python3
"""Verify CALM's reviewed single-public-API contract.

This checker is deliberately not a freeze.  It rejects inconsistency between
reviewed metadata, runtime exports, Project operations, documentation, and the
current persistence schemas.  Deliberate API revisions are made by updating the
implementation and reviewed contract together.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "engineering" / "architecture" / "current-public-contract.json"
PUBLIC_API = REPO_ROOT / "public_api.md"
INTERNAL_ROOTS = (
    "calm/public/__init__.py",
    "calm/project/__init__.py",
    "calm/interface/__init__.py",
    "calm/slab/__init__.py",
    "calm/bulk/__init__.py",
    "calm/calculators/__init__.py",
    "calm/viz/__init__.py",
)


def _load_contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "calm.public_api_contract.v4":
        raise ValueError("Unsupported public API contract schema")
    return payload


def _marked_rows(begin: str, end: str) -> list[dict[str, str]]:
    lines = PUBLIC_API.read_text(encoding="utf-8").splitlines()
    i0 = lines.index(begin) + 1
    i1 = lines.index(end)
    header: list[str] | None = None
    rows: list[dict[str, str]] = []
    for raw in lines[i0:i1]:
        if not raw.startswith("|"):
            continue
        parts = [part.strip() for part in raw.strip("|").split("|")]
        if not parts or set(parts[0]) == {"-"}:
            continue
        if header is None:
            header = parts
            continue
        rows.append(dict(zip(header, parts)))
    return rows


def _project_method_names() -> list[str]:
    tree = ast.parse(
        (REPO_ROOT / "calm" / "public" / "project.py").read_text(encoding="utf-8")
    )
    project = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Project"
    )
    return [
        node.name
        for node in project.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]


def _assert_internal_roots_are_not_aggregators() -> None:
    errors: list[str] = []
    for relative in INTERNAL_ROOTS:
        path = REPO_ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                    errors.append(f"{relative}: defines __all__")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__":
                errors.append(f"{relative}: defines __getattr__")
            elif isinstance(node, ast.Import):
                errors.append(f"{relative}: imports runtime names")
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                errors.append(f"{relative}: imports from {node.module!r}")
    if errors:
        raise AssertionError("Internal package-root API leakage:\n" + "\n".join(errors))


def current_projection() -> dict[str, Any]:
    sys.path.insert(0, str(REPO_ROOT))
    import calm.api as api
    from calm.project.domain.schema import (
        AUTOMATIC_PROJECT_MIGRATION_SUPPORTED,
        CURRENT_SCHEMA_VERSION,
        IN_PLACE_PROJECT_REPAIR_SUPPORTED,
        PROJECT_COMPATIBILITY_POLICY,
        PROJECT_RELEASE_STAGE,
    )

    contract = _load_contract()
    documented_exports = [row["Import path"] for row in _marked_rows(
        "<!-- public-api-table:begin -->", "<!-- public-api-table:end -->"
    )]
    documented_methods = [
        row["Method"].removeprefix("Project.")
        for row in _marked_rows(
            "<!-- project-method-table:begin -->", "<!-- project-method-table:end -->"
        )
    ]
    documented_workflow_objects = _marked_rows(
        "<!-- workflow-object-table:begin -->",
        "<!-- workflow-object-table:end -->",
    )
    return {
        "contract_exports": [row["name"] for row in contract["exports"]],
        "runtime_exports": list(api.PUBLIC_EXPORTS),
        "contract_implementations": [
            row["implementation"] for row in contract["exports"]
        ],
        "runtime_implementations": [
            f"{module_path}.{attribute}"
            for name in api.PUBLIC_EXPORTS
            for module_path, attribute in (api._EXPORT_MAP[name],)
        ],
        "contract_project_methods": [row["name"] for row in contract["project_methods"]],
        "runtime_project_methods": _project_method_names(),
        "documented_exports": documented_exports,
        "documented_project_methods": documented_methods,
        "documented_workflow_objects": documented_workflow_objects,
        "release_stage": PROJECT_RELEASE_STAGE,
        "database_schema_version": CURRENT_SCHEMA_VERSION,
        "project_compatibility_policy": PROJECT_COMPATIBILITY_POLICY,
        "automatic_project_migration_supported": (
            AUTOMATIC_PROJECT_MIGRATION_SUPPORTED
        ),
        "in_place_project_repair_supported": IN_PLACE_PROJECT_REPAIR_SUPPORTED,
    }


def verify() -> None:
    contract = _load_contract()
    projection = current_projection()

    expected_exports = [row["name"] for row in contract["exports"]]
    if projection["runtime_exports"] != expected_exports:
        raise AssertionError(
            "Runtime calm exports differ from the reviewed contract:\n"
            f"contract={expected_exports!r}\nruntime={projection['runtime_exports']!r}"
        )

    expected_imports = [row["import_path"] for row in contract["exports"]]
    if projection["documented_exports"] != expected_imports:
        raise AssertionError("public_api.md canonical imports differ from the contract")

    expected_implementations = [
        row["implementation"] for row in contract["exports"]
    ]
    if projection["runtime_implementations"] != expected_implementations:
        raise AssertionError(
            "Public implementation owners differ from the reviewed contract:\n"
            f"contract={expected_implementations!r}\n"
            f"runtime={projection['runtime_implementations']!r}"
        )

    expected_methods = [row["name"] for row in contract["project_methods"]]
    if projection["runtime_project_methods"] != expected_methods:
        raise AssertionError(
            "Project public methods differ from the reviewed contract:\n"
            f"contract={expected_methods!r}\nruntime={projection['runtime_project_methods']!r}"
        )
    if projection["documented_project_methods"] != expected_methods:
        raise AssertionError("public_api.md Project methods differ from the contract")

    expected_workflow_objects = [
        {
            "Object": row["name"],
            "Implementation owner": row["implementation"],
            "Role": row["role"],
        }
        for row in contract["workflow_objects"]
    ]
    if projection["documented_workflow_objects"] != expected_workflow_objects:
        raise AssertionError(
            "public_api.md returned workflow objects differ from the contract"
        )

    if projection["release_stage"] != contract["release_stage"]:
        raise AssertionError("Release-stage metadata differs from the contract")

    persistence = contract["persistence"]
    if projection["database_schema_version"] != persistence["database_schema_version"]:
        raise AssertionError("Database schema metadata differs from the contract")
    if (
        projection["project_compatibility_policy"]
        != persistence["compatibility_policy"]
    ):
        raise AssertionError("Project compatibility policy differs from the contract")
    if (
        projection["automatic_project_migration_supported"]
        != persistence["automatic_migration"]
    ):
        raise AssertionError("Automatic-migration policy differs from the contract")
    if (
        projection["in_place_project_repair_supported"]
        != persistence["in_place_repair"]
    ):
        raise AssertionError("In-place-repair policy differs from the contract")

    positive = set(expected_imports)
    retired = set(contract["retired_top_level_exports"])
    overlap = positive & retired
    if overlap:
        raise AssertionError(f"Retired and supported imports overlap: {sorted(overlap)}")

    _assert_internal_roots_are_not_aggregators()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-current", action="store_true")
    args = parser.parse_args()
    try:
        projection = current_projection()
        if args.show_current:
            print(json.dumps(projection, indent=2, sort_keys=True))
            return 0
        verify()
    except Exception as exc:
        print(f"Public API consistency check failed: {exc}", file=sys.stderr)
        return 1
    print(
        "Public API consistency verified: "
        f"{projection['release_stage']} contract, "
        f"{len(projection['runtime_exports'])} canonical imports, "
        f"{len(projection['runtime_project_methods'])} Project operations, "
        f"database schema {projection['database_schema_version']}, "
        f"project policy {projection['project_compatibility_policy']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
