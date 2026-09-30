#!/usr/bin/env python3
"""Generate the public figures owned by the greenfield Understand chapters."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence
import sys
import xml.etree.ElementTree as ET

TOOL_ROOT = Path(__file__).resolve().parent
ROOT = TOOL_ROOT.parents[2]
PUBLIC_ROOT = ROOT / "docs" / "assets" / "figures" / "understand"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)

if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from generate_lattice_figures import render_svg as render_lattice_svg  # noqa: E402
from generate_scientific_figures import rendered_figures as rendered_scientific_figures  # noqa: E402
from lattice_figure_recipes import recipe_map  # noqa: E402


@dataclass(frozen=True)
class FigureAsset:
    """One public figure and its single authored page owner."""

    filename: str
    owner: str
    source: str


FIGURES: tuple[FigureAsset, ...] = (
    FigureAsset(
        "surface-construction-workflow.svg",
        "docs/understand/surface-models.md",
        "scientific",
    ),
    FigureAsset(
        "cell-map-types.svg",
        "docs/understand/surface-supercells.md",
        "lattice",
    ),
    FigureAsset(
        "coupled-common-cell.svg",
        "docs/understand/coherent-matching.md",
        "lattice",
    ),
    FigureAsset(
        "coherent-misfit-principal-strain.svg",
        "docs/understand/coherent-matching.md",
        "scientific",
    ),
    FigureAsset(
        "pareto-strain-size.svg",
        "docs/understand/coherent-matching.md",
        "scientific",
    ),
    FigureAsset(
        "strain-partition-path.svg",
        "docs/understand/strain-registry.md",
        "lattice",
    ),
    FigureAsset(
        "registry-translation-torus.svg",
        "docs/understand/strain-registry.md",
        "scientific",
    ),
    FigureAsset(
        "interface-energy-reference-cycles.svg",
        "docs/understand/energetics.md",
        "scientific",
    ),
)

LATTICE_RECIPE_BY_FILENAME = {
    recipe.filename: recipe
    for recipe in recipe_map().values()
}


def _svg_tag(name: str) -> str:
    return f"{{{SVG_NAMESPACE}}}{name}"


def rendered_figures() -> dict[str, str]:
    """Return deterministic SVG content keyed by public filename."""

    scientific = rendered_scientific_figures()
    rendered: dict[str, str] = {}
    for figure in FIGURES:
        if figure.source == "scientific":
            rendered[figure.filename] = scientific[figure.filename]
        elif figure.source == "lattice":
            rendered[figure.filename] = render_lattice_svg(
                LATTICE_RECIPE_BY_FILENAME[figure.filename]
            )
        else:  # pragma: no cover - closed inventory
            raise RuntimeError(f"Unknown figure source {figure.source!r}")
    return rendered


def validate_svg(path: Path) -> list[str]:
    """Validate one accessible, vector-only public SVG."""

    errors: list[str] = []
    if not path.is_file():
        return [f"missing Understand figure: {path}"]
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"could not parse {path}: {exc}"]

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
    """Write every Understand figure and return the paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = rendered_figures()
    paths: list[Path] = []
    for figure in FIGURES:
        path = output_dir / figure.filename
        path.write_text(rendered[figure.filename], encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def check_figures(output_dir: Path = PUBLIC_ROOT) -> list[str]:
    """Return drift and accessibility errors for the committed assets."""

    expected = rendered_figures()
    errors: list[str] = []
    for figure in FIGURES:
        path = output_dir / figure.filename
        errors.extend(validate_svg(path))
        if path.is_file() and path.read_text(encoding="utf-8") != expected[figure.filename]:
            errors.append(f"{path}: generated content differs from the committed asset")
    existing = {path.name for path in output_dir.glob("*.svg")} if output_dir.exists() else set()
    declared = {figure.filename for figure in FIGURES}
    for unexpected in sorted(existing - declared):
        errors.append(f"{output_dir / unexpected}: undeclared Understand figure")
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
        help="SVG output directory (defaults to the public Understand figure tree)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the existing assets without rewriting them",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()

    if args.check:
        errors = check_figures(output_dir)
        if errors:
            print("Understand figure validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print(f"validated {len(FIGURES)} Understand figures in {_display(output_dir)}")
        return 0

    paths = write_figures(output_dir)
    print(f"wrote {len(paths)} Understand figures to {_display(output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
