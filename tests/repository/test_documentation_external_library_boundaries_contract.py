"""Boundary contracts for external-library and archived documentation notes."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ARCHIVE = ROOT / "archive" / "documentation-notes"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"


def test_detailed_adapter_notes_remain_outside_mkdocs_and_engineering() -> None:
    assert (ARCHIVE / "external-library-boundaries.md").is_file()
    assert not (DOCS / "reference" / "external-library-boundaries.md").exists()
    assert not any((ROOT / "engineering").rglob("*.md"))


def test_public_pages_do_not_link_to_archived_or_engineering_notes() -> None:
    offenders: list[str] = []
    for page in DOCS.rglob("*.md"):
        text = page.read_text(encoding="utf-8")
        for marker in ("archive/", "engineering/"):
            if marker in text:
                offenders.append(f"{page.relative_to(ROOT)}: {marker}")
    assert offenders == []


def test_external_library_user_conventions_have_a_public_owner() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    requirements = contract["content_requirements"]["terminology_and_notation"]
    assert "reference/units-conventions.md" in requirements["owners"]
    page = DOCS / "reference" / "units-conventions.md"
    assert page.is_file()
    assert "basis-vector convention" in page.read_text(encoding="utf-8")


def test_archive_readme_marks_notes_as_provenance_only() -> None:
    text = (ARCHIVE / "README.md").read_text(encoding="utf-8")
    assert "retains implementation and qualification notes for provenance" in text
    assert "excluded from both the public MkDocs site" in text
    assert "not live maintainer instructions" in text
