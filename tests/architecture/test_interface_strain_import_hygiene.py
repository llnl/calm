"""Guardrails for interface strain import hygiene."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGET = ROOT / "calm/interface/refinement/strain.py"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def typing_imports(path: Path) -> set[str]:
    tree = ast.parse(read(path), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            names.update(alias.name for alias in node.names)
    return names

def test_interface_strain_has_no_unused_legacy_typing_imports() -> None:
    imports = typing_imports(TARGET)
    target = read(TARGET)

    assert {"Any", "Dict", "Optional"}.isdisjoint(imports)
    assert "from typing import" not in target
    assert "Optional[" not in target
    assert "Dict[" not in target
