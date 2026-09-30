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


def test_layer_import_boundaries() -> None:
    """Enforce CALM's layered architecture import boundaries.

    Layers:
      - domain
      - ports
      - application
      - infrastructure
      - runtime
      - presentation

    Rules (high level):
      - domain depends on nothing in project (except itself)
      - ports may depend on domain
      - application may depend on domain + ports
      - infrastructure may depend on domain + ports + application
      - presentation may depend on domain + ports
      - runtime may compose application and presentation, but not infrastructure
    """
    repo = _repo_root()
    project_root = repo / "calm" / "project"

    layers = {
        "domain": project_root / "domain",
        "ports": project_root / "ports",
        "application": project_root / "application",
        "infrastructure": project_root / "infrastructure",
        "runtime": project_root / "runtime",
        "presentation": project_root / "presentation",
    }

    missing = [p for p in layers.values() if not p.exists()]
    assert not missing, f"Missing expected layer paths: {missing}"

    allowed = {
        "domain": {"domain"},
        "ports": {"ports", "domain"},
        "application": {"application", "domain", "ports"},
        "infrastructure": {"infrastructure", "domain", "ports", "application"},
        "runtime": {
            "runtime",
            "presentation",
            "application",
            "domain",
            "ports",
        },
        "presentation": {"presentation", "domain", "ports"},
    }

    offenders: list[str] = []

    for layer_name, root in layers.items():
        for f in _iter_py_files(root):
            txt = f.read_text(encoding="utf-8")
            try:
                tree = ast.parse(txt, filename=str(f))
            except SyntaxError:
                continue

            for mod in _iter_imported_modules(tree):
                if not mod.startswith("calm.project."):
                    continue

                parts = mod.split(".")
                # calm.project.<segment>...
                if len(parts) < 3:
                    continue
                seg = parts[2]
                if seg in layers and seg not in allowed[layer_name]:
                    offenders.append(
                        f"{f.relative_to(repo)}: {layer_name} imports {seg} via {mod}"
                    )

    assert not offenders, (
        "Layer import boundary violations detected:\n"
        + "\n".join(f"- {o}" for o in sorted(set(offenders)))
    )
