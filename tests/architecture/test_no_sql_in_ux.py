from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


def _repo_root() -> Path:
    """Return the repository root (directory containing pyproject.toml)."""
    p = Path(__file__).resolve()
    for parent in [p.parent, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback: repo/tests/architecture/<file>
    return p.parents[2]


def _iter_py_files(path: Path) -> Iterable[Path]:
    if path.is_dir():
        yield from path.rglob("*.py")
    elif path.is_file() and path.suffix == ".py":
        yield path


def _iter_imported_modules(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_no_sql_in_public_runtime_and_presentation_modules() -> None:
    repo_root = _repo_root()
    src_root = repo_root / "calm"

    # Public entry point and internal runtime/presentation adapters to scan.
    targets: list[Path] = [
        src_root / "api.py",
        src_root / "project" / "runtime",
        src_root / "project" / "presentation",
    ]

    # NOTE:
    # - We forbid direct SQL drivers + SQLAlchemy.
    # - We also forbid importing CALM's DB infrastructure modules directly.
    #   Runtime and presentation code should depend on ports + services; persistence wiring belongs in a
    #   composition root (e.g., calm.project.bootstrap).
    forbidden_prefixes = {
        "sqlite3",
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.sql",
        # Legacy SQL helpers (pre-layering)
        "calm.project.sa_schema",
        "calm.project.sa_utils",
        "calm.project.store",
        "calm.project.schema",
        "calm.project.migrations",
        "calm.project.atoms_db",
        "calm.project.view",
        "calm.project.records",
        # New architecture: infrastructure must not be imported by runtime or presentation.
        "calm.project.infrastructure",
    }

    missing = [p for p in targets if not p.exists()]
    assert not missing, f"Missing expected public/runtime/presentation paths: {missing}"

    offenders: list[str] = []

    for tgt in targets:
        for f in _iter_py_files(tgt):
            txt = f.read_text(encoding="utf-8")
            try:
                tree = ast.parse(txt, filename=str(f))
            except SyntaxError:
                # If a file doesn't parse, the normal unit-test suite will catch it.
                continue

            for mod in _iter_imported_modules(tree):
                for prefix in forbidden_prefixes:
                    if mod == prefix or mod.startswith(prefix + "."):
                        offenders.append(f"{f.relative_to(repo_root)}: {mod}")

    assert not offenders, (
        "Public, runtime, and presentation modules must not import SQL drivers or infrastructure modules:\n"
        + "\n".join(f"- {o}" for o in sorted(set(offenders)))
    )
