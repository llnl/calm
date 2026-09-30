"""Ownership guardrails for exact follow-up persistence and resume lookup."""

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


def _called_attributes(function: ast.FunctionDef) -> set[str]:
    return {
        call.func.attr
        for call in ast.walk(function)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    }


def test_shared_persistence_helpers_do_not_own_or_suppress_transactions() -> None:
    module = _tree("calm/project/application/followups/orch_helpers.py")
    for name in (
        "load_existing_followups",
        "persist_artifact_payloads",
        "persist_followups_with_edges",
    ):
        function = _function(module, name)
        assert not any(isinstance(node, ast.With) for node in ast.walk(function))
        assert not any(
            isinstance(node, ast.ExceptHandler) for node in ast.walk(function)
        )
        calls = _called_attributes(function)
        assert "commit" not in calls
        assert "rollback" not in calls


def test_shared_persistence_helpers_write_required_rows_and_lineage() -> None:
    module = _tree("calm/project/application/followups/orch_helpers.py")
    artifacts = _function(module, "persist_artifact_payloads")
    followups = _function(module, "persist_followups_with_edges")

    assert "put_bytes_in" in _called_attributes(artifacts)
    artifact_source = ast.unparse(artifacts)
    assert "artifacts.put_bytes_in" in artifact_source
    assert "uow.artifacts.add" not in artifact_source
    assert "uow.edges.add" not in artifact_source
    assert "prototype_uid_full" in artifact_source
    assert "target_uid_full" in artifact_source
    assert "lineage_payload" in artifact_source

    assert "upsert_many" in _called_attributes(followups)
    followup_source = ast.unparse(followups)
    for edge_kind in (
        "run_to_followup",
        "prototype_to_followup",
        "interface_to_followup",
    ):
        assert edge_kind in followup_source


def test_registry_partial_resume_is_current_run_and_kind_scoped() -> None:
    node = _class(
        "calm/project/application/followups/registry_search.py",
        "RegistrySearchOrchestrator",
    )
    run_stage = _function(node, "run_stage")
    calls = [
        call
        for call in ast.walk(run_stage)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "load_existing_followups"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg for keyword in calls[0].keywords}
    assert {"run_uid_full", "kind", "targets"}.issubset(keywords)
    assert "_create_edges" not in {
        item.name for item in node.body if isinstance(item, ast.FunctionDef)
    }


def test_reference_and_thermodynamic_workspace_adapters_do_not_enter_uows() -> None:
    workspace = _class("calm/project/runtime/workspace.py", "Workspace")
    for name in ("run_reference_energy_stage", "run_thermodynamic_stage"):
        function = _function(workspace, name)
        assert not any(isinstance(node, ast.With) for node in ast.walk(function))
        source = ast.unparse(function)
        assert "getattr(self, '_uow_factory'" not in source
        assert "self._uow_factory" in source


def test_resume_and_lineage_failures_are_not_silently_suppressed() -> None:
    cases = (
        (
            "calm/project/application/followups/energy.py",
            "EnergyOrchestrator",
            "_existing_followups",
        ),
        (
            "calm/project/application/followups/relaxation.py",
            "RelaxationOrchestrator",
            "_existing_followups",
        ),
        (
            "calm/project/application/followups/reference_energy.py",
            "ReferenceEnergyOrchestrator",
            "_existing",
        ),
        (
            "calm/project/application/followups/thermodynamics.py",
            "ThermodynamicOrchestrator",
            "_existing",
        ),
    )
    for path, class_name, method_name in cases:
        function = _function(_class(path, class_name), method_name)
        assert not any(
            isinstance(node, ast.ExceptHandler) for node in ast.walk(function)
        )
