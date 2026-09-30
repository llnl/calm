"""Architecture guardrails for public dataset workflow ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
SERVICE_SOURCE = ROOT / "calm" / "public" / "workflows" / "datasets.py"
CAMPAIGN_SOURCE = ROOT / "calm" / "public" / "workflows" / "campaigns.py"


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


def test_project_dataset_mutations_are_thin_service_delegates() -> None:
    for name in ("create_dataset", "add_dataset_items"):
        method = _project_method(name)
        assert _self_attributes(method) == {"_dataset_workflows"}
        assert not any(isinstance(item, ast.For) for item in ast.walk(method))
        assert not any(
            isinstance(item, ast.ExceptHandler) for item in ast.walk(method)
        )


def test_project_no_longer_owns_dataset_item_normalization() -> None:
    method_names = {
        node.name
        for node in _project_class().body
        if isinstance(node, ast.FunctionDef)
    }
    assert "_normalize_dataset_items" not in method_names


def test_dataset_service_owns_public_composition_only() -> None:
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    assert "class ProjectDatasetWorkflowService" in source
    assert "def create_dataset(" in source
    assert "def add_dataset_items(" in source
    assert "normalize_authoritative_dataset_source(" in source
    assert "self._workspace.create_or_get_dataset(" in source
    assert "self._workspace.add_dataset_items(" in source
    assert "ProjectDataset.from_item(" in source
    assert "uow." not in source
    assert "persisted_entity_uid_v2" not in source
    assert "dataset_item_identity_payload" not in source
    assert "add_provenance_edge" not in source


def test_campaign_dataset_stage_calls_dataset_service_directly() -> None:
    source = CAMPAIGN_SOURCE.read_text(encoding="utf-8")
    assert "owner._datasets.create_dataset(" in source
    assert "owner._project.create_dataset(" not in source


def test_dataset_service_is_internal_not_a_top_level_api() -> None:
    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    assert "ProjectDatasetWorkflowService" not in api_source
    assert "ProjectDatasetWorkflowService" not in init_source
