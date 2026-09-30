"""Guardrails against restoring public API tiers or parallel entry points."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
ACTIVE_PUBLIC_FILES = (
    ROOT / "README.md",
    ROOT / "public_api.md",
    ROOT / "docs" / "reference" / "public-api.md",
    ROOT / "docs" / "use" / "projects.md",
    ROOT / "docs" / "index.md",
)


def test_active_public_guidance_has_no_api_tiers() -> None:
    forbidden = ("beginner api", "basic api", "advanced api")
    errors: list[str] = []
    for path in ACTIVE_PUBLIC_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            if phrase in text:
                errors.append(f"{path.relative_to(ROOT)} contains {phrase!r}")
    assert errors == []


def test_internal_namespaces_are_not_supported_import_surfaces() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert set(contract["internal_namespaces"]) == {
        "calm.public",
        "calm.project",
        "calm.interface",
        "calm.slab",
        "calm.bulk",
        "calm.calculators",
        "calm.viz",
    }
    assert all(
        row["import_path"].count(".") == 1
        for row in contract["exports"]
        if row["name"] != "__version__"
    )


def test_workspace_and_slab_construction_types_are_not_public_exports() -> None:
    import calm.api as api

    assert {
        "Workspace",
        "open_workspace",
        "Slab",
        "SlabSpec",
        "Surface",
        "search_interfaces",
        "search_interface_grid",
    }.isdisjoint(api.PUBLIC_EXPORTS)
