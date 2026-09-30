"""Contracts for public figures owned by the greenfield Understand chapters."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "engineering" / "documentation" / "figures" / "generate_understand_figures.py"
PUBLIC_ROOT = ROOT / "docs" / "assets" / "figures" / "understand"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _load_tool():
    spec = importlib.util.spec_from_file_location("calm_understand_figures", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_understand_figure_inventory_and_page_ownership_are_exact() -> None:
    tool = _load_tool()
    expected = {
        "surface-construction-workflow.svg",
        "cell-map-types.svg",
        "coupled-common-cell.svg",
        "coherent-misfit-principal-strain.svg",
        "pareto-strain-size.svg",
        "strain-partition-path.svg",
        "registry-translation-torus.svg",
        "interface-energy-reference-cycles.svg",
    }
    assert {figure.filename for figure in tool.FIGURES} == expected
    assert {path.name for path in PUBLIC_ROOT.glob("*.svg")} == expected

    for figure in tool.FIGURES:
        owner = ROOT / figure.owner
        text = owner.read_text(encoding="utf-8")
        assert text.count(figure.filename) == 2
        assert "<figcaption>" in text
        assert '[![' in text
        assert '<img ' not in text


def test_understand_figures_are_deterministic_accessible_vector_assets(tmp_path: Path) -> None:
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
        assert (root.find("svg:title", namespace).text or "").strip()
        assert (root.find("svg:desc", namespace).text or "").strip()
        assert root.find(".//svg:image", namespace) is None


def test_lower_level_generators_do_not_write_committed_understand_assets() -> None:
    scientific = ROOT / "engineering" / "documentation" / "figures" / "generate_scientific_figures.py"
    lattice = ROOT / "engineering" / "documentation" / "figures" / "generate_lattice_figures.py"
    for path in (scientific, lattice):
        text = path.read_text(encoding="utf-8")
        assert "docs/assets/figures/understand" not in text
