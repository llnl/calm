"""Integrity contracts for the greenfield documentation skeleton."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
CONTRACT = ROOT / "engineering" / "architecture" / "current-documentation-site.json"

sys.path.insert(0, str(ROOT / "engineering" / "documentation"))
import api_reference_manifest as api_reference  # noqa: E402

GENERATED_PAGES = {
    (DOCS / relative).resolve(): content
    for relative, content in api_reference.rendered_pages().items()
}
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\((?P<target>[^)]+)\)")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _heading_slug(heading: str) -> str:
    normalized = re.sub(r"<[^>]+>", "", heading)
    normalized = re.sub(r"[^\w\- ]", "", normalized.lower()).strip()
    return re.sub(r"[-\s]+", "-", normalized)


def test_all_local_markdown_links_and_heading_fragments_resolve() -> None:
    errors: list[str] = []
    for page in sorted(DOCS.rglob("*.md")):
        for match in MARKDOWN_LINK_RE.finditer(_text(page)):
            target_text = match.group("target").strip()
            if target_text.startswith(("#", "http://", "https://", "mailto:", "tel:")):
                continue
            relative, separator, fragment = target_text.partition("#")
            relative = relative.split("?", maxsplit=1)[0]
            target = page if not relative else (page.parent / relative).resolve()
            try:
                target.relative_to(DOCS.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(ROOT)} -> {target_text} leaves docs tree")
                continue
            if target.is_file():
                resolved_text = _text(target)
            elif target in GENERATED_PAGES:
                resolved_text = GENERATED_PAGES[target]
            else:
                errors.append(f"{page.relative_to(ROOT)} -> {target_text} missing")
                continue
            if separator:
                headings = {
                    _heading_slug(line.lstrip("#").strip())
                    for line in resolved_text.splitlines()
                    if line.startswith("#")
                }
                if fragment not in headings:
                    errors.append(f"{page.relative_to(ROOT)} -> {target_text} missing anchor")
    assert errors == [], "\n".join(errors)


def test_committed_documentation_pages_have_one_unique_h1() -> None:
    owners: defaultdict[str, list[Path]] = defaultdict(list)
    errors: list[str] = []
    for page in sorted(DOCS.rglob("*.md")):
        h1 = [line[2:].strip() for line in _text(page).splitlines() if line.startswith("# ")]
        if len(h1) != 1:
            errors.append(f"{page.relative_to(ROOT)} has {len(h1)} H1 headings")
            continue
        owners[h1[0].casefold()].append(page)
    duplicates = {
        title: [str(path.relative_to(ROOT)) for path in paths]
        for title, paths in owners.items()
        if len(paths) > 1
    }
    assert errors == [], "\n".join(errors)
    assert duplicates == {}, f"Duplicate public page titles: {duplicates}"


def test_generated_api_pages_are_renderable_and_link_to_greenfield_workflows() -> None:
    assert {path.relative_to(DOCS).as_posix() for path in GENERATED_PAGES} == {
        "reference/api/project.md",
        "reference/api/inputs-settings.md",
        "reference/api/returned-objects.md",
        "reference/api/exceptions-utilities.md",
    }
    project = GENERATED_PAGES[(DOCS / "reference/api/project.md").resolve()]
    for target in (
        "../../use/projects.md",
        "../../use/materials.md",
        "../../use/searches.md",
        "../../use/relax-evaluate.md",
        "../../use/datasets-campaigns.md",
    ):
        assert target in project
    for legacy in ("user-guide/", "scientific-background/", "how-to/"):
        assert legacy not in project


def test_public_figures_have_one_explicit_authored_owner() -> None:
    figure_root = DOCS / "assets" / "figures"
    expected = {
        "site/calm-workflow-map.svg": "index.md",
        "tutorials/first-interface-workflow.svg": "learn/first-interface.md",
        "tutorials/candidate-selection.svg": "learn/compare-candidates.md",
        "tutorials/refine-relax-evaluate.svg": "learn/refine-relax-evaluate.md",
        "understand/surface-construction-workflow.svg": "understand/surface-models.md",
        "understand/cell-map-types.svg": "understand/surface-supercells.md",
        "understand/coupled-common-cell.svg": "understand/coherent-matching.md",
        "understand/coherent-misfit-principal-strain.svg": "understand/coherent-matching.md",
        "understand/pareto-strain-size.svg": "understand/coherent-matching.md",
        "understand/strain-partition-path.svg": "understand/strain-registry.md",
        "understand/registry-translation-torus.svg": "understand/strain-registry.md",
        "understand/interface-energy-reference-cycles.svg": "understand/energetics.md",
    }
    actual = {
        path.relative_to(figure_root).as_posix()
        for path in figure_root.rglob("*.svg")
    }
    assert actual == set(expected)

    references: dict[str, list[str]] = defaultdict(list)
    for page in DOCS.rglob("*.md"):
        relative = page.relative_to(DOCS).as_posix()
        text = _text(page)
        for figure in expected:
            if figure in text:
                references[figure].append(relative)
        if relative not in {"index.md"} and not relative.startswith(("learn/", "understand/")):
            assert "<figure" not in text
            assert "assets/figures" not in text

    assert references == {figure: [owner] for figure, owner in expected.items()}
    for owner in sorted(set(expected.values())):
        text = _text(DOCS / owner)
        assert text.count("<figure") >= 1
        assert "<figure" in text and " markdown>" in text
        assert "![" in text
        assert "<figcaption>" in text


def test_figure_urls_use_mkdocs_rewritten_markdown_links() -> None:
    errors: list[str] = []
    for page in sorted(DOCS.rglob("*.md")):
        text = _text(page)
        for match in re.finditer(r'<(?:img|a)\b[^>]+(?:src|href)="(?P<target>[^"]+)"', text):
            target = match.group("target")
            if target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue
            if "assets/figures/" in target:
                errors.append(
                    f"{page.relative_to(ROOT)} uses raw HTML for {target}; "
                    "MkDocs does not rewrite raw HTML asset URLs"
                )
        if "assets/figures/" in text:
            assert "<figure" in text
            assert " markdown>" in text

    assert errors == [], "\n".join(errors)


def test_legacy_figure_generators_default_to_the_ignored_build_tree() -> None:
    sys.path.insert(0, str(ROOT / "engineering" / "documentation" / "figures"))
    import generate_lattice_figures as lattice  # noqa: E402
    import generate_scientific_figures as scientific  # noqa: E402

    build_root = (ROOT / "build" / "documentation-figures").resolve()
    assert lattice.DEFAULT_OUTPUT.resolve().is_relative_to(build_root)
    assert scientific.OUT.resolve().is_relative_to(build_root)
    assert not lattice.DEFAULT_OUTPUT.resolve().is_relative_to(DOCS.resolve())
    assert not scientific.OUT.resolve().is_relative_to(DOCS.resolve())


def test_mkdocs_contains_only_greenfield_user_pages_and_generated_reference() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = []

    def collect(rows: list[dict[str, object]]) -> None:
        for row in rows:
            if row.get("children"):
                collect(row["children"])
            else:
                entries.append(row)

    collect(contract["navigation"])
    expected = {row["path"] for row in entries}
    nav = _text(ROOT / "mkdocs.yml")
    actual = set(re.findall(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./-]+\.md)", nav))
    assert actual == expected

    forbidden_visible_markers = (
        "engineering/",
        "archive/",
        "current-public-contract",
        "database schema",
        "serializer",
        "migration strategy",
        "qualification tests",
        "Internal namespaces",
        "Retired duplicate entry points",
    )
    visible = {
        **{page.relative_to(DOCS).as_posix(): _text(page) for page in DOCS.rglob("*.md")},
        **{path.relative_to(DOCS).as_posix(): content for path, content in GENERATED_PAGES.items()},
    }
    leaks = [
        f"{relative}: {marker}"
        for relative, text in visible.items()
        for marker in forbidden_visible_markers
        if marker in text
    ]
    assert leaks == [], "\n".join(leaks)
