from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "calm" / "project" / "runtime" / "workspace.py"


def test_artifact_backed_interface_atoms_use_rehydration_boundary() -> None:
    tree = ast.parse(WORKSPACE.read_text(encoding="utf-8"))

    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "get_derived_interface_atoms"
    )

    returns = [node.value for node in ast.walk(method) if isinstance(node, ast.Return)]
    assert any(
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "_rehydrate_persisted_atoms"
        and len(value.args) == 1
        and isinstance(value.args[0], ast.Name)
        and value.args[0].id == "data"
        for value in returns
    )
