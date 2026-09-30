"""Ownership guardrails for exact persisted build-stage orchestration."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))


def _class(relative_path: str, name: str) -> ast.ClassDef:
    for node in _tree(relative_path).body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {relative_path}")


def _function(node: ast.Module | ast.ClassDef, name: str) -> ast.FunctionDef:
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
    raise AssertionError(f"{name} not found")


def test_build_stage_owns_exact_run_lifecycle_and_fresh_uows() -> None:
    node = _class(
        "calm/project/application/build_stage.py",
        "BuildStageOrchestrator",
    )
    source = ast.unparse(node)
    assert "fresh non-entered UnitOfWork" in source
    assert "mark_running" in source
    assert "mark_done" in source
    assert "mark_failed" in source
    assert "best-effort" not in source
    assert "persist_atoms" not in source
    assert not any(
        isinstance(handler.type, ast.Name) and handler.type.id == "TypeError"
        for handler in ast.walk(node)
        if isinstance(handler, ast.ExceptHandler) and handler.type is not None
    )


def test_interface_builder_uses_only_current_identifier_contract() -> None:
    function = _function(
        _tree("calm/project/application/interface_building.py"),
        "build_interface_model_from_prototype",
    )
    source = ast.unparse(function)
    assert "resolve_prototype" in source
    assert ".resolve(" not in source
    assert "hasattr(" not in source
    assert not any(
        isinstance(node, ast.ExceptHandler) for node in ast.walk(function)
    )


def test_workspace_build_adapters_use_fresh_factory_once() -> None:
    workspace = _class("calm/project/runtime/workspace.py", "Workspace")
    direct = _function(workspace, "build_interface_from_prototype")
    staged = _function(workspace, "run_build_stage")
    direct_source = ast.unparse(direct)
    staged_source = ast.unparse(staged)

    assert "self._fresh_uow()" in direct_source
    assert "self._uow_factory()" not in direct_source
    assert not any(
        isinstance(node, ast.ExceptHandler) for node in ast.walk(direct)
    )
    calls = [
        node
        for node in ast.walk(staged)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BuildStageOrchestrator"
    ]
    assert len(calls) == 1
    assert "persist_atoms" not in staged_source


def test_public_build_service_has_no_low_level_stage_adapter() -> None:
    service = _class(
        "calm/public/workflows/interface_build.py",
        "ProjectInterfaceBuildService",
    )
    method_names = {
        item.name for item in service.body if isinstance(item, ast.FunctionDef)
    }
    assert "build_interfaces" in method_names
    assert "run_build_stage" not in method_names


def test_project_has_no_private_build_stage_delegate() -> None:
    project = _class("calm/public/project.py", "Project")
    method_names = {
        item.name for item in project.body if isinstance(item, ast.FunctionDef)
    }
    assert "_run_build_stage" not in method_names
