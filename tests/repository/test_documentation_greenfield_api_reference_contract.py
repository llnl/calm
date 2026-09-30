"""Content and coverage contracts for the greenfield public API reference."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
import re

from engineering.documentation import api_reference_manifest as manifest


ROOT = Path(__file__).resolve().parents[2]
OVERVIEW = ROOT / "docs" / "reference" / "public-api.md"
SITE_CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"
PUBLIC_CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
TABLE_CONTRACT = ROOT / "engineering" / "architecture" / "current-public-table-views.json"
STUB_MARKER = "Greenfield reconstruction:"

EXPECTED_PAGES = {
    Path("reference/api/project.md"),
    Path("reference/api/inputs-settings.md"),
    Path("reference/api/returned-objects.md"),
    Path("reference/api/exceptions-utilities.md"),
}


def _site_contract() -> dict[str, object]:
    return json.loads(SITE_CONTRACT.read_text(encoding="utf-8"))


def _public_contract() -> dict[str, object]:
    return json.loads(PUBLIC_CONTRACT.read_text(encoding="utf-8"))


def _pages() -> dict[Path, str]:
    return manifest.rendered_pages()


def test_public_api_overview_is_complete_and_routes_every_lookup_mode() -> None:
    text = OVERVIEW.read_text(encoding="utf-8")
    assert STUB_MARKER not in text
    for heading in _site_contract()["page_anatomy"]["reference"]:
        assert f"## {heading}" in text
    for target in (
        "api/project.md",
        "api/inputs-settings.md",
        "api/returned-objects.md",
        "api/exceptions-utilities.md",
        "../use/projects.md",
        "../understand/surface-models.md",
    ):
        assert target in text
    for phrase in (
        "top-level `calm` namespace",
        "project = calm.open_project",
        'project.search("cu-ni-100").candidates()',
        "Package submodules are implementation details",
        "Generated signatures are taken from the installed CALM source",
        "Implementation metadata is intentionally omitted",
    ):
        assert phrase in text


def test_api_reference_contract_records_exact_live_coverage() -> None:
    site = _site_contract()["api_reference"]
    public = _public_contract()
    tables = json.loads(TABLE_CONTRACT.read_text(encoding="utf-8"))

    assert site["implemented_phase"] == "G6"
    assert site["authored_overview"] == "docs/reference/public-api.md"
    assert set(site["generated_pages"]) == {path.as_posix() for path in EXPECTED_PAGES}
    assert site["coverage"] == {
        "top_level_exports": len(public["exports"]),
        "project_operations": len(public["project_methods"]),
        "returned_object_types": len(public["workflow_objects"]),
        "table_view_owners": len(tables["current_view_owners"]),
    }


def test_generated_reference_has_complete_public_surface_coverage() -> None:
    pages = _pages()
    assert set(pages) == EXPECTED_PAGES
    public = _public_contract()
    combined = "\n".join(pages.values())

    for row in public["exports"]:
        assert f"calm.{row['name']}" in combined
    for row in public["project_methods"]:
        assert f"Project.{row['name']}()" in pages[Path("reference/api/project.md")]
    for row in public["workflow_objects"]:
        assert f"`{row['name']}`" in pages[Path("reference/api/returned-objects.md")]


def test_settings_reference_renders_every_field_meaning() -> None:
    public = _public_contract()
    page = _pages()[Path("reference/api/inputs-settings.md")]
    for row in public["exports"]:
        if row["group"] != "settings":
            continue
        cls = manifest._load_symbol(row["implementation"])
        assert dataclasses.is_dataclass(cls)
        section = page.split(f"### `calm.{row['name']}`", 1)[1]
        section = section.split("\n### `calm.", 1)[0]
        assert "**Fields**" in section
        for field in dataclasses.fields(cls):
            assert f"| `{field.name}` |" in section


def test_api_families_link_back_to_workflow_and_recovery_guidance() -> None:
    pages = _pages()
    project = pages[Path("reference/api/project.md")]
    inputs = pages[Path("reference/api/inputs-settings.md")]
    returned = pages[Path("reference/api/returned-objects.md")]
    errors = pages[Path("reference/api/exceptions-utilities.md")]

    for target in (
        "../../use/projects.md",
        "../../use/materials.md",
        "../../use/surfaces.md",
        "../../use/searches.md",
        "../../use/build-refine.md",
        "../../use/relax-evaluate.md",
        "../../use/datasets-campaigns.md",
        "../../understand/energetics.md",
    ):
        assert target in project + inputs + returned

    assert "| Exception | Meaning | Recovery guidance | Direct bases |" in errors
    assert "../troubleshooting-geometry.md" in errors
    assert "../troubleshooting-calculations.md" in errors
    assert "../../learn/first-interface.md" in errors


def test_generated_reference_omits_implementation_language_and_fields() -> None:
    pages = _pages()
    combined = "\n".join(pages.values())
    lowered = combined.casefold()
    for phrase in (
        "calm.public.",
        "canonical payload",
        "database schema",
        "persistence adapter",
        "serializer",
        "identity-construction",
        "joined-record path",
        "current operational result limit",
        "canonical operational grid",
        "internal workspace state",
    ):
        assert phrase.casefold() not in lowered

    returned = pages[Path("reference/api/returned-objects.md")]
    for field in (
        "`payload`",
        "`authority`",
        "`identity_algorithm`",
        "`pair_identity`",
        "`identity_version`",
        "`pareto_policy`",
    ):
        assert field not in returned

    authoritative_tokens = re.findall(r"authoritative[A-Za-z0-9_]*", combined)
    assert authoritative_tokens
    assert set(authoritative_tokens) == {"authoritative_interface_area"}


def test_generated_pages_remain_compact_lookup_material() -> None:
    pages = _pages()
    limits = {
        "project.md": 4000,
        "inputs-settings.md": 3600,
        "returned-objects.md": 5000,
        "exceptions-utilities.md": 700,
    }
    for path, text in pages.items():
        assert len(text.split()) < limits[path.name], (path, len(text.split()))
