from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() or (parent / "public_api.md").exists():
            return parent
    raise RuntimeError(f"Could not locate repo root from {here}")


def _iter_py_files(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*.py") if p.is_file()])


def _module_path_for_file(repo_root: Path, py_file: Path) -> list[str]:
    calm_root = repo_root / "calm"
    rel = py_file.resolve().relative_to(calm_root.resolve())
    parts = list(rel.parts)

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(parts[-1]).stem

    return ["calm", *parts]


def _package_path_for_file(repo_root: Path, py_file: Path) -> list[str]:
    mod = _module_path_for_file(repo_root, py_file)
    if py_file.name == "__init__.py":
        return mod
    return mod[:-1]


def _resolve_importfrom_targets(repo_root: Path, py_file: Path, node: ast.ImportFrom) -> list[str]:
    """Resolve ImportFrom to absolute module strings."""
    if node.level == 0:
        if node.module:
            return [node.module]
        return []

    pkg = _package_path_for_file(repo_root, py_file)
    up = node.level - 1
    if up > len(pkg):
        return []

    base = pkg[: len(pkg) - up]

    if node.module:
        base = [*base, *node.module.split(".")]
        return [".".join(base)]

    # from .. import X  (module is None); treat each imported name as a module under base
    out: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            continue
        out.append(".".join([*base, alias.name]))
    return out


def test_infrastructure_imports_only_in_bootstrap_or_infrastructure_package() -> None:
    repo = _repo_root()
    project_root = repo / "calm" / "project"
    assert project_root.exists(), f"Expected project package dir: {project_root}"

    allowed_files = {
        (project_root / "bootstrap.py").resolve(),
    }

    offenders: list[str] = []

    for py_file in _iter_py_files(project_root):
        p = py_file.resolve()

        # Exclusions: legacy is quarantined, infrastructure is allowed.
        if (project_root / "legacy") in p.parents:
            continue
        if (project_root / "infrastructure") in p.parents:
            continue

        # Allow bootstrap composition root.
        if p in allowed_files:
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
                    if name.startswith("calm.project.infrastructure"):
                        offenders.append(f"{py_file}: import {name} (infra imports must be in bootstrap or infrastructure)")
            elif isinstance(node, ast.ImportFrom):
                targets = _resolve_importfrom_targets(repo, py_file, node)
                for mod in targets:
                    if mod.startswith("calm.project.infrastructure"):
                        offenders.append(
                            f"{py_file}: from {mod} import ... (infra imports must be in bootstrap or infrastructure)"
                        )

    assert not offenders, (
        "Composition-root rule violated: calm.project.infrastructure imported outside bootstrap/infrastructure.\n"
        + "\n".join(f"- {x}" for x in offenders)
    )
