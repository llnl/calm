"""Architecture guardrails for lineage, health, and structure read owners."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
LINEAGE_SOURCE = ROOT / "calm" / "public" / "queries" / "lineage.py"
HEALTH_SOURCE = ROOT / "calm" / "public" / "queries" / "health.py"
STRUCTURE_SOURCE = ROOT / "calm" / "public" / "queries" / "structures.py"
PERSISTED_SEARCH_SOURCE = ROOT / "calm" / "public" / "records" / "search.py"


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


def test_project_lineage_is_a_thin_read_service_delegate() -> None:
    method = _project_method("lineage")
    assert _self_attributes(method) == {"_lineage_queries"}
    assert not any(isinstance(item, ast.For) for item in ast.walk(method))
    assert not any(isinstance(item, ast.While) for item in ast.walk(method))


def test_project_has_no_private_read_model_helpers() -> None:
    method_names = {
        node.name
        for node in _project_class().body
        if isinstance(node, ast.FunctionDef)
    }
    assert {
        "_lineage_identifier",
        "_lineage_kind_hints",
        "_lineage_node",
        "_get_interface_atoms",
        "_check_prototype_buildability",
        "_check_prototypes_buildability",
    }.isdisjoint(method_names)
    assert {name for name in method_names if name.startswith("_")} == {
        "__init__"
    }


def test_read_services_are_query_only_and_internal() -> None:
    lineage = LINEAGE_SOURCE.read_text(encoding="utf-8")
    health = HEALTH_SOURCE.read_text(encoding="utf-8")
    structures = STRUCTURE_SOURCE.read_text(encoding="utf-8")
    combined = "\n".join((lineage, health, structures))

    assert "class ProjectLineageQueryService" in lineage
    assert "class ProjectHealthService" in health
    assert "class ProjectStructureQueryService" in structures
    for forbidden in (
        "add_provenance_edge(",
        "create_derived_interface(",
        "persist_derived_interface(",
        "create_or_get_dataset(",
        "uow.",
    ):
        assert forbidden not in combined

    api_source = (ROOT / "calm" / "api.py").read_text(encoding="utf-8")
    init_source = (ROOT / "calm" / "__init__.py").read_text(encoding="utf-8")
    for service_name in (
        "ProjectLineageQueryService",
        "ProjectHealthService",
        "ProjectStructureQueryService",
    ):
        assert service_name not in api_source
        assert service_name not in init_source


def test_search_readiness_delegates_to_health_owner() -> None:
    source = PERSISTED_SEARCH_SOURCE.read_text(encoding="utf-8")
    assert "self.project._health.search_status(self.name)" in source
    assert "self.project._health.search_buildability(self.name)" in source
    assert "self.project._health.search_summary(self.name)" in source
    assert "self.candidates().validate_buildable()" not in source


def test_structure_consumers_use_the_structure_query_owner() -> None:
    for relative in (
        "calm/public/collections/interfaces.py",
        "calm/public/records/dataset_learning.py",
        "calm/public/records/datasets.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "._structure_queries.get_interface_atoms(" in source
        assert "._get_interface_atoms(" not in source
