"""Architecture guardrails for public relaxation workflow ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
SERVICE_SOURCE = ROOT / "calm" / "public" / "workflows" / "relaxation.py"


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


def test_project_relaxation_methods_are_thin_service_delegates() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    method = _method(project, "relax_interfaces")
    attributes = _self_attributes(method)
    assert "_relaxation_workflows" in attributes
    assert attributes.isdisjoint(
        {
            "_workspace",
            "_repo",
            "refined_interfaces",
            "relaxed_interfaces",
            "interface",
            "run",
        }
    )
    assert not any(isinstance(item, ast.For) for item in ast.walk(method))
    assert not any(isinstance(item, ast.ExceptHandler) for item in ast.walk(method))


def test_project_no_longer_owns_relaxation_target_normalization() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    method_names = {
        node.name for node in project.body if isinstance(node, ast.FunctionDef)
    }
    assert "_relaxation_interface_record" not in method_names
    assert "_relaxation_target_ids" not in method_names
    assert "_run_relaxation_stage" not in method_names


def test_relaxation_service_owns_public_workflow_composition() -> None:
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectRelaxationWorkflowService" in source
    assert "def relax_interfaces(" in source
    assert "def run_relaxation_stage(" in source
    assert "RelaxSettings" in source
    assert "RelaxationResultCollection(" in source
    assert "RelaxationWorkflowResult(" in source
    assert "run_relaxation_stage(" in source


def test_relaxation_service_is_internal_not_a_top_level_api() -> None:
    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    assert "ProjectRelaxationWorkflowService" not in api_source
    assert "ProjectRelaxationWorkflowService" not in init_source
