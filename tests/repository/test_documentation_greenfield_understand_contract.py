"""Content contracts for the greenfield Understand scientific manual."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "understand"
STUB_MARKER = "Greenfield reconstruction:"

PAGES = {
    "surface-models": DOCS / "surface-models.md",
    "surface-supercells": DOCS / "surface-supercells.md",
    "coherent-matching": DOCS / "coherent-matching.md",
    "strain-registry": DOCS / "strain-registry.md",
    "energetics": DOCS / "energetics.md",
}

HEADINGS = (
    "Scientific question",
    "Physical interpretation",
    "Definition",
    "How CALM uses it",
    "What the user controls",
    "Assumptions and limitations",
    "Related workflow",
    "References",
)


def _text(name: str) -> str:
    return PAGES[name].read_text(encoding="utf-8")


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value)


def test_understand_pages_are_complete_and_share_one_anatomy() -> None:
    for path in PAGES.values():
        text = path.read_text(encoding="utf-8")
        assert STUB_MARKER not in text
        assert text.count("# ") >= 1
        assert text.count("<figure") >= 1
        assert "calm-lede" in text
        assert "doi.org/" in text
        for heading in HEADINGS:
            assert f"## {heading}" in text, f"{path}: missing {heading}"


def test_surface_model_chapter_separates_geometry_from_model_choices() -> None:
    text = _text("surface-models")
    compact = _compact(text)
    for phrase in (
        "Miller index identifies a family of bulk lattice planes",
        "side A contributes its **top** face",
        "side B contributes its **bottom** face",
        "CALM does not infer the physically correct termination",
        "ideal bulk-derived slabs",
        "not necessarily thermodynamically stable",
    ):
        assert phrase in compact
    assert "surface-construction-workflow.svg" in text
    assert "\\mathbf m^{\\mathsf T}\\mathbf u=0" in text


def test_surface_supercell_chapter_defines_basis_supercell_and_deformation() -> None:
    text = _text("surface-supercells")
    compact = _compact(text)
    for phrase in (
        "basis vectors as columns",
        "same lattice",
        "index is",
        "Only the last operation is strain",
        "No candidates",
    ):
        assert phrase in compact
    for token in (
        "\\mathbf S'=\\mathbf S\\mathbf U",
        "n=|\\det\\mathbf H|",
        "A_H=nA_0",
        "\\mathbf G=\\mathbf S^{\\mathsf T}\\mathbf S",
    ):
        assert token in text
    assert "cell-map-types.svg" in text


def test_coherent_matching_chapter_matches_public_candidate_quantities() -> None:
    text = _text("coherent-matching")
    compact = _compact(text)
    for token in (
        "max_principal_strain",
        "max_supercell_index",
        "n_atoms_estimate",
        "d_cell",
        "d_area",
        "d_shape",
        "is_pareto",
        "mismatch_weight",
    ):
        assert token in text
    for phrase in (
        "not an elastic energy",
        "not a scientific ranking",
        "Low mismatch does not imply",
        "Changing bounds can change the front",
    ):
        assert phrase in compact
    for figure in (
        "coupled-common-cell.svg",
        "coherent-misfit-principal-strain.svg",
        "pareto-strain-size.svg",
    ):
        assert figure in text
    assert "\\varepsilon_i=\\ln\\lambda_i" in text
    assert "d_{\\mathrm{cell}}" in text


def test_strain_registry_chapter_defines_alpha_endpoints_and_periodicity() -> None:
    text = _text("strain-registry")
    compact = _compact(text)
    for phrase in (
        "alpha=0",
        "alpha=1",
        "geometric midpoint in metric space",
        "not automatically the elastic-energy minimum",
        "opposite edges of the unit square represent the same registry state",
        "best unrelaxed registry may change after atomic relaxation",
    ):
        assert phrase in compact
    for figure in ("strain-partition-path.svg", "registry-translation-torus.svg"):
        assert figure in text
    assert "\\mathbf t=\\mathbf X\\mathbf q" in text
    assert "0\\le\\alpha\\le1" in text


def test_energetics_chapter_keeps_relaxation_and_reference_meaning_separate() -> None:
    text = _text("energetics")
    compact = _compact(text)
    for token in (
        "interface_excess_strained_bulk",
        "work_of_separation_unrelaxed_surfaces",
        "work_of_adhesion_relaxed_surfaces",
        "EnergyConvention.reference_capability()",
        "n_interfaces",
        "16.02176634",
    ):
        assert token in text
    for phrase in (
        "raw total energy is not an interface energy",
        "does not prove global stability",
        "report the derived result as unavailable",
        "chemical-potential reservoirs",
        "finite-temperature free-energy contributions",
    ):
        assert phrase in compact
    assert "interface-energy-reference-cycles.svg" in text
    assert "W_{\\mathrm{ad}}^{\\mathrm{rel}}" in text
    assert "\\gamma_{\\mathrm{sb}}" in text


def test_scientific_manual_avoids_implementation_documentation() -> None:
    combined = "\n".join(_text(name) for name in PAGES)
    banned = (
        "serializer",
        "database schema",
        "migration strategy",
        "canonical payload",
        "unit of work",
        "persistence adapter",
        "qualification campaign",
        "HNF orbit",
        "exact integer certificate",
    )
    lowered = combined.casefold()
    for phrase in banned:
        assert phrase.casefold() not in lowered
