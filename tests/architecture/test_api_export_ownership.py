"""Ownership guardrails for CALM's single public namespace."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
INTERNAL_ROOTS = (
    "calm/public/__init__.py",
    "calm/project/__init__.py",
    "calm/interface/__init__.py",
    "calm/slab/__init__.py",
    "calm/bulk/__init__.py",
    "calm/calculators/__init__.py",
    "calm/viz/__init__.py",
)


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_calm_api_is_the_only_positive_export_registry() -> None:
    import calm.api as api

    expected = [row["name"] for row in _contract()["exports"]]
    assert list(api.PUBLIC_EXPORTS) == expected
    assert list(api._EXPORT_MAP) == expected
    assert list(api.__all__) == [name for name in expected if name != "__version__"]
    assert not hasattr(api, "COMPAT_TOP_LEVEL_EXPORTS")
    assert not hasattr(api, "_BEGINNER_EXPORT_MAP")


def test_implementation_package_roots_are_not_public_aggregators() -> None:
    errors: list[str] = []
    for relative in INTERNAL_ROOTS:
        path = ROOT / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in targets
                ):
                    errors.append(f"{relative}: defines __all__")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__":
                errors.append(f"{relative}: defines __getattr__")
            elif isinstance(node, ast.Import):
                errors.append(f"{relative}: imports runtime names")
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                errors.append(f"{relative}: imports from {node.module!r}")
    assert errors == []


def test_retired_top_level_paths_do_not_return_to_the_export_registry() -> None:
    import calm.api as api

    retired_names = {
        path.removeprefix("calm.")
        for path in _contract()["retired_top_level_exports"]
    }
    assert retired_names.isdisjoint(api.PUBLIC_EXPORTS)
    assert retired_names.isdisjoint(api._EXPORT_MAP)


def test_compatibility_only_slabspec_module_is_retired() -> None:
    assert not (ROOT / "calm" / "slab" / "slabspec.py").exists()
