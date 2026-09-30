#!/usr/bin/env python3
"""Generate the public SVG figures owned by CALM's Learn tutorials."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable, Sequence
import sys
import xml.etree.ElementTree as ET

from generate_scientific_figures import SVG

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "figures" / "tutorials"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)


@dataclass(frozen=True)
class TutorialFigure:
    name: str
    filename: str
    title: str
    description: str
    build: Callable[[], SVG]


def _first_interface_workflow() -> SVG:
    svg = SVG(
        "Calculator-free first-interface workflow",
        "Seven connected stages show packaged LiF and Li2O structures becoming saved materials, explicit surfaces, a bounded coherent-interface search, one selected candidate, a built interface, and exported files. A lower band states that no calculator is required and that the result is constructed but unrelaxed.",
    )
    svg.text(56, 54, "From packaged structures to one saved coherent interface", "title")
    svg.text(
        56,
        82,
        "The first tutorial performs geometry, search, construction, and export without loading a calculator.",
        "body",
    )

    stages = [
        ("1", "tutorial structures", "LiF · Li₂O", "panel-a"),
        ("2", "project materials", "saved bulk inputs", "panel-a"),
        ("3", "explicit surfaces", "selected (100) terminations", "panel-amber"),
        ("4", "bounded search", "strain · supercell · atoms", "panel-violet"),
        ("5", "candidate", "inspect before selection", "panel-violet"),
        ("6", "build", "gap · vacuum · registry", "panel-b"),
        ("7", "saved interface", "stage = built", "panel-b"),
    ]
    x0 = 42
    y = 158
    w = 172
    h = 252
    gap = 25
    for index, (number, title, subtitle, panel) in enumerate(stages):
        x = x0 + index * (w + gap)
        svg.rect(x, y, w, h, panel, rx=16)
        badge_cls = {
            "panel-a": "panel-a",
            "panel-amber": "panel-amber",
            "panel-violet": "panel-violet",
            "panel-b": "panel-b",
        }[panel]
        svg.circle(x + 28, y + 30, 18, badge_cls)
        svg.text(x + 28, y + 35, number, "label", anchor="middle")
        svg.text(x + w / 2, y + 72, title, "panel-title", anchor="middle")
        svg.text(x + w / 2, y + 98, subtitle, "small", anchor="middle")

        if index == 0:
            for row, cls in ((0, "atom-a"), (1, "atom-b")):
                for col in range(4):
                    svg.circle(x + 44 + col * 28, y + 145 + row * 42, 7, cls)
            svg.text(x + w / 2, y + 225, "fresh ASE Atoms", "tiny", anchor="middle")
        elif index == 1:
            svg.rect(x + 35, y + 128, 102, 38, "panel-white", rx=8)
            svg.rect(x + 35, y + 178, 102, 38, "panel-white", rx=8)
            svg.text(x + w / 2, y + 153, "LiF", "label a-text", anchor="middle")
            svg.text(x + w / 2, y + 203, "Li₂O", "label b-text", anchor="middle")
        elif index == 2:
            svg.line(x + 32, y + 151, x + 140, y + 151, "line-a")
            svg.line(x + 32, y + 193, x + 140, y + 193, "line-b")
            for col in range(4):
                svg.circle(x + 46 + col * 27, y + 137, 6, "atom-a")
                svg.circle(x + 46 + col * 27, y + 207, 6, "atom-b")
            svg.text(x + w / 2, y + 232, "contact faces chosen", "tiny", anchor="middle")
        elif index == 3:
            for col, value in enumerate((0.18, 0.12, 0.08, 0.05)):
                cx = x + 42 + col * 29
                cy = y + 210 - value * 270
                svg.circle(cx, cy, 6, "point-front" if col > 1 else "point-dominated")
            svg.line(x + 31, y + 213, x + 142, y + 213, "line-muted")
            svg.line(x + 31, y + 128, x + 31, y + 213, "line-muted")
            svg.text(x + w / 2, y + 232, "admitted matches", "tiny", anchor="middle")
        elif index == 4:
            svg.rect(x + 39, y + 134, 94, 78, "panel-white", rx=8)
            svg.text(x + w / 2, y + 158, "ID", "small", anchor="middle")
            svg.text(x + w / 2, y + 181, "size + strain", "small", anchor="middle")
            svg.text(x + w / 2, y + 204, "score", "small", anchor="middle")
        elif index == 5:
            svg.rect(x + 38, y + 132, 96, 86, "panel-white", rx=8)
            svg.text(x + w / 2, y + 154, "α = 0.5", "small", anchor="middle")
            svg.text(x + w / 2, y + 178, "gap = 1.5 Å", "small", anchor="middle")
            svg.text(x + w / 2, y + 202, "t = (0, 0)", "small", anchor="middle")
        else:
            for row, cls in ((0, "atom-a"), (1, "atom-b")):
                yy = y + 150 + row * 47
                for col in range(4):
                    svg.circle(x + 44 + col * 28, yy, 7, cls)
            svg.line(x + 31, y + 174, x + 141, y + 174, "line-violet")
            svg.text(x + w / 2, y + 229, "structure + table", "tiny", anchor="middle")

        if index < len(stages) - 1:
            svg.line(
                x + w + 4,
                y + h / 2,
                x + w + gap - 4,
                y + h / 2,
                "line",
                marker_end="arrow-muted",
            )

    svg.rect(88, 500, 1264, 180, "panel-white", rx=18)
    svg.text(126, 548, "What the completed tutorial establishes", "panel-title")
    statements = [
        ("No calculator", "search and construction", "use geometry only", "a-text"),
        ("Saved lineage", "the project can be reopened", "and continued", "violet-text"),
        ("Explicit choices", "termination · bounds · strain sharing", "gap · vacuum · registry", "b-text"),
        ("Not yet validated", "built and unrelaxed", "feasibility is not stability", "red-text"),
    ]
    for i, (heading, line_one, line_two, cls) in enumerate(statements):
        x = 126 + i * 304
        svg.text(x, 586, heading, "label " + cls)
        svg.text(x, 616, line_one, "small")
        svg.text(x, 642, line_two, "small")
    return svg


def _candidate_selection() -> SVG:
    svg = SVG(
        "Candidate filtering and Pareto selection",
        "An illustrative scatter plot compares interface candidates by estimated atom count and cell mismatch. Four nondominated Pareto points form a descending front. Three points also satisfy the tutorial strain threshold and become a shortlist. A side panel emphasizes that the shortlist still requires a modeling decision.",
    )
    svg.text(56, 54, "Pareto filtering narrows the choices; it does not choose the physics", "title")
    svg.text(
        56,
        82,
        "Illustrative geometry follows the verified tutorial outcome: 429 candidates, 4 Pareto candidates, and a 3-candidate shortlist.",
        "body",
    )

    # Plot panel.
    svg.rect(44, 116, 866, 574, "panel-white")
    px0, py0 = 130, 610
    px1, py1 = 850, 174
    svg.line(px0, py0, px1, py0, "line-heavy", marker_end="arrow-ink")
    svg.line(px0, py0, px0, py1, "line-heavy", marker_end="arrow-ink")
    svg.text((px0 + px1) / 2, 662, "estimated interface atoms", "label", anchor="middle")
    svg.text(69, (py0 + py1) / 2, "cell mismatch  d_cell", "label", anchor="middle", transform=f"rotate(-90 69 {(py0 + py1) / 2:g})")
    for x in range(220, 821, 120):
        svg.line(x, py1 + 22, x, py0, "grid")
    for y in range(230, 591, 72):
        svg.line(px0, y, px1 - 20, y, "grid")

    dominated = [
        (190, 276), (240, 332), (290, 250), (335, 385), (390, 304),
        (435, 430), (485, 348), (535, 470), (590, 388), (640, 508),
        (690, 442), (735, 538), (790, 486), (825, 565), (360, 485),
        (520, 255), (680, 310), (760, 360), (285, 520), (445, 560),
    ]
    for x, y in dominated:
        svg.circle(x, y, 7, "point-dominated")

    pareto = [(205, 520), (330, 455), (510, 370), (735, 250)]
    # Front step path.
    svg.path(
        "M 205 520 H 330 V 455 H 510 V 370 H 735 V 250",
        "line-a",
    )
    for i, (x, y) in enumerate(pareto):
        cls = "point-selected" if i < 3 else "point-front"
        svg.circle(x, y, 11, cls)
        svg.text(x + 13, y - 13, f"P{i + 1}", "small")

    svg.text(174, 205, "dominated candidate", "small red-text")
    svg.circle(153, 199, 7, "point-dominated")
    svg.text(350, 205, "Pareto candidate", "small a-text")
    svg.circle(330, 199, 9, "point-front")
    svg.text(535, 205, "shortlisted", "small violet-text")
    svg.circle(515, 199, 10, "point-selected")

    # Selection panel.
    svg.rect(944, 116, 452, 574, "panel-violet")
    svg.text(1170, 158, "Tutorial selection sequence", "panel-title violet-text", anchor="middle")
    steps = [
        ("429", "admitted candidates", "complete search population"),
        ("4", "Pareto candidates", "no candidate is smaller and less mismatched"),
        ("3", "strain-eligible", "max principal strain ≤ 0.08"),
        ("≤ 5", "score-ranked shortlist", "retain alternatives for later physics"),
    ]
    y = 210
    for idx, (count, title, body) in enumerate(steps):
        svg.rect(982, y, 376, 78, "panel-white", rx=12)
        svg.circle(1022, y + 39, 24, "panel-violet")
        svg.text(1022, y + 45, count, "label violet-text", anchor="middle")
        svg.text(1062, y + 30, title, "label")
        svg.text(1062, y + 55, body, "small")
        if idx < len(steps) - 1:
            svg.line(1170, y + 81, 1170, y + 103, "line-violet", marker_end="arrow-violet")
        y += 105
    svg.text(1170, 634, "Final choice depends on the modeling objective", "label", anchor="middle")
    svg.text(1170, 660, "cell cost · strain tolerance · downstream relaxation · scientific scope", "small", anchor="middle")
    return svg


def _refine_relax_evaluate() -> SVG:
    svg = SVG(
        "Refine, relax, and evaluate workflow",
        "A built Cu/Ni interface passes through strain-partition and registry refinement, then fixed-cell relaxation. Raw interface energy and independently relaxed fixed-cell surface reference energies feed an explicit work-of-adhesion equation divided by interface area and interface multiplicity. Every calculator-backed stage is marked as a local model-dependent calculation.",
    )
    svg.text(56, 54, "Calculator-backed stages add energetic evidence in explicit layers", "title")
    svg.text(
        56,
        82,
        "ASE EMT demonstrates workflow mechanics; each result remains conditional on the model, starting structure, settings, and reference process.",
        "body",
    )

    # Top pipeline.
    cards = [
        (48, "built interface", "coherent cell\ninitial gap + registry", "panel-b"),
        (320, "strain partition", "α = 0, 0.5, 1\nenergy-density target", "panel-violet"),
        (592, "registry refinement", "periodic translations\n16-step search", "panel-violet"),
        (864, "fixed-cell relaxation", "forces converge\ncell remains coherent", "panel-amber"),
        (1136, "relaxed interface", "raw total energy\nE_int", "panel-b"),
    ]
    for idx, (x, title, body, panel) in enumerate(cards):
        svg.rect(x, 132, 224, 170, panel, rx=16)
        svg.circle(x + 28, 160, 18, panel)
        svg.text(x + 28, 166, str(idx + 1), "label", anchor="middle")
        svg.text(x + 112, 197, title, "panel-title", anchor="middle")
        lines = body.split("\n")
        svg.text(x + 112, 235, lines[0], "small", anchor="middle")
        svg.text(x + 112, 260, lines[1], "small", anchor="middle")
        if idx < len(cards) - 1:
            svg.line(x + 228, 217, x + 264, 217, "line", marker_end="arrow-muted")

    svg.rect(62, 360, 1316, 330, "panel-white", rx=18)
    svg.text(100, 404, "Explicit reference cycle", "panel-title")

    # Interface energy card.
    svg.rect(110, 446, 310, 172, "panel-b", rx=14)
    svg.text(265, 480, "relaxed interface calculation", "label b-text", anchor="middle")
    for row, cls in ((0, "atom-a"), (1, "atom-b")):
        yy = 528 + row * 42
        for col in range(6):
            svg.circle(170 + col * 38, yy, 6, cls)
    svg.line(145, 549, 385, 549, "line-violet")
    svg.text(265, 602, "E_int", "math", anchor="middle")

    # Reference surface card.
    svg.rect(565, 446, 310, 172, "panel-a", rx=14)
    svg.text(720, 480, "independent fixed-cell surfaces", "label a-text", anchor="middle")
    svg.line(620, 525, 700, 525, "line-a")
    svg.line(740, 567, 820, 567, "line-b")
    for col in range(4):
        svg.circle(630 + col * 22, 512, 6, "atom-a")
        svg.circle(750 + col * 22, 580, 6, "atom-b")
    svg.text(720, 602, "E_A^rel  +  E_B^rel", "math", anchor="middle")

    svg.line(426, 532, 548, 532, "line", marker_end="arrow-muted")

    # Formula card.
    svg.rect(1010, 430, 320, 204, "panel-violet", rx=14)
    svg.text(1170, 470, "work of adhesion", "panel-title violet-text", anchor="middle")
    svg.text(1170, 520, "W_ad = (E_A^rel + E_B^rel − E_int)", "math-small", anchor="middle")
    svg.line(1082, 535, 1258, 535, "line-heavy")
    svg.text(1170, 566, "n_int A", "math-small", anchor="middle")
    svg.text(1170, 602, "n_int = 2 in this tutorial", "small", anchor="middle")
    svg.line(882, 532, 994, 532, "line-violet", marker_end="arrow-violet")

    svg.text(720, 664, "Refinement, relaxation, raw energies, and the derived quantity remain separate inspectable results.", "body", anchor="middle")
    return svg


FIGURES: tuple[TutorialFigure, ...] = (
    TutorialFigure(
        name="first-interface-workflow",
        filename="first-interface-workflow.svg",
        title="Calculator-free first-interface workflow",
        description=(
            "Seven connected stages show packaged LiF and Li2O structures becoming "
            "saved materials, explicit surfaces, a bounded coherent-interface search, "
            "one selected candidate, a built interface, and exported files. A lower "
            "band states that no calculator is required and that the result is "
            "constructed but unrelaxed."
        ),
        build=_first_interface_workflow,
    ),
    TutorialFigure(
        name="candidate-selection",
        filename="candidate-selection.svg",
        title="Candidate filtering and Pareto selection",
        description=(
            "An illustrative scatter plot compares interface candidates by estimated "
            "atom count and cell mismatch. Four nondominated Pareto points form a "
            "descending front. Three points also satisfy the tutorial strain threshold "
            "and become a shortlist. A side panel emphasizes that the shortlist still "
            "requires a modeling decision."
        ),
        build=_candidate_selection,
    ),
    TutorialFigure(
        name="refine-relax-evaluate",
        filename="refine-relax-evaluate.svg",
        title="Refine, relax, and evaluate workflow",
        description=(
            "A built Cu/Ni interface passes through strain-partition and registry "
            "refinement, then fixed-cell relaxation. Raw interface energy and "
            "independently relaxed fixed-cell surface reference energies feed an "
            "explicit work-of-adhesion equation divided by interface area and "
            "interface multiplicity. Every calculator-backed stage is marked as a "
            "local model-dependent calculation."
        ),
        build=_refine_relax_evaluate,
    ),
)


def rendered_figures() -> dict[str, str]:
    return {figure.filename: figure.build().render() for figure in FIGURES}


def _svg_tag(name: str) -> str:
    return f"{{{SVG_NAMESPACE}}}{name}"


def validate_svg(path: Path, figure: TutorialFigure) -> list[str]:
    if not path.is_file():
        return [f"missing tutorial figure: {path}"]
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
    if root.find(f".//{_svg_tag('image')}") is not None:
        errors.append(f"{path}: raster image content is not permitted")
    title = root.find(_svg_tag("title"))
    description = root.find(_svg_tag("desc"))
    if title is None or (title.text or "").strip() != figure.title:
        errors.append(f"{path}: accessible title does not match")
    if description is None or (description.text or "").strip() != figure.description:
        errors.append(f"{path}: accessible description does not match")
    return errors


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="SVG output directory",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that committed figures match generated output",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir.resolve()
    expected = rendered_figures()
    if args.check:
        errors: list[str] = []
        for figure in FIGURES:
            path = output_dir / figure.filename
            errors.extend(validate_svg(path, figure))
            if path.is_file() and path.read_text(encoding="utf-8") != expected[figure.filename]:
                errors.append(f"{path}: committed content differs from generated output")
        if output_dir.is_dir():
            extras = sorted(
                path.name
                for path in output_dir.glob("*.svg")
                if path.name not in expected
            )
            if extras:
                errors.append("unowned tutorial figure assets: " + ", ".join(extras))
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print(f"validated {len(FIGURES)} tutorial figures in {_display_path(output_dir)}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in expected.items():
        (output_dir / filename).write_text(content, encoding="utf-8")
    print(f"wrote {len(expected)} tutorial figures to {_display_path(output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
