from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT_SOURCE = ROOT / "calm" / "public" / "project.py"
REPOSITORY_SOURCE = ROOT / "calm" / "public" / "persistence" / "repository.py"


def _project_methods() -> set[str]:
    tree = ast.parse(PROJECT_SOURCE.read_text(encoding="utf-8"))
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


def test_project_has_an_explicit_public_boundary() -> None:
    methods = _project_methods()
    assert "__getattr__" not in methods
    assert {
        "runs",
        "run",
        "followups",
        "followup",
        "run_artifacts",
        "edges",
        "lineage",
        "interface",
        "dataset",
        "campaign",
        "campaign_run",
    } <= methods
    assert {
        "create_derived_interface",
        "get_derived_interface",
        "check_prototype_buildability",
        "check_prototypes_buildability",
    }.isdisjoint(methods)


def test_interface_queries_do_not_fabricate_persisted_interface_uids() -> None:
    repository = REPOSITORY_SOURCE.read_text(encoding="utf-8")
    assert not (ROOT / "calm" / "public" / "records.py").exists()
    assert 'f"iface:{interface_id}"' not in repository
    assert 'f"iface:{local_uid}"' not in repository
