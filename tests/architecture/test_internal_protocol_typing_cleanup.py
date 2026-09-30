"""Guardrails for internal project-port protocol typing cleanup."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REPOS = ROOT / "calm/project/ports/repos.py"
UOW = ROOT / "calm/project/ports/uow.py"

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def imported_typing_names(path: Path) -> set[str]:
    tree = ast.parse(read(path), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            names.update(alias.name for alias in node.names)
    return names

def test_project_port_protocols_do_not_import_optional() -> None:
    assert "Optional" not in imported_typing_names(REPOS)

def test_unit_of_work_exit_protocol_is_explicitly_typed() -> None:
    source = read(UOW)
    assert "TracebackType" in source
    assert "exc_type: type[BaseException] | None" in source
    assert "exc: BaseException | None" in source
    assert "tb: TracebackType | None" in source
