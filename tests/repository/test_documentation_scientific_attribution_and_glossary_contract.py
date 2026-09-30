"""Ownership contracts for greenfield scientific and reference content."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_understand_section_has_five_canonical_scientific_chapters() -> None:
    expected = {
        "surface-models.md",
        "surface-supercells.md",
        "coherent-matching.md",
        "strain-registry.md",
        "energetics.md",
    }
    assert {path.name for path in (DOCS / "understand").glob("*.md")} == expected
    assert not any((DOCS / "scientific-background").rglob("*.md"))
    assert not any((DOCS / "mathematics").rglob("*.md"))


def test_terminology_and_conventions_have_separate_compact_owners() -> None:
    requirements = _contract()["content_requirements"]["terminology_and_notation"]
    assert requirements["owners"] == [
        "reference/terminology.md",
        "reference/units-conventions.md",
    ]
    assert set(requirements["must_define"]) == {
        "basis vectors as columns",
        "periodic directions",
        "strain convention",
        "names and identifiers",
    }
    assert (DOCS / "reference" / "terminology.md").is_file()
    assert (DOCS / "reference" / "units-conventions.md").is_file()


def test_scientific_pages_are_implemented_in_g5() -> None:
    entries: list[dict[str, object]] = []

    def collect(rows: list[dict[str, object]]) -> None:
        for row in rows:
            if row.get("children"):
                collect(row["children"])
            else:
                entries.append(row)

    collect(_contract()["navigation"])
    scientific = [row for row in entries if str(row["path"]).startswith("understand/")]
    assert len(scientific) == 5
    assert {row["phase"] for row in scientific} == {"G5"}
    for row in scientific:
        text = (DOCS / row["path"]).read_text(encoding="utf-8")
        assert row.get("implemented") is True
        assert "Greenfield reconstruction:" not in text
        assert "## References" in text
        assert "doi.org/" in text


def test_archived_notes_are_not_public_scientific_sources() -> None:
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in DOCS.rglob("*.md"))
    assert "archive/documentation-notes" not in public_text
    assert "engineering/documentation" not in public_text
