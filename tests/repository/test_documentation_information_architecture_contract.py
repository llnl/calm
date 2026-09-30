"""Contracts for CALM's greenfield documentation architecture."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"
STUB_MARKER = "Greenfield reconstruction:"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _entries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for row in rows:
        children = row.get("children")
        if children:
            entries.extend(_entries(children))
        else:
            entries.append(row)
    return entries


def _nav_paths() -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+\.md)", MKDOCS.read_text(encoding="utf-8"))


def test_greenfield_contract_defines_the_site_on_its_own_terms() -> None:
    contract = _contract()
    assert contract["schema_version"] == "calm.documentation_site_contract.v1"
    assert contract["status"] == "editorial_integration_complete"
    assert contract["counts"] == {
        "authored_pages": 24,
        "generated_api_pages": 4,
        "top_level_destinations": 6,
    }
    assert contract["objective"] == (
        "A single guided scientific manual with a compact exact public API reference."
    )
    assert contract["publication_gate"] == {
        "skeleton_is_not_publishable": False,
        "content_complete": True,
        "publication_ready": False,
        "remaining_before_publication": [
            "execute all three tutorials in their declared environments after the final corrective patches",
            "run python -m mkdocs build --strict",
            "run the final documentation, link, API, package, and figure verification suite",
            "inspect the rendered home, installation, tutorial, scientific, and API pages",
        ],
    }


def test_navigation_has_six_reader_oriented_destinations() -> None:
    text = MKDOCS.read_text(encoding="utf-8")
    expected = (
        "  - Home: index.md",
        "  - Install: install.md",
        "  - Learn:",
        "  - Use CALM:",
        "  - Understand:",
        "  - Reference:",
    )
    positions = [text.index(value) for value in expected]
    assert positions == sorted(positions)
    for legacy in (
        "Getting started:",
        "Tutorials:",
        "User guide:",
        "Scientific background:",
        "Recipes:",
        "Troubleshooting:",
    ):
        assert legacy not in text
    assert "navigation.tabs" in text
    assert "navigation.tabs.sticky" in text


def test_contract_and_mkdocs_own_the_same_pages() -> None:
    contract = _contract()
    entries = _entries(contract["navigation"])
    authored = {row["path"] for row in entries if row["kind"] == "authored"}
    generated = {row["path"] for row in entries if row["kind"] == "generated"}
    committed = {path.relative_to(DOCS).as_posix() for path in DOCS.rglob("*.md")}
    nav_paths = set(_nav_paths())

    assert committed == authored
    assert nav_paths == authored | generated
    assert len(authored) == 24
    assert generated == {
        "reference/api/project.md",
        "reference/api/inputs-settings.md",
        "reference/api/returned-objects.md",
        "reference/api/exceptions-utilities.md",
    }


def test_completed_greenfield_sections_are_implemented_and_remaining_pages_are_stubs() -> None:
    entries = _entries(_contract()["navigation"])
    errors: list[str] = []
    for row in entries:
        if row["kind"] != "authored":
            continue
        relative = str(row["path"])
        path = DOCS / relative
        text = path.read_text(encoding="utf-8")
        h1 = [line for line in text.splitlines() if line.startswith("# ")]
        if len(h1) != 1:
            errors.append(f"{relative}: expected exactly one H1")
        if relative == "index.md":
            implemented_section = "home"
        elif relative == "install.md":
            implemented_section = "install"
        elif relative.startswith("learn/"):
            implemented_section = "learn"
        elif relative.startswith("use/"):
            implemented_section = "use"
        elif relative.startswith("understand/"):
            implemented_section = "understand"
        elif relative.startswith("reference/"):
            implemented_section = "reference"
        else:  # pragma: no cover - closed navigation contract
            errors.append(f"{relative}: no page-anatomy owner")
            continue

        if row.get("implemented") is not True:
            errors.append(f"{relative}: missing implemented=true")
        if STUB_MARKER in text:
            errors.append(f"{relative}: retains reconstruction marker")
        for heading in _contract()["page_anatomy"][implemented_section]:
            if f"## {heading}" not in text:
                errors.append(f"{relative}: missing {heading!r} section")
        if implemented_section in {"home", "install", "learn", "use"} and "```" not in text:
            errors.append(f"{relative}: missing executable examples")
        if implemented_section in {"home", "learn", "understand"} and "<figure" not in text:
            errors.append(f"{relative}: missing owned figure")
    assert errors == [], "\n".join(errors)


def test_legacy_documentation_trees_and_public_figures_are_deleted() -> None:
    for directory in (
        "getting-started",
        "how-to",
        "scientific-background",
        "troubleshooting",
        "tutorials",
        "user-guide",
        "mathematics",
        "concepts",
    ):
        assert not any((DOCS / directory).rglob("*.md"))
    figure_root = DOCS / "assets" / "figures"
    assert {
        path.relative_to(figure_root).as_posix()
        for path in figure_root.rglob("*.svg")
    } == {
        "site/calm-workflow-map.svg",
        "tutorials/first-interface-workflow.svg",
        "tutorials/candidate-selection.svg",
        "tutorials/refine-relax-evaluate.svg",
        "understand/surface-construction-workflow.svg",
        "understand/cell-map-types.svg",
        "understand/coupled-common-cell.svg",
        "understand/coherent-misfit-principal-strain.svg",
        "understand/pareto-strain-size.svg",
        "understand/strain-partition-path.svg",
        "understand/registry-translation-torus.svg",
        "understand/interface-energy-reference-cycles.svg",
    }

    replacement = _contract()["legacy_replacement"]
    assert len(replacement["replaced_authored_pages"]) == 32
    assert len(replacement["removed_public_figures"]) == 9
    assert replacement["redirect_policy"].startswith("No compatibility redirects")


def test_tutorial_platform_is_implemented_before_content_work() -> None:
    tutorial = _contract()["tutorial_product"]
    delivery = tutorial["data_delivery"]
    assert delivery["implementation_phase"] == "G2"
    assert delivery["implemented"] is True
    assert delivery["package_change_required"] is False
    assert delivery["public_boundary"] == "calm.tutorial_structure"
    assert delivery["resource_names"] == ["lif", "li2o", "cu", "ni"]
    assert "repository-relative input paths" in delivery["forbidden"]
    assert tutorial["canonical_sources"] == {
        "first-interface": "examples/tutorials/first_interface.py",
        "compare-candidates": "examples/tutorials/compare_candidates.py",
        "refine-relax-evaluate": "examples/tutorials/refine_relax_evaluate.py",
    }
    assert tutorial["expected_output_fixtures"] == (
        "examples/tutorials/expected/*.json"
    )
    assert "ASE provider with EMT" in tutorial["calculator_tutorial"]["decision"]
    assert "not evidence" in tutorial["calculator_tutorial"]["interpretation_boundary"]
    assert "generated from tested canonical tutorial sources" in tutorial["notebooks"]


def test_g1_scope_excludes_substantive_content_and_package_changes() -> None:
    scope = _contract()["g1_scope"]
    assert "delete legacy authored pages and public figures" in scope["included"]
    assert "tutorial data or package API changes" in scope["excluded"]
    assert "substantive tutorial prose" in scope["excluded"]
    assert "new public figures" in scope["excluded"]



def test_g2_scope_owns_tutorial_infrastructure_without_writing_tutorials() -> None:
    scope = _contract()["g2_scope"]
    assert "add one top-level tutorial_structure data boundary" in scope["included"]
    assert "create three independent canonical tutorial programs" in scope["included"]
    assert "substantive tutorial prose" in scope["excluded"]
    assert "tutorial figures" in scope["excluded"]
    assert "changes to CALM scientific algorithms" in scope["excluded"]



def test_g3_scope_owns_learn_prose_and_tutorial_figures_only() -> None:
    scope = _contract()["g3_scope"]
    assert "write the three Learn tutorials from canonical executable sources" in scope["included"]
    assert "create three tutorial-owned accessible SVG figures" in scope["included"]
    assert "workflow-manual prose under Use CALM" in scope["excluded"]
    assert "full scientific derivations under Understand" in scope["excluded"]
    assert "changes to CALM scientific algorithms" in scope["excluded"]



def test_g4_scope_owns_the_integrated_workflow_manual() -> None:
    scope = _contract()["g4_scope"]
    assert "write the seven task-oriented Use CALM chapters" in scope["included"]
    assert "integrate contextual troubleshooting into each workflow chapter" in scope["included"]
    assert "define repository-owned tutorial work directories under examples/work" in scope["included"]
    assert "full scientific derivations under Understand" in scope["excluded"]
    assert "new public figures" in scope["excluded"]
    assert "changes to CALM scientific algorithms" in scope["excluded"]



def test_g5_scope_owns_the_scientific_manual_and_concept_figures() -> None:
    scope = _contract()["g5_scope"]
    assert "write the five interpretation-oriented Understand chapters" in scope["included"]
    assert "publish eight concept-owned accessible SVG figures" in scope["included"]
    assert "Reference section prose" in scope["excluded"]
    assert "changes to CALM scientific algorithms" in scope["excluded"]


def test_g6_scope_owns_the_exact_public_api_reference() -> None:
    scope = _contract()["g6_scope"]
    assert "write the authored public API overview" in scope["included"]
    assert "render every public settings field meaning and default" in scope["included"]
    assert "curate returned-object members and stable analytical table fields" in scope["included"]
    assert "changes to the supported public API" in scope["excluded"]
    assert "new public figures" in scope["excluded"]




def test_g7_scope_owns_compact_reference_and_symptom_indexes() -> None:
    scope = _contract()["g7_scope"]
    assert "write the units and conventions reference" in scope["included"]
    assert "track every registered calculator family and calculated-reference capability" in scope["included"]
    assert "write two symptom-oriented troubleshooting indexes that route to contextual remedies" in scope["included"]
    assert "Home and installation prose" in scope["excluded"]
    assert "changes to supported thermodynamic formulas" in scope["excluded"]
    assert "changes to CALM scientific algorithms" in scope["excluded"]


def test_g8_scope_owns_entry_pages_and_editorial_integration() -> None:
    scope = _contract()["g8_scope"]
    assert "write the documentation home and supported installation guide" in scope["included"]
    assert "publish one project-centered workflow-map figure" in scope["included"]
    assert "remove reconstruction and phase language from public documentation" in scope["included"]
    assert "changes to supported installation artifacts or dependency metadata" in scope["excluded"]
    assert "publication deployment or compatibility redirects" in scope["excluded"]
    assert "the final strict-build and clean-environment verification campaign" in scope["excluded"]

def test_repository_readme_routes_to_the_new_reader_modes() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for label in ("Learn CALM", "Use CALM", "Understand the science", "Look something up"):
        assert label in text
    for target in (
        "docs/install.md",
        "docs/learn/first-interface.md",
        "docs/use/projects.md",
        "docs/understand/surface-models.md",
        "docs/reference/public-api.md",
    ):
        assert target in text
