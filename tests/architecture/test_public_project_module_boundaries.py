"""Architecture guardrails for the public Project facade decomposition."""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _module_ast(relative_path: str) -> ast.Module:
    return ast.parse((_REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def _imported_from_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_project_facade_delegates_query_and_save_ownership() -> None:
    tree = _module_ast("calm/public/project.py")
    modules = _imported_from_modules(tree)

    assert "calm.public.queries.project" in modules
    assert "calm.public.workflows.saving" in modules
    assert "calm.public.workflows.interface_search" in modules
    assert "calm.public.workflows.interface_build" in modules
    assert "calm.public.workflows.interface_refinement" in modules
    assert "calm.public.workflows.relaxation" in modules
    assert "calm.public.workflows.energy" in modules
    assert "calm.public.workflows.datasets" in modules
    assert "calm.public.workflows.campaigns" in modules
    assert not any("sidecar" in module for module in modules)


def test_project_facade_does_not_import_save_target_classes_directly() -> None:
    tree = _module_ast("calm/public/project.py")

    # Save dispatch belongs in calm.public.workflows.saving, not the public facade.
    # Match exact AST identifiers rather than substrings so typed workflow
    # collections such as EnergyResultCollection remain legitimate.
    imported_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    referenced_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    forbidden = {
        "InterfaceSearchResult",
        "InterfaceModel",
        "EnergyResult",
        "InterfaceEnergyScalarResult",
    }
    assert forbidden.isdisjoint(imported_names)
    assert forbidden.isdisjoint(referenced_names)


def test_project_helper_modules_are_not_public_reexport_shims() -> None:
    queries = _module_ast("calm/public/queries/project.py")
    saving = _module_ast("calm/public/workflows/saving.py")

    query_classes = {node.name for node in ast.walk(queries) if isinstance(node, ast.ClassDef)}
    save_classes = {node.name for node in ast.walk(saving) if isinstance(node, ast.ClassDef)}

    assert "PublicProjectQueries" in query_classes
    assert "PublicProjectSaver" in save_classes
