"""Guardrails for the first Internal Modernization implementation slice."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MODULES = (
    ROOT / "calm/interface/matching/audit.py",
    ROOT / "calm/interface/matching/_types.py",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_modernized_modules_do_not_use_legacy_typing_collection_aliases() -> None:
    legacy_names = {"Dict", "List", "Set", "Tuple"}
    for path in MODULES:
        tree = ast.parse(_read(path), filename=str(path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "typing":
                imported.update(alias.name for alias in node.names)
        assert legacy_names.isdisjoint(imported), (
            f"{path} still imports {legacy_names & imported}"
        )
