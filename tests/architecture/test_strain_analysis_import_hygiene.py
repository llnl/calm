"""Guardrails for strain analysis import hygiene."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TARGET = ROOT / "calm/interface/refinement/analysis.py"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def typing_imports(path: Path) -> set[str]:
    tree = ast.parse(read(path), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            names.update(alias.name for alias in node.names)
    return names

def test_strain_analysis_no_longer_imports_unused_legacy_typing_aliases() -> None:
    target = read(TARGET)
    imports = typing_imports(TARGET)

    assert "Optional" not in imports
    assert "Tuple" not in imports
    assert "from typing import" not in target
    assert "StrainDecomposition" in target
    assert "compute_strain_decomposition" in target
