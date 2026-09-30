"""Contracts for the workflow figure owned by the documentation home page."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "engineering" / "documentation" / "figures" / "generate_site_figures.py"
PUBLIC_ROOT = ROOT / "docs" / "assets" / "figures" / "site"
HOME = ROOT / "docs" / "index.md"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _load_tool():
    spec = importlib.util.spec_from_file_location("calm_site_figures", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_site_figure_inventory_and_page_ownership_are_exact() -> None:
    tool = _load_tool()
    assert tool.FILENAME == "calm-workflow-map.svg"
    assert tool.OWNER == "docs/index.md"
    assert {path.name for path in PUBLIC_ROOT.glob("*.svg")} == {tool.FILENAME}
    text = HOME.read_text(encoding="utf-8")
    assert text.count(tool.FILENAME) == 2
    assert "<figcaption>" in text
    assert '[![' in text
    assert '<img ' not in text


def test_site_figure_is_deterministic_accessible_and_vector_only(tmp_path: Path) -> None:
    tool = _load_tool()
    assert tool.rendered_figures() == tool.rendered_figures()
    assert tool.main(["--output-dir", str(tmp_path)]) == 0
    assert tool.main(["--check", "--output-dir", str(tmp_path)]) == 0
    assert tool.main(["--check"]) == 0

    path = tmp_path / tool.FILENAME
    namespace = {"svg": SVG_NAMESPACE}
    root = ET.parse(path).getroot()
    assert root.attrib["role"] == "img"
    assert root.attrib["aria-labelledby"] == "title desc"
    assert root.find("svg:title", namespace) is not None
    assert root.find("svg:desc", namespace) is not None
    assert root.find(".//svg:image", namespace) is None


def test_other_figure_generators_do_not_publish_into_the_site_tree() -> None:
    for name in (
        "generate_tutorial_figures.py",
        "generate_understand_figures.py",
        "generate_scientific_figures.py",
        "generate_lattice_figures.py",
    ):
        text = (TOOL.parent / name).read_text(encoding="utf-8")
        assert "docs/assets/figures/site" not in text
