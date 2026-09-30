#!/usr/bin/env python3
"""Generate the public SVG figure owned by CALM's documentation home page."""

from __future__ import annotations

import argparse
from pathlib import Path
from collections.abc import Sequence
import sys
import xml.etree.ElementTree as ET

TOOL_ROOT = Path(__file__).resolve().parent
ROOT = TOOL_ROOT.parents[2]
PUBLIC_ROOT = ROOT / "docs" / "assets" / "figures" / "site"
FILENAME = "calm-workflow-map.svg"
OWNER = "docs/index.md"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)

if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from generate_scientific_figures import SVG  # noqa: E402


def _workflow_map() -> SVG:
    svg = SVG(
        "CALM coherent-interface workflow",
        "A project-centered workflow begins with bulk materials and explicit surfaces, continues through bounded coherent matching, candidate selection, and interface construction without a calculator, then optionally uses a calculator for refinement, relaxation, raw energies, and reference calculations. Datasets and campaigns form an optional study-management layer.",
    )
    svg.text(56, 54, "One project connects geometry, calculator-backed results, and scientific interpretation", "title")
    svg.text(
        56,
        83,
        "The core geometry path is calculator-free; energetic stages require an explicit compatible calculator and reference process.",
        "body",
    )

    # Project boundary.
    svg.rect(42, 116, 1356, 476, "panel-white", rx=22)
    svg.text(74, 150, "reopenable CALM project", "label violet-text")

    cards = [
        (70, "materials", "bulk structures", "panel-a"),
        (278, "surfaces", "explicit terminations", "panel-a"),
        (486, "search", "bounded coherent\nmatches", "panel-violet"),
        (694, "candidates", "size · strain · Pareto", "panel-violet"),
        (902, "interface", "constructed geometry", "panel-b"),
    ]
    y = 202
    w = 176
    h = 146
    gap = 32
    for index, (x, title, subtitle, panel) in enumerate(cards):
        svg.rect(x, y, w, h, panel, rx=16)
        svg.circle(x + 28, y + 29, 18, panel)
        svg.text(x + 28, y + 35, str(index + 1), "label", anchor="middle")
        svg.text(x + w / 2, y + 76, title, "panel-title", anchor="middle")
        subtitle_lines = subtitle.split("\n")
        if len(subtitle_lines) == 1:
            svg.text(x + w / 2, y + 105, subtitle_lines[0], "small", anchor="middle")
        else:
            svg.text(x + w / 2, y + 101, subtitle_lines[0], "small", anchor="middle")
            svg.text(x + w / 2, y + 122, subtitle_lines[1], "small", anchor="middle")
        if index < len(cards) - 1:
            svg.line(x + w + 5, y + h / 2, x + w + gap - 5, y + h / 2, "line", marker_end="arrow-muted")

    svg.rect(1122, y, 236, h, "panel-amber", rx=16)
    svg.text(1240, y + 43, "optional calculator path", "panel-title amber-text", anchor="middle")
    svg.text(1240, y + 77, "refine · relax · raw energy", "small", anchor="middle")
    svg.text(1240, y + 105, "references · derived quantity", "small", anchor="middle")
    svg.line(1083, y + h / 2, 1115, y + h / 2, "line-amber", marker_end="arrow-amber")

    # Evidence bands.
    bands = [
        (82, 410, 370, "Geometry evidence", "surfaces · matches · built interfaces", "panel-a", "a-text"),
        (484, 410, 418, "Calculator-backed evidence", "refinement · relaxation · raw energies", "panel-amber", "amber-text"),
        (934, 410, 408, "Derived interpretation", "explicit area · multiplicity · references", "panel-violet", "violet-text"),
    ]
    for x, by, bw, title, subtitle, panel, text_cls in bands:
        svg.rect(x, by, bw, 112, panel, rx=14)
        svg.text(x + 22, by + 42, title, f"label {text_cls}")
        svg.text(x + 22, by + 72, subtitle, "small")
        svg.text(x + 22, by + 94, "each layer preserves its assumptions", "tiny")

    # Optional study management layer.
    svg.rect(196, 628, 1048, 92, "panel", rx=18)
    svg.text(238, 666, "Optional study management", "panel-title")
    svg.text(238, 695, "datasets · grouping and leakage control · campaigns · reproducible comparisons", "body")
    svg.line(720, 592, 720, 620, "line", marker_end="arrow-muted")
    svg.text(1168, 680, "not required for every study", "small", anchor="end")
    return svg


def rendered_figures() -> dict[str, str]:
    """Return deterministic SVG content keyed by public filename."""

    return {FILENAME: _workflow_map().render()}


def _svg_tag(name: str) -> str:
    return f"{{{SVG_NAMESPACE}}}{name}"


def validate_svg(path: Path) -> list[str]:
    """Validate the accessible, vector-only public SVG."""

    if not path.is_file():
        return [f"missing site figure: {path}"]
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"could not parse {path}: {exc}"]

    errors: list[str] = []
    if root.tag != _svg_tag("svg"):
        errors.append(f"{path}: root element is not SVG")
    if root.attrib.get("role") != "img":
        errors.append(f"{path}: missing role=img")
    if root.attrib.get("aria-labelledby") != "title desc":
        errors.append(f"{path}: missing aria-labelledby='title desc'")
    title = root.find(_svg_tag("title"))
    description = root.find(_svg_tag("desc"))
    if title is None or not (title.text or "").strip():
        errors.append(f"{path}: missing accessible title")
    if description is None or not (description.text or "").strip():
        errors.append(f"{path}: missing accessible description")
    if root.find(f".//{_svg_tag('image')}") is not None:
        errors.append(f"{path}: raster image content is not permitted")
    return errors


def write_figures(output_dir: Path = PUBLIC_ROOT) -> tuple[Path, ...]:
    """Write the public site figure."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = rendered_figures()
    path = output_dir / FILENAME
    path.write_text(rendered[FILENAME], encoding="utf-8")
    return (path,)


def check_figures(output_dir: Path = PUBLIC_ROOT) -> list[str]:
    """Return drift and accessibility errors for the public site figure."""

    path = output_dir / FILENAME
    errors = validate_svg(path)
    expected = rendered_figures()[FILENAME]
    if path.is_file() and path.read_text(encoding="utf-8") != expected:
        errors.append(f"{path}: generated content differs from the committed asset")
    existing = {candidate.name for candidate in output_dir.glob("*.svg")} if output_dir.exists() else set()
    if existing != {FILENAME}:
        for unexpected in sorted(existing - {FILENAME}):
            errors.append(f"{output_dir / unexpected}: undeclared site figure")
    return errors


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PUBLIC_ROOT,
        help="SVG output directory (defaults to the public site figure tree)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the existing asset without rewriting it",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()

    if args.check:
        errors = check_figures(output_dir)
        if errors:
            print("Site figure validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(f"validated 1 site figure in {_display(output_dir)}")
        return 0

    write_figures(output_dir)
    print(f"wrote 1 site figure to {_display(output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
