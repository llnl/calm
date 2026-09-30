"""Architecture guardrails for public campaign workflow ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
SERVICE_SOURCE = ROOT / "calm" / "public" / "workflows" / "campaigns.py"
CONTRACT_SOURCE = ROOT / "calm" / "public" / "inputs" / "campaigns.py"


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


def test_project_campaign_methods_are_thin_service_delegates() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    for name in ("create_campaign", "run_campaign"):
        method = _method(project, name)
        attributes = _self_attributes(method)
        assert attributes == {"_campaign_workflows"}
        assert not any(isinstance(item, ast.For) for item in ast.walk(method))
        assert not any(
            isinstance(item, ast.ExceptHandler) for item in ast.walk(method)
        )


def test_project_has_no_campaign_stage_adapters() -> None:
    project = _class(PROJECT_SOURCE, "Project")
    method_names = {
        item.name for item in project.body if isinstance(item, ast.FunctionDef)
    }
    assert {
        "_run_build_stage",
        "_run_registry_stage",
        "_run_relaxation_stage",
        "_run_energy_stage",
    }.isdisjoint(method_names)


def test_campaign_service_composes_existing_internal_workflow_owners() -> None:
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectCampaignWorkflowService" in source
    assert "def create_campaign(" in source
    assert "def run_campaign(" in source
    assert "def execute_campaign(" in source
    assert "def reused_campaign_result(" in source
    assert "owner._searches.search_interfaces(" in source
    assert "owner._builds.build_interfaces(" in source
    assert "owner._refinements.refine_interfaces(" in source
    assert "owner._relaxations.relax_interfaces(" in source
    assert "owner._energies.evaluate_reference_energies(" in source
    assert "owner._energies.evaluate_energies(" in source
    assert "owner._datasets.create_dataset(" in source
    assert "owner._project.create_dataset(" not in source
    assert "campaign_case_result" in source
    assert "run_of_campaign_execution" in source


def test_campaign_contract_module_contains_no_workflow_executor() -> None:
    source = CONTRACT_SOURCE.read_text(encoding="utf-8")
    assert "def execute_campaign(" not in source
    assert "def reused_campaign_result(" not in source
    assert "ProjectCampaignWorkflowService" not in source


def test_campaign_service_is_internal_not_a_top_level_api() -> None:
    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    assert "ProjectCampaignWorkflowService" not in api_source
    assert "ProjectCampaignWorkflowService" not in init_source
