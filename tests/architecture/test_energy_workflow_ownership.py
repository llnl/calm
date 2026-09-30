"""Architecture guardrails for public energy workflow ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
SERVICE_SOURCE = ROOT / "calm" / "public" / "workflows" / "energy.py"


def _project_class() -> ast.ClassDef:
    tree = ast.parse(PROJECT_SOURCE.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Project"
    )


def _project_method(name: str) -> ast.FunctionDef:
    return next(
        node
        for node in _project_class().body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _self_attributes(node: ast.AST) -> set[str]:
    return {
        item.attr
        for item in ast.walk(node)
        if isinstance(item, ast.Attribute)
        and isinstance(item.value, ast.Name)
        and item.value.id == "self"
    }


def test_project_energy_methods_are_thin_service_delegates() -> None:
    for name in ("evaluate_reference_energies", "evaluate_energies"):
        method = _project_method(name)
        attributes = _self_attributes(method)
        assert "_energy_workflows" in attributes
        assert attributes.isdisjoint(
            {
                "_workspace",
                "_repo",
                "_run_energy_stage",
                "relaxed_interfaces",
                "interface",
                "run",
            }
        )


def test_project_no_longer_owns_energy_target_normalization() -> None:
    method_names = {
        node.name
        for node in _project_class().body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_energy_interface_record" not in method_names
    assert "_energy_target_ids" not in method_names


def test_energy_service_owns_public_workflow_composition() -> None:
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectEnergyWorkflowService" in source
    assert "def evaluate_reference_energies(" in source
    assert "def evaluate_energies(" in source
    assert "def run_energy_stage(" in source
    assert "run_reference_energy_stage(" in source
    assert "run_thermodynamic_stage(" in source
    assert "ReferenceEnergyWorkflowResult(" in source
    assert "EnergyWorkflowResult(" in source


def test_energy_service_is_internal_not_a_top_level_api() -> None:
    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    assert "ProjectEnergyWorkflowService" not in api_source
    assert "ProjectEnergyWorkflowService" not in init_source
