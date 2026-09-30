"""Ownership guardrails for project follow-up orchestration."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _class_node(relative_path: str, class_name: str) -> ast.ClassDef:
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"{class_name} not found in {relative_path}")


def _method(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
    raise AssertionError(f"{node.name}.{name} not found")


def _argument_names(function: ast.FunctionDef) -> set[str]:
    args = function.args
    return {
        argument.arg
        for argument in [
            *args.posonlyargs,
            *args.args,
            *args.kwonlyargs,
        ]
        if argument.arg != "self"
    }


def _caught_exceptions(function: ast.FunctionDef) -> set[str]:
    caught: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        if isinstance(node.type, ast.Name):
            caught.add(node.type.id)
        elif isinstance(node.type, ast.Tuple):
            caught.update(
                element.id
                for element in node.type.elts
                if isinstance(element, ast.Name)
            )
    return caught


def _call_keywords(function: ast.FunctionDef, method_name: str) -> set[str]:
    keywords: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != method_name:
            continue
        keywords.update(
            keyword.arg for keyword in node.keywords if keyword.arg is not None
        )
    return keywords


def test_each_followup_orchestrator_has_one_execution_entrypoint() -> None:
    cases = (
        (
            "calm/project/application/followups/strain_scan.py",
            "StrainPartitionScanOrchestrator",
        ),
        (
            "calm/project/application/followups/registry_search.py",
            "RegistrySearchOrchestrator",
        ),
        (
            "calm/project/application/followups/relaxation.py",
            "RelaxationOrchestrator",
        ),
        (
            "calm/project/application/followups/energy.py",
            "EnergyOrchestrator",
        ),
    )
    retired = {
        "start_scan",
        "start_search",
        "start_search_run",
        "start_relaxation_run",
        "_run_stage_impl",
    }

    for path, class_name in cases:
        node = _class_node(path, class_name)
        methods = {
            item.name for item in node.body if isinstance(item, ast.FunctionDef)
        }
        assert "run_stage" in methods
        assert methods.isdisjoint(retired)
        assert "params" not in _argument_names(_method(node, "run_stage"))


def test_followups_service_uses_exact_run_stage_contracts() -> None:
    node = _class_node(
        "calm/project/application/followups/service.py",
        "FollowupsService",
    )
    methods = {
        item.name: item
        for item in node.body
        if isinstance(item, ast.FunctionDef)
    }

    for name in (
        "start_strain_partition_scan",
        "start_registry_search",
        "start_relaxation_run",
    ):
        function = methods[name]
        assert "params" not in _argument_names(function)
        called = {
            call.func.attr
            for call in ast.walk(function)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        }
        assert "run_stage" in called
        assert not any(isinstance(item, ast.With) for item in ast.walk(function))


def test_workspace_and_public_stage_boundaries_do_not_retry_type_errors() -> None:
    workspace = _class_node("calm/project/runtime/workspace.py", "Workspace")
    project = _class_node("calm/public/project.py", "Project")

    workspace_methods = (
        "start_strain_partition_scan",
        "start_registry_search",
        "start_relaxation_run",
        "run_registry_stage",
        "run_relaxation_stage",
        "run_energy_stage",
    )
    for name in workspace_methods:
        function = _method(workspace, name)
        assert "params" not in _argument_names(function)
        assert "TypeError" not in _caught_exceptions(function)

    for name in ("run_registry_stage", "run_relaxation_stage", "run_energy_stage"):
        assert not any(
            isinstance(item, ast.With)
            and any(
                isinstance(name_node, ast.Name) and name_node.id == "uow_obj"
                for name_node in ast.walk(item.items[0].context_expr)
            )
            for item in ast.walk(_method(workspace, name))
        )

    registry_keywords = _call_keywords(
        _method(workspace, "run_registry_stage"),
        "run_stage",
    )
    assert "resume" in registry_keywords

    project_methods = {
        item.name for item in project.body if isinstance(item, ast.FunctionDef)
    }
    assert {
        "_run_registry_stage",
        "_run_relaxation_stage",
        "_run_energy_stage",
    }.isdisjoint(project_methods)


def test_historical_registry_chain_is_absent() -> None:
    workspace = _class_node("calm/project/runtime/workspace.py", "Workspace")
    retired = "start_registry_search_from_strain_partition_scan"

    for node in (workspace,):
        methods = {
            item.name for item in node.body if isinstance(item, ast.FunctionDef)
        }
        assert retired not in methods


def test_strain_scan_keeps_energy_backend_import_lazy() -> None:
    tree = ast.parse(
        (ROOT / "calm/project/application/followups/strain_scan.py").read_text(
            encoding="utf-8"
        )
    )
    top_level_imports = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "interface_energy" not in top_level_imports
