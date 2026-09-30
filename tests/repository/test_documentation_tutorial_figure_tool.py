"""Contracts for the public figures owned by the greenfield Learn tutorials."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import sys


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "engineering" / "documentation" / "figures" / "generate_tutorial_figures.py"
PUBLIC_ROOT = ROOT / "docs" / "assets" / "figures" / "tutorials"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _load_tool():
    spec = importlib.util.spec_from_file_location("calm_tutorial_figures", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tutorial_figure_inventory_and_page_ownership_are_exact() -> None:
    tool = _load_tool()
    assert {figure.filename for figure in tool.FIGURES} == {
        "first-interface-workflow.svg",
        "candidate-selection.svg",
        "refine-relax-evaluate.svg",
    }
    assert {path.name for path in PUBLIC_ROOT.glob("*.svg")} == {
        figure.filename for figure in tool.FIGURES
    }

    owners = {
        "first-interface-workflow.svg": ROOT / "docs" / "learn" / "first-interface.md",
        "candidate-selection.svg": ROOT / "docs" / "learn" / "compare-candidates.md",
        "refine-relax-evaluate.svg": ROOT / "docs" / "learn" / "refine-relax-evaluate.md",
    }
    for filename, owner in owners.items():
        text = owner.read_text(encoding="utf-8")
        assert text.count(filename) == 2
        assert "<figcaption>" in text
        assert '[![' in text
        assert '<img ' not in text


def test_tutorial_figures_are_deterministic_accessible_vector_assets(tmp_path: Path) -> None:
    tool = _load_tool()
    first = tool.rendered_figures()
    second = tool.rendered_figures()
    assert first == second

    assert tool.main(["--output-dir", str(tmp_path)]) == 0
    assert tool.main(["--check", "--output-dir", str(tmp_path)]) == 0
    assert tool.main(["--check"]) == 0

    namespace = {"svg": SVG_NAMESPACE}
    for figure in tool.FIGURES:
        path = tmp_path / figure.filename
        root = ET.parse(path).getroot()
        assert root.attrib["role"] == "img"
        assert root.attrib["aria-labelledby"] == "title desc"
        assert root.find("svg:title", namespace).text == figure.title
        assert root.find("svg:desc", namespace).text == figure.description
        assert root.find(".//svg:image", namespace) is None


def test_legacy_figure_generators_do_not_publish_into_the_tutorial_tree() -> None:
    scientific = ROOT / "engineering" / "documentation" / "figures" / "generate_scientific_figures.py"
    lattice = ROOT / "engineering" / "documentation" / "figures" / "generate_lattice_figures.py"
    for path in (scientific, lattice):
        text = path.read_text(encoding="utf-8")
        assert "docs/assets/figures/tutorials" not in text
