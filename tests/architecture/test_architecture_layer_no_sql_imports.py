from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not locate repository root from {p}")


def _iter_py_files(root: Path) -> Iterable[Path]:
    yield from root.rglob("*.py")


def _iter_imported_modules(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_layers_do_not_import_sql_drivers_or_sqlalchemy() -> None:
    repo = _repo_root()
    project_root = repo / "calm" / "project"

    layers = [
        project_root / "domain",
        project_root / "ports",
        project_root / "application",
        project_root / "runtime",
        project_root / "presentation",
    ]

    missing = [p for p in layers if not p.exists()]
    assert not missing, f"Missing expected layer dirs: {missing}"

    forbidden_prefixes = {
        "sqlite3",
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.sql",
        # Alembic should not appear outside infrastructure/bootstrap.
        "alembic",
        # Layering rule: infra must not be imported by domain/ports/application/runtime/presentation.
        "calm.project.infrastructure",
    }

    offenders: list[str] = []

    for root in layers:
        for f in _iter_py_files(root):
            txt = f.read_text(encoding="utf-8")
            try:
                tree = ast.parse(txt, filename=str(f))
            except SyntaxError:
                continue

            for mod in _iter_imported_modules(tree):
                for prefix in forbidden_prefixes:
                    if mod == prefix or mod.startswith(prefix + "."):
                        offenders.append(f"{f.relative_to(repo)}: {mod}")

    assert not offenders, (
        "Found SQL driver / SQLAlchemy imports in non-infrastructure layers:\n"
        + "\n".join(f"- {o}" for o in sorted(set(offenders)))
    )
