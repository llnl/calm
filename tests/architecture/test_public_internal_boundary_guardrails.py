"""Conservative public/internal package-boundary guardrails.

These tests protect high-value ownership rules without attempting to freeze every
legitimate dependency in the package.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ImportRecord:
    source: Path
    target: str
    lineno: int


def _repo_root() -> Path:
    path = Path(__file__).resolve()
    for parent in [path.parent, *path.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"Could not locate repository root from {path}")


def _module_name(path: Path, package_root: Path) -> str:
    rel = path.relative_to(package_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].removesuffix(".py")
    return "calm" if not parts else "calm." + ".".join(parts)


def _iter_library_files(root: Path) -> Iterable[Path]:
    package_root = root / "calm"
    for path in package_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(package_root)
        if rel.parts and rel.parts[0] == "tests":
            continue
        yield path


def _resolve_importfrom_target(path: Path, node: ast.ImportFrom, package_root: Path) -> str | None:
    module = node.module or ""
    if node.level == 0:
        return module or None

    source_module = _module_name(path, package_root)
    source_parts = source_module.split(".")
    if path.name != "__init__.py":
        source_parts = source_parts[:-1]

    up = max(node.level - 1, 0)
    if up:
        source_parts = source_parts[:-up]

    suffix = module.split(".") if module else []
    parts = [p for p in source_parts + suffix if p]
    return ".".join(parts) if parts else None


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, source: Path, package_root: Path) -> None:
        self.source = source
        self.package_root = package_root
        self.records: list[ImportRecord] = []

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self.records.append(ImportRecord(self.source, alias.name, int(node.lineno)))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        target = _resolve_importfrom_target(self.source, node, self.package_root)
        if target:
            self.records.append(ImportRecord(self.source, target, int(node.lineno)))


def _imports_for(path: Path, package_root: Path) -> list[ImportRecord]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    visitor = _ImportCollector(path, package_root)
    visitor.visit(tree)
    return visitor.records


def _format(records: Iterable[ImportRecord], root: Path) -> str:
    return "\n".join(
        f"- {rec.source.relative_to(root)}:{rec.lineno}: imports {rec.target}"
        for rec in sorted(records, key=lambda r: (str(r.source), r.lineno, r.target))
    )


def test_internal_kernels_do_not_import_beginner_public_facade() -> None:
    """Internal kernels should not depend on ``calm.public``.

    Allowed exceptions are the public facade itself and the top-level API
    resolver. Internal project runtime and presentation modules do not import
    the public facade.
    """

    root = _repo_root()
    package_root = root / "calm"
    allowed_prefixes = ("calm.public",)
    allowed_modules = {
        "calm",
        "calm.api",
    }

    offenders: list[ImportRecord] = []
    for path in _iter_library_files(root):
        source_module = _module_name(path, package_root)
        if source_module in allowed_modules or source_module.startswith(allowed_prefixes):
            continue
        for rec in _imports_for(path, package_root):
            if rec.target == "calm.public" or rec.target.startswith("calm.public."):
                offenders.append(rec)

    assert offenders == [], (
        "Internal modules must not import the basic public facade.\n"
        "Public facade orchestration may depend on internal kernels, but the "
        "reverse dependency creates circular-import and ownership drift.\n"
        + _format(offenders, root)
    )


def test_public_facade_does_not_import_project_infrastructure_layer() -> None:
    """The basic facade may open projects but must not import DB internals."""

    root = _repo_root()
    package_root = root / "calm"
    offenders: list[ImportRecord] = []
    for path in (root / "calm" / "public").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for rec in _imports_for(path, package_root):
            if rec.target == "calm.project.infrastructure" or rec.target.startswith(
                "calm.project.infrastructure."
            ):
                offenders.append(rec)
            if rec.target == "sqlalchemy" or rec.target.startswith("sqlalchemy."):
                offenders.append(rec)

    assert offenders == [], (
        "calm.public should not import database infrastructure or SQLAlchemy "
        "directly. Route durable operations through calm.project public ports.\n"
        + _format(offenders, root)
    )
