"""Architecture guardrails for public collection implementation ownership."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "calm" / "public"
COLLECTIONS = PUBLIC / "collections"


IMPLEMENTATION_MODULES = {
    "base.py",
    "candidates.py",
    "structures.py",
    "interfaces.py",
    "datasets.py",
    "persistence.py",
}


PUBLIC_EXPORTS = {
    "CandidateCollection",
    "DatasetCollection",
    "EnergyResultCollection",
    "InterfaceCollection",
    "MaterialCollection",
    "SurfaceCollection",
}


def _class_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def test_public_collections_module_is_reexport_shim() -> None:
    # The former single-file shim is absent; concrete owners live in the
    # private calm.public.collections package.
    assert not (PUBLIC / "collections.py").exists()
    assert (COLLECTIONS / "__init__.py").exists()


def test_collection_implementations_are_split_by_ownership() -> None:
    missing = sorted(name for name in IMPLEMENTATION_MODULES if not (COLLECTIONS / name).exists())
    assert missing == []

    assert "CandidateCollection" in _class_names(COLLECTIONS / "candidates.py")
    assert "InterfaceCollection" in _class_names(COLLECTIONS / "interfaces.py")
    assert "DatasetCollection" in _class_names(COLLECTIONS / "datasets.py")
    assert "EnergyResultCollection" in _class_names(
        COLLECTIONS / "persistence.py"
    )
    assert {"MaterialCollection", "SurfaceCollection"}.issubset(_class_names(COLLECTIONS / "structures.py"))
    assert "_BaseCollection" in _class_names(COLLECTIONS / "base.py")


def test_collection_public_import_path_is_preserved() -> None:
    # Import concrete collection implementations directly.
    from calm.public.collections.candidates import CandidateCollection
    from calm.public.collections.datasets import DatasetCollection
    from calm.public.collections.persistence import EnergyResultCollection
    from calm.public.collections.interfaces import InterfaceCollection
    from calm.public.collections.structures import MaterialCollection, SurfaceCollection

    assert CandidateCollection.__module__ == "calm.public.collections.candidates"
    assert DatasetCollection.__module__ == "calm.public.collections.datasets"
    assert EnergyResultCollection.__module__ == "calm.public.collections.persistence"
    assert InterfaceCollection.__module__ == "calm.public.collections.interfaces"
    assert MaterialCollection.__module__ == "calm.public.collections.structures"
    assert SurfaceCollection.__module__ == "calm.public.collections.structures"
