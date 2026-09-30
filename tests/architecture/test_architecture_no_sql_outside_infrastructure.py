"""Architecture guardrails for the staged legacy migration.

During the *legacy isolation* stage we still carry legacy modules alongside the
new layered architecture.

This test enforces:
  - SQL libraries are only imported in:
      * calm.project.infrastructure  (modern persistence)
      * calm.project.legacy          (temporary; to be removed later)

Once legacy is fully removed, this test should be tightened (or replaced) to
only allow SQL libs within calm.project.infrastructure.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not locate repository root from {here}")


def _iter_py_files(root: Path) -> Iterable[Path]:
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        yield py_file


def test_no_sql_libs_outside_infrastructure_or_legacy() -> None:
    repo = _repo_root()
    project_root = repo / "calm" / "project"
    assert project_root.exists(), f"Expected calm.project package dir: {project_root}"

    infra_dir = project_root / "infrastructure"
    assert infra_dir.exists(), f"Expected infrastructure dir: {infra_dir}"

    legacy_dir = project_root / "legacy"  # may be removed in later phases

    forbidden_roots = {"sqlite3", "sqlalchemy", "alembic"}

    offenders: list[str] = []

    for py_file in _iter_py_files(project_root):
        p = py_file.resolve()

        # Allowed zones: infrastructure + legacy (during isolation stage).
        if infra_dir in p.parents:
            continue
        if legacy_dir.exists() and legacy_dir in p.parents:
            continue

        src = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(py_file))
        except SyntaxError as e:
            offenders.append(f"{py_file}: SyntaxError: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name or ""
                    root = name.split(".", 1)[0]
                    if root in forbidden_roots:
                        offenders.append(
                            f"{py_file}: import {name} (SQL libs forbidden outside infrastructure/legacy)"
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                root = mod.split(".", 1)[0] if mod else ""
                if root in forbidden_roots:
                    offenders.append(
                        f"{py_file}: from {mod} import ... (SQL libs forbidden outside infrastructure/legacy)"
                    )

    assert not offenders, (
        "SQL/lib imports found outside calm.project.infrastructure or calm.project.legacy:\n"
        + "\n".join(f"- {x}" for x in offenders)
    )
