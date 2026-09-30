"""Guard the database-only ownership boundary for named interface searches."""

from __future__ import annotations

import ast
from pathlib import Path

from calm.project.infrastructure.db.tables import interface_searches


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "calm" / "public" / "project.py"
PROJECT_QUERIES = ROOT / "calm" / "public" / "queries" / "project.py"
REPOSITORY = ROOT / "calm" / "public" / "persistence" / "repository.py"


def _project_methods() -> set[str]:
    tree = ast.parse(PROJECT.read_text(encoding="utf-8"))
    project = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Project"
    )
    return {
        node.name
        for node in project.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_sidecar_search_lifecycle_helpers_remain_deleted() -> None:
    methods = _project_methods()
    assert {
        "_search_projection",
        "_upsert_search_state",
        "_prepare_interface_search",
        "_complete_interface_search",
        "_fail_interface_search",
    }.isdisjoint(methods)


def test_public_search_queries_do_not_read_sidecar_search_rows() -> None:
    source = PROJECT_QUERIES.read_text(encoding="utf-8")
    assert '_records.get("searches"' not in source
    assert "list_searches(" in source
    assert 'run_type="prototype_search"' not in source


def test_search_reporting_does_not_write_sidecar_workflow_rows() -> None:
    repository_source = REPOSITORY.read_text(encoding="utf-8")
    assert not (ROOT / "calm" / "public" / "records.py").exists()
    assert not (ROOT / "calm" / "public" / "sidecar_store.py").exists()
    assert "SidecarStore" not in repository_source
    assert '.table("candidates")' not in repository_source
    assert not (ROOT / "calm" / "public" / "sidecar.py").exists()


def test_named_search_relation_is_one_to_one() -> None:
    for column_name in ("name", "search_identity", "run_uid_full"):
        column = interface_searches.c[column_name]
        assert column.nullable is False
        assert column.unique is True
