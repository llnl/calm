"""Contracts for the greenfield compact reference and symptom indexes."""

from __future__ import annotations

import json
from pathlib import Path
import re

from calm.calculators.registry import default_registry
from calm.interface.energy.contract import (
    EV_PER_A2_TO_J_PER_M2,
    FORMULA_TO_QUANTITY,
)


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"
REFERENCE = DOCS / "reference"


def _text(name: str) -> str:
    return (REFERENCE / name).read_text(encoding="utf-8")


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[`'\"]", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def _common_problem_headings(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    collecting = False
    headings: list[str] = []
    for line in lines:
        if line == "## Common problems":
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting and line.startswith("### "):
            headings.append(line[4:].strip())
    return headings


def test_g7_reference_pages_are_implemented_and_owned() -> None:
    contract = _contract()
    entries: list[dict[str, object]] = []

    def collect(rows: list[dict[str, object]]) -> None:
        for row in rows:
            if row.get("children"):
                collect(row["children"])
            else:
                entries.append(row)

    collect(contract["navigation"])
    g7 = [row for row in entries if row.get("phase") == "G7"]
    assert {row["path"] for row in g7} == {
        "reference/units-conventions.md",
        "reference/terminology.md",
        "reference/supported-scope.md",
        "reference/calculator-support.md",
        "reference/troubleshooting-geometry.md",
        "reference/troubleshooting-calculations.md",
    }
    for row in g7:
        text = (DOCS / row["path"]).read_text(encoding="utf-8")
        assert row.get("implemented") is True
        assert "Greenfield reconstruction:" not in text
        for heading in contract["page_anatomy"]["reference"]:
            assert f"## {heading}" in text


def test_units_page_tracks_runtime_units_and_coordinate_conventions() -> None:
    text = _text("units-conventions.md")
    assert f"{EV_PER_A2_TO_J_PER_M2:.8f}" in text
    for token in (
        "eV/Å",
        "eV/Å²",
        "J/m²",
        "basis vectors as **columns**",
        "ASE stores the same cell vectors as rows",
        "principal logarithmic",
        "authoritative_interface_area",
        "prototype_interface_area",
        "n_interfaces",
        "DatasetFeature.units",
        "DatasetTarget.units",
    ):
        assert token in text
    assert "alpha = 0" in text
    assert "alpha = 1" in text
    assert "[0, 1)" in text


def test_terminology_page_uses_the_compact_public_vocabulary() -> None:
    text = _text("terminology.md")
    for term in (
        "**Project**",
        "**Material**",
        "**Surface**",
        "**Termination**",
        "**Search**",
        "**Candidate**",
        "**Interface**",
        "**Refinement**",
        "**Relaxation**",
        "**Raw energy**",
        "**Reference calculation**",
        "**Derived quantity**",
        "**Dataset**",
        "**Campaign**",
        "**Short identifier (`id_short`)**",
        "**Full identifier (`uid_full`)**",
    ):
        assert term in text
    for forbidden in (
        "unit-of-work",
        "serializer payload",
        "database table layout",
        "canonical payload construction",
        "migration strategy",
    ):
        assert forbidden not in text.lower()


def test_supported_scope_tracks_every_public_energy_formula() -> None:
    text = _text("supported-scope.md")
    assert set(FORMULA_TO_QUANTITY) == {
        "interface_excess_strained_bulk",
        "work_of_separation_unrelaxed_surfaces",
        "work_of_adhesion_relaxed_surfaces",
    }
    for formula, quantity in FORMULA_TO_QUANTITY.items():
        assert f"`{formula}`" in text
        assert quantity.replace("_", " ") in text.lower()
    for phrase in (
        "does not infer the physically correct termination",
        "misfit dislocations",
        "Variable-cell relaxed interfaces are outside",
        "independently relaxed fixed-cell surface",
        "CALM executes synchronously",
        "preserve the original directory",
    ):
        assert phrase.lower() in text.lower()


def test_calculator_support_tracks_the_live_registry() -> None:
    text = _text("calculator-support.md")
    families = default_registry().families()
    assert families == ("ase", "chgnet", "grace", "lammps", "mace")
    for family in families:
        assert f"`{family}`" in text
        assert f"--provider {family}" in text
    for distinction in (
        "Registered",
        "Available",
        "Compatible",
        "Scientifically suitable",
    ):
        assert distinction in text
    for formula in FORMULA_TO_QUANTITY:
        assert f"`{formula}`" in text
    assert "convention.reference_capability()" in text
    assert "capability.raise_for_calculated_references()" in text
    assert "does not run model inference or certify scientific accuracy" in text


def test_every_contextual_common_problem_is_indexed() -> None:
    geometry = _text("troubleshooting-geometry.md")
    calculations = _text("troubleshooting-calculations.md")
    combined = geometry + "\n" + calculations

    for path in sorted((DOCS / "use").glob("*.md")):
        for heading in _common_problem_headings(path):
            target = f"../use/{path.name}#{_slug(heading)}"
            assert target in combined, f"Missing troubleshooting route for {path.name}: {heading}"


def test_troubleshooting_pages_are_symptom_oriented_and_safe() -> None:
    geometry = _text("troubleshooting-geometry.md")
    calculations = _text("troubleshooting-calculations.md")
    for text in (geometry, calculations):
        assert "| Symptom | Likely cause | First action | Canonical guidance |" in text
        assert "edit project files" not in text.lower()
        assert "calm.public" not in text
        assert "calm.project" not in text
        assert "engineering/" not in text
    assert "preserve the project directory" in geometry
    assert "CALM runs synchronously" in calculations
    assert "Do not publish credentials" in geometry
