"""Repository guardrails for coupled-search orchestration ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "calm" / "interface" / "matching" / "_orchestrator.py"


def _top_level_definition(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"missing top-level definition: {name}")


def test_coupled_search_has_preparation_state_traversal_and_finalization() -> None:
    tree = ast.parse(ORCHESTRATOR.read_text(encoding="utf-8"))

    for name in (
        "_CoupledMatchSearchPlan",
        "_CoupledMatchSearchState",
        "_prepare_coupled_match_search",
        "_traverse_scheduled_index_pair",
        "_traverse_orbit_pair",
        "_finalize_coupled_match_search",
    ):
        _top_level_definition(tree, name)

    entrypoint = _top_level_definition(tree, "enumerate_coupled_match_classes_core")
    assert isinstance(entrypoint, ast.FunctionDef)
    called_names = {
        node.func.id
        for node in ast.walk(entrypoint)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names == {
        "_prepare_coupled_match_search",
        "_traverse_scheduled_index_pair",
        "_finalize_coupled_match_search",
    }
    assert sum(isinstance(node, ast.For) for node in ast.walk(entrypoint)) == 1
    assert entrypoint.end_lineno is not None
    assert entrypoint.end_lineno - entrypoint.lineno + 1 <= 60


def test_search_reuse_is_owned_by_one_mutable_state_object() -> None:
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "@dataclass(slots=True)\nclass _CoupledMatchSearchState" in source
    assert "primitive_cache: dict[" in source
    assert "identity_cache: dict[" in source
    assert "geometry_cache: dict[" in source
    assert "correspondence_metric_cache: dict[" in source
    assert "classes_by_key: dict[" in source
    assert "representative_ranks: dict[" in source
    assert "@lru_cache" not in source
