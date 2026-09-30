"""Content contracts for the greenfield Use CALM workflow manual."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "use"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"
STUB_MARKER = "Greenfield reconstruction:"

PAGES = {
    "projects": DOCS / "projects.md",
    "materials": DOCS / "materials.md",
    "surfaces": DOCS / "surfaces.md",
    "searches": DOCS / "searches.md",
    "build-refine": DOCS / "build-refine.md",
    "relax-evaluate": DOCS / "relax-evaluate.md",
    "datasets-campaigns": DOCS / "datasets-campaigns.md",
}


def _headings(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_use_pages_follow_one_predictable_anatomy() -> None:
    anatomy = _contract()["page_anatomy"]["use"]
    assert anatomy == [
        "Outcome",
        "When to use it",
        "Prerequisites",
        "Scientific decisions",
        "Minimal procedure",
        "Inspect the result",
        "Interpretation",
        "Common variations",
        "Common problems",
        "Exact API",
    ]
    for page in PAGES.values():
        text = page.read_text(encoding="utf-8")
        assert STUB_MARKER not in text
        assert _headings(text) == anatomy
        assert text.count("```python") >= 2
        assert len(text.split()) >= 700
        assert "../reference/api/" in text


def test_each_workflow_has_one_primary_task_owner() -> None:
    text = {name: path.read_text(encoding="utf-8") for name, path in PAGES.items()}
    required = {
        "projects": (
            "older or incompatible project",
            "Preserve the original directory unchanged",
            "write_reproducibility_manifest",
            "project.lineage",
        ),
        "materials": (
            "Material.from_ase",
            "optimize_material",
            "project.export_materials",
            "A calculator being loadable does not make it valid",
        ),
        "surfaces": (
            "side A contributes its top face",
            "side B contributes its bottom face",
            "termination_bottom",
            "CALM does not infer the physically correct termination",
        ),
        "searches": (
            "max_principal_strain",
            "buildability_summary",
            "Pareto optimality",
            "The search score combines configured geometric objectives",
        ),
        "build-refine": (
            "strain_partition=\"both\"",
            "potential_energy_density_eV_per_A2",
            "Registry refinement",
            "best among evaluated choices",
        ),
        "relax-evaluate": (
            "fixed-cell relaxation",
            "work_of_adhesion_relaxed_surfaces",
            "raw total energy",
            "unavailable result",
        ),
        "datasets-campaigns": (
            "group_by",
            "validate_ml",
            "CampaignCase.grid",
            "Datasets and campaigns are advanced study-management tools",
        ),
    }
    for name, phrases in required.items():
        for phrase in phrases:
            assert phrase in text[name], (name, phrase)


def test_contextual_troubleshooting_is_integrated_into_every_workflow() -> None:
    for page in PAGES.values():
        text = page.read_text(encoding="utf-8")
        common = text.split("## Common problems", 1)[1].split("## Exact API", 1)[0]
        assert common.count("### ") >= 3
        assert "troubleshooting" not in page.name


def test_use_pages_avoid_implementation_and_storage_language() -> None:
    forbidden = (
        "canonical payload",
        "serializer",
        "database schema",
        "persistence adapter",
        "migration strategy",
        "implementation owner",
        "authoritative persisted",
    )
    for page in PAGES.values():
        text = page.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            assert phrase not in text, (page.name, phrase)
