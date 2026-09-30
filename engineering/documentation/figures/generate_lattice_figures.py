#!/usr/bin/env python3
"""Generate CALM lattice figures with the vendored latticeplot2d tool."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from io import BytesIO
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

try:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
    raise SystemExit(
        "Lattice figure generation requires Matplotlib. Install CALM's existing "
        "plot environment with: python -m pip install -e '.[plot]'"
    ) from exc

from lattice_figure_recipes import (
    FigureRecipe,
    published_recipe_map,
    recipe_map,
)

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_OUTPUT = ROOT / "docs" / "assets" / "figures" / "lattice"
DEFAULT_OUTPUT = ROOT / "build" / "documentation-figures" / "lattice"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)


def _svg_tag(name: str) -> str:
    return f"{{{SVG_NAMESPACE}}}{name}"


def render_svg(recipe: FigureRecipe) -> str:
    """Render one recipe as an accessible, vector-only SVG document."""

    with mpl.rc_context({"svg.hashsalt": "calm-lattice-figures-v1"}):
        figure = recipe.build()
        try:
            stream = BytesIO()
            figure.savefig(
                stream,
                format="svg",
                bbox_inches="tight",
                metadata={
                    "Creator": "CALM documentation lattice figure tool",
                    "Date": None,
                    "Description": recipe.description,
                    "Title": recipe.title,
                },
            )
        finally:
            plt.close(figure)

    root = ET.fromstring(stream.getvalue())
    for child in list(root):
        if child.tag in {_svg_tag("title"), _svg_tag("desc")}:
            root.remove(child)

    title = ET.Element(_svg_tag("title"), {"id": "title"})
    title.text = recipe.title
    description = ET.Element(_svg_tag("desc"), {"id": "desc"})
    description.text = recipe.description
    root.insert(0, description)
    root.insert(0, title)
    root.set("role", "img")
    root.set("aria-labelledby", "title desc")
    root.set("data-calm-lattice-figure-version", "1")
    root.set("data-calm-lattice-recipe", recipe.name)
    content = ET.tostring(root, encoding="unicode")
    return "\n".join(line.rstrip() for line in content.splitlines()) + "\n"


def validate_svg(path: Path, recipe: FigureRecipe) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing generated lattice figure: {path}"]
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
    if root.attrib.get("data-calm-lattice-recipe") != recipe.name:
        errors.append(f"{path}: recipe identifier does not match {recipe.name!r}")
    if root.find(f".//{_svg_tag('image')}") is not None:
        errors.append(f"{path}: raster image content is not permitted")

    title = root.find(_svg_tag("title"))
    description = root.find(_svg_tag("desc"))
    if title is None or (title.text or "").strip() != recipe.title:
        errors.append(f"{path}: accessible title does not match the recipe")
    if description is None or (description.text or "").strip() != recipe.description:
        errors.append(f"{path}: accessible description does not match the recipe")
    return errors


def _selected_recipes(names: Sequence[str] | None) -> tuple[FigureRecipe, ...]:
    recipes = recipe_map()
    if not names:
        return tuple(published_recipe_map().values())
    return tuple(recipes[name] for name in names)


def write_figures(
    recipes: Iterable[FigureRecipe],
    *,
    output_dir: Path = DEFAULT_OUTPUT,
) -> tuple[Path, ...]:
    """Write selected SVG recipes and return their output paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for recipe in recipes:
        path = output_dir / recipe.filename
        path.write_text(render_svg(recipe), encoding="utf-8")
        written.append(path)
    return tuple(written)


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    recipes = recipe_map()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list",
        action="store_true",
        help="list available recipe names and exit",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=tuple(recipes),
        metavar="NAME",
        help="generate or check only one named recipe; may be repeated",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="SVG output directory (defaults to the MkDocs figure tree)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate committed SVG assets without rewriting them",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name in recipes:
            print(name)
        return 0

    selected = _selected_recipes(args.only)
    output_dir = args.output_dir.resolve()
    engineering_only = [recipe.name for recipe in selected if not recipe.published]
    if engineering_only and output_dir == PUBLIC_OUTPUT.resolve():
        print(
            "engineering-only lattice recipes require --output-dir outside "
            "the public MkDocs asset tree: " + ", ".join(engineering_only),
            file=sys.stderr,
        )
        return 2
    if args.check:
        errors = [
            error
            for recipe in selected
            for error in validate_svg(output_dir / recipe.filename, recipe)
        ]
        if not args.only and output_dir.is_dir():
            expected = {recipe.filename for recipe in selected}
            actual = {path.name for path in output_dir.glob("*.svg")}
            extras = sorted(actual - expected)
            if extras:
                errors.append(
                    "unowned lattice figure assets: " + ", ".join(extras)
                )
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        noun = "figure" if len(selected) == 1 else "figures"
        print(
            f"validated {len(selected)} lattice {noun} in "
            f"{_display_path(output_dir)}"
        )
        return 0

    written = write_figures(selected, output_dir=output_dir)
    noun = "figure" if len(written) == 1 else "figures"
    print(
        f"wrote {len(written)} lattice {noun} to {_display_path(output_dir)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
