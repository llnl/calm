"""Architecture guardrails for public named-search workflow ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
SERVICE_SOURCE = ROOT / "calm" / "public" / "workflows" / "interface_search.py"


def _class(path: Path, name: str) -> ast.ClassDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == name
    )


def _method(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(
        item
        for item in node.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )


def _self_attributes(node: ast.AST) -> set[str]:
    return {
        item.attr
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        and isinstance(item.value, ast.Name)
        and item.value.id == "self"
    }


def test_project_search_methods_are_thin_service_delegates() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    for name in ("search", "search_interfaces"):
        method = _method(project, name)
        attributes = _self_attributes(method)
        assert "_search_workflows" in attributes
        assert attributes.isdisjoint(
            {
                "_adapter",
                "_repo",
                "_saver",
                "searches",
            }
        )
        assert not any(isinstance(item, ast.For) for item in ast.walk(method))
        assert not any(
            isinstance(item, ast.ExceptHandler) for item in ast.walk(method)
        )


def test_project_no_longer_owns_search_selector_normalization() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    method_names = {
        node.name for node in project.body if isinstance(node, ast.FunctionDef)
    }
    assert "_search_name" not in method_names


def test_search_service_owns_public_workflow_composition() -> None:
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectInterfaceSearchWorkflowService" in source
    assert "def search(" in source
    assert "def search_interfaces(" in source
    assert "build_search_identity(" in source
    assert "prepare_interface_search(" in source
    assert "record_search_result(" in source
    assert "complete_interface_search(" in source
    assert "fail_interface_search(" in source
    assert "PersistedInterfaceSearch(" in source


def test_database_search_service_remains_lifecycle_owner() -> None:
    source = (
        ROOT / "calm" / "project" / "application" / "interface_searches.py"
    ).read_text(encoding="utf-8")
    assert "class InterfaceSearchesService" in source
    assert "def prepare(" in source
    assert "def complete(" in source
    assert "def fail(" in source
    assert "get_by_search_identity" in source
    assert "get_by_run_uid_full" in source


def test_search_workflow_service_is_internal_not_a_top_level_api() -> None:
    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    assert "ProjectInterfaceSearchWorkflowService" not in api_source
    assert "ProjectInterfaceSearchWorkflowService" not in init_source
