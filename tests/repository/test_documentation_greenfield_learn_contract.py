"""Content contracts for the greenfield Learn tutorials."""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "learn"
EXPECTED = ROOT / "examples" / "tutorials" / "expected"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"
STUB_MARKER = "Greenfield reconstruction:"
SNIPPET_RE = re.compile(r'--8<-- "(?P<path>[^"]+):(?P<section>[^"]+)"')

PAGES = {
    "first-interface": DOCS / "first-interface.md",
    "compare-candidates": DOCS / "compare-candidates.md",
    "refine-relax-evaluate": DOCS / "refine-relax-evaluate.md",
}
SOURCES = {
    "first-interface": ROOT / "examples" / "tutorials" / "first_interface.py",
    "compare-candidates": ROOT / "examples" / "tutorials" / "compare_candidates.py",
    "refine-relax-evaluate": ROOT / "examples" / "tutorials" / "refine_relax_evaluate.py",
}


def _headings(text: str) -> list[str]:
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def test_learn_pages_follow_one_predictable_anatomy() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    anatomy = contract["page_anatomy"]["learn"]
    assert anatomy == [
        "Outcome",
        "Prerequisites",
        "Workflow",
        "Inspect the result",
        "Expected output",
        "Interpretation",
        "Limitations",
        "Next step",
    ]
    authored_order = anatomy
    for page in PAGES.values():
        text = page.read_text(encoding="utf-8")
        assert STUB_MARKER not in text
        assert _headings(text) == authored_order
        assert text.count("<figure") == 1
        assert "<figcaption>" in text


def test_learn_pages_use_only_canonical_tested_source_snippets() -> None:
    used_sources: set[Path] = set()
    for page in PAGES.values():
        for match in SNIPPET_RE.finditer(page.read_text(encoding="utf-8")):
            source = ROOT / match.group("path")
            assert source in set(SOURCES.values())
            used_sources.add(source)
            text = source.read_text(encoding="utf-8")
            assert f"# --8<-- [start:{match.group('section')}]" in text
            assert f"# --8<-- [end:{match.group('section')}]" in text
    assert used_sources == set(SOURCES.values())


def test_documented_outcomes_and_artifacts_match_expected_output_fixtures() -> None:
    for name, page in PAGES.items():
        expected = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))
        text = page.read_text(encoding="utf-8")
        assert expected["outcome"] in text
        for artifact in expected["required_artifacts"]:
            assert artifact in text
        assert str(expected["calculator_required"]).lower() in text.lower() or (
            "Calculator:** not required" in text
            if not expected["calculator_required"]
            else "Calculator:** ASE EMT" in text
        )


def test_first_interface_tutorial_states_the_construction_boundary() -> None:
    text = PAGES["first-interface"].read_text(encoding="utf-8")
    for phrase in (
        "constructed but not relaxed",
        "Geometric feasibility",
        "stage is `built`",
        "does not infer which termination is physically correct",
        "exact candidate count is not part of the tutorial contract",
    ):
        assert phrase in text


def test_candidate_tutorial_separates_pareto_filtering_from_physical_selection() -> None:
    text = PAGES["compare-candidates"].read_text(encoding="utf-8")
    for phrase in (
        "strain–size Pareto front",
        "max_principal_strain=(None, 0.08)",
        "The search score is not a thermodynamic quantity",
        "does not claim that this candidate is universally best",
        "not a fixed expected outcome",
    ):
        assert phrase in text


def test_calculator_tutorial_states_model_and_reference_limits() -> None:
    text = PAGES["refine-relax-evaluate"].read_text(encoding="utf-8")
    for phrase in (
        "EMT is a workflow demonstration",
        "work_of_adhesion_relaxed_surfaces",
        "n_interfaces=2",
        "fixed-cell",
        "does not prove global stability",
        "report the derived result as unavailable",
    ):
        assert phrase in text
