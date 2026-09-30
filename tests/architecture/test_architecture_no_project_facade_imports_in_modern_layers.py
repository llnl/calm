from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

import pytest


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not locate repository root from {p}")


def _iter_py_files(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.py")


def _iter_imports(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


@pytest.mark.arch
def test_modern_layers_do_not_import_project_facade_modules() -> None:
    repo = _repo_root()
    project_root = repo / "calm" / "project"
    assert project_root.exists(), f"Expected calm.project package dir: {project_root}"

    # Any Python file directly under calm/project/*.py (except __init__.py and
    # the composition root) is treated as a legacy compatibility facade.
    facade_modules = {
        p.stem
        for p in project_root.glob("*.py")
        if p.is_file()
        and p.stem not in {
            "__init__",
            # Composition root is intentionally allowed to import infrastructure.
            "bootstrap",
        }
    }

    # Modern layer targets.
    modern_dirs = [
        project_root / "domain",
        project_root / "application",
        project_root / "ports",
        project_root / "infrastructure",
        project_root / "runtime",
        project_root / "presentation",
    ]

    missing = [p for p in modern_dirs if not p.exists()]
    assert not missing, f"Missing expected modern layer dirs: {missing}"

    offenders: list[str] = []

    for root in modern_dirs:
        for f in _iter_py_files(root):
            txt = f.read_text(encoding="utf-8")
            try:
                tree = ast.parse(txt, filename=str(f))
            except SyntaxError:
                continue

            for mod in _iter_imports(tree):
                if not mod.startswith("calm.project."):
                    continue
                parts = mod.split(".")
                if len(parts) < 3:
                    continue
                candidate = parts[2]
                if candidate in facade_modules:
                    offenders.append(f"{f.relative_to(repo)}: {mod}")

    assert not offenders, (
        "Modern layered code must not import legacy facade modules:\n"
        + "\n".join(f"- {o}" for o in sorted(set(offenders)))
    )
