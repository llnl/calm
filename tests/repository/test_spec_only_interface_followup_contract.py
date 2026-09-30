from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "calm" / "project" / "runtime" / "workspace.py"


def test_atomistic_followups_use_reconstructing_interface_loader() -> None:
    tree = ast.parse(WORKSPACE.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword)
        and node.arg in {"target_atoms_loader", "interface_atoms_loader"}
    ]
    assert len(calls) == 3
    assert all(
        isinstance(keyword.value, ast.Attribute)
        and keyword.value.attr == "materialize_derived_interface_atoms"
        for keyword in calls
    )
