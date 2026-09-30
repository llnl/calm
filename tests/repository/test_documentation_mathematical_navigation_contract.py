"""Navigation and rendering contracts for greenfield scientific explanations."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_understand_navigation_is_ordered_by_user_interpretation() -> None:
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    ordered = (
        "understand/surface-models.md",
        "understand/surface-supercells.md",
        "understand/coherent-matching.md",
        "understand/strain-registry.md",
        "understand/energetics.md",
    )
    positions = [text.index(path) for path in ordered]
    assert positions == sorted(positions)


def test_understand_page_anatomy_starts_with_the_scientific_question() -> None:
    anatomy = _contract()["page_anatomy"]["understand"]
    assert anatomy[0] == "Scientific question"
    assert anatomy == [
        "Scientific question",
        "Physical interpretation",
        "Definition",
        "How CALM uses it",
        "What the user controls",
        "Assumptions and limitations",
        "Related workflow",
        "References",
    ]


def test_math_rendering_support_remains_available() -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "pymdownx.arithmatex" in mkdocs
    assert "javascripts/mathjax.js" in mkdocs
    assert (DOCS / "javascripts" / "mathjax.js").is_file()


def test_implementation_math_trees_are_not_reintroduced() -> None:
    for path in (
        DOCS / "mathematics",
        DOCS / "scientific-background",
        DOCS / "concepts",
    ):
        assert not any(path.rglob("*.md"))
    for page in DOCS.rglob("*.md"):
        text = page.read_text(encoding="utf-8").lower()
        for phrase in (
            "exact hnf orbit",
            "canonical pair identity",
            "integer certificate",
            "canonical payload",
        ):
            assert phrase not in text
