"""Architecture guardrails for public interface workflow ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
BUILD_SOURCE = ROOT / "calm" / "public" / "workflows" / "interface_build.py"
REFINEMENT_SOURCE = ROOT / "calm" / "public" / "workflows" / "interface_refinement.py"


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


def test_project_interface_methods_are_thin_service_delegates() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    expected = {
        "build_interfaces": "_interface_builds",
        "refine_interfaces": "_interface_refinements",
        "refine_registry": "_interface_refinements",
    }
    for name, owner in expected.items():
        method = _method(project, name)
        attributes = _self_attributes(method)
        assert owner in attributes
        assert attributes.isdisjoint({"_workspace", "_repo", "_saver"})
        assert not any(isinstance(item, ast.For) for item in ast.walk(method))
        assert not any(isinstance(item, ast.ExceptHandler) for item in ast.walk(method))


def test_project_no_longer_owns_low_level_interface_execution_bridges() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    method_names = {
        node.name for node in project.body if isinstance(node, ast.FunctionDef)
    }
    assert {
        "_build_interface_from_prototype",
        "_create_derived_interface",
        "_get_derived_interface",
        "_start_strain_partition_scan",
        "_derive_interfaces_from_strain_partition_scan",
        "_start_registry_search",
        "_derive_interfaces_from_registry_search",
        "_run_build_stage",
        "_run_registry_stage",
    }.isdisjoint(method_names)


def test_interface_build_service_owns_selection_build_and_persistence() -> None:
    source = BUILD_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectInterfaceBuildService" in source
    assert "def build_interfaces(" in source
    assert 'select_top(top, by="score")' in source
    assert "validate_buildable()" in source
    assert "build_interface_from_prototype(" in source
    assert "record_interface_model(" in source
    assert "def run_build_stage(" not in source


def test_interface_refinement_service_owns_scan_and_registry_composition() -> None:
    source = REFINEMENT_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectInterfaceRefinementService" in source
    assert "def refine_interfaces(" in source
    assert "def refine_registry(" in source
    assert "start_strain_partition_scan(" in source
    assert "derive_interfaces_from_strain_partition_scan(" in source
    assert "start_registry_search(" in source
    assert "derive_interfaces_from_registry_search(" in source
    assert "InterfaceRefinementResult(" in source
    assert "def run_registry_stage(" not in source


def test_retired_interface_workflow_modules_cannot_return() -> None:
    assert not (ROOT / "calm" / "public" / "_authoritative_build.py").exists()
    assert not (ROOT / "calm" / "public" / "project_interface_workflows.py").exists()
    assert not (ROOT / "calm" / "public" / "_interface_workflows.py").exists()


def test_interface_workflow_services_are_not_top_level_api() -> None:
    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    for name in (
        "ProjectInterfaceBuildService",
        "ProjectInterfaceRefinementService",
    ):
        assert name not in api_source
        assert name not in init_source
