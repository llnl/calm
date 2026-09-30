"""Durable content contracts for CALM's public documentation and examples."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
README = ROOT / "README.md"
EXAMPLES_README = ROOT / "examples" / "README.md"
PUBLIC_API = ROOT / "public_api.md"

FENCE_RE = re.compile(r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)\n```", re.DOTALL)
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\((?P<target>[^)]+)\)")
SNIPPET_DIRECTIVE_RE = re.compile(
    r'^\s*--8<--\s+"(?P<path>[^"]+\.py):(?P<section>[^"]+)"\s*$',
    re.MULTILINE,
)
SECTION_MARKER_RE = re.compile(
    r"^[ \t]*# --8<-- \[(?P<kind>start|end):(?P<name>[^\]]+)\][ \t]*$"
)

ADDITIONAL_PUBLIC_MARKDOWN = (
    README,
    EXAMPLES_README,
    PUBLIC_API,
    ROOT / "environments" / "README.md",
    ROOT / "conda-recipe" / "README.md",
)
ENTRY_PAGES = (
    README,
    DOCS / "index.md",
    DOCS / "learn" / "first-interface.md",
    DOCS / "use" / "projects.md",
    EXAMPLES_README,
)
FORBIDDEN_PARALLEL_SURFACES = (
    "from calm.project",
    "from calm.interface",
    "from calm.slab",
    "from calm.bulk",
    "from calm.calculators",
    "from calm.viz",
    "import calm.project",
    "import calm.interface",
    "import calm.slab",
    "import calm.bulk",
    "import calm.calculators",
    "import calm.viz",
    "open_workspace",
    "ws.mutations",
    "ws.query",
)
FORBIDDEN_TRANSITION_LANGUAGE = (
    "alpha-to-beta",
    "alpha to beta",
    "historical mathematics remains archived until",
    "mathematical-audit program",
    "mathematical audit program",
    "beta release closure is intentionally paused",
)


def _public_markdown_files() -> tuple[Path, ...]:
    files = [*ADDITIONAL_PUBLIC_MARKDOWN, *sorted(DOCS.rglob("*.md"))]
    missing = [path.relative_to(ROOT).as_posix() for path in files if not path.is_file()]
    assert missing == [], f"Missing public documentation files: {missing}"
    return tuple(files)


def _snippet_sections(path: Path) -> dict[str, str]:
    sections: dict[str, str] = {}
    active_name: str | None = None
    active_lines: list[str] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        marker = SECTION_MARKER_RE.match(line)
        if marker is None:
            if active_name is not None:
                active_lines.append(line)
            continue

        kind = marker.group("kind")
        name = marker.group("name")
        if kind == "start":
            assert active_name is None, (
                f"Nested snippet section in {path.relative_to(ROOT)} at line "
                f"{line_number}"
            )
            assert name not in sections, (
                f"Duplicate snippet section {name!r} in {path.relative_to(ROOT)}"
            )
            active_name = name
            active_lines = []
            continue

        assert active_name == name, (
            f"Mismatched snippet end in {path.relative_to(ROOT)} at line "
            f"{line_number}: expected {active_name!r}, found {name!r}"
        )
        sections[name] = dedent("\n".join(active_lines)).strip() + "\n"
        active_name = None
        active_lines = []

    assert active_name is None, (
        f"Unclosed snippet section {active_name!r} in {path.relative_to(ROOT)}"
    )
    return sections


def _expand_snippets(body: str, cache: dict[Path, dict[str, str]]) -> str:
    def replace(match: re.Match[str]) -> str:
        source = (ROOT / match.group("path")).resolve()
        try:
            source.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise AssertionError(f"Snippet source leaves repository: {source}") from exc
        assert source.is_file(), f"Missing snippet source: {source}"
        sections = cache.setdefault(source, _snippet_sections(source))
        name = match.group("section")
        assert name in sections, (
            f"Missing snippet section {name!r} in {source.relative_to(ROOT)}"
        )
        return sections[name].rstrip("\n")

    return SNIPPET_DIRECTIVE_RE.sub(replace, body)


def test_public_markdown_is_clean_and_free_of_closed_campaign_language() -> None:
    offenders: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for offset, character in enumerate(text):
            codepoint = ord(character)
            if codepoint >= 32 or character in {"\n", "\r"}:
                continue
            line = text.count("\n", 0, offset) + 1
            offenders.append(
                f"{path.relative_to(ROOT)}:{line} contains U+{codepoint:04X}"
            )
        for phrase in FORBIDDEN_TRANSITION_LANGUAGE:
            if phrase in lower:
                offenders.append(f"{path.relative_to(ROOT)} retains {phrase!r}")
    assert offenders == [], "\n".join(offenders)


def test_user_documentation_avoids_internal_identity_and_storage_language() -> None:
    forbidden = (
        "authoritative user-facing",
        "public contract",
        "project record",
        "workflow record",
        "internal workspace state",
        "project internals",
    )
    offenders: list[str] = []
    for path in sorted(DOCS.rglob("*.md")):
        lower = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            if phrase in lower:
                offenders.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert offenders == [], "\n".join(offenders)


def test_public_python_fences_and_local_snippets_compile() -> None:
    cache: dict[Path, dict[str, str]] = {}
    errors: list[str] = []
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        for index, match in enumerate(FENCE_RE.finditer(text), start=1):
            language = (match.group("lang") or "").strip().lower()
            if language not in {"python", "py", "python3"}:
                continue
            try:
                body = _expand_snippets(match.group("body") or "", cache)
                ast.parse(body, filename=f"{path}:fence-{index}")
            except (AssertionError, SyntaxError) as exc:
                errors.append(
                    f"{path.relative_to(ROOT)} Python fence {index}: "
                    f"{type(exc).__name__}: {exc}"
                )
    assert errors == [], "\n".join(errors)


def test_public_examples_do_not_import_private_calm_modules() -> None:
    offenders: list[str] = []
    cache: dict[Path, dict[str, str]] = {}
    for path in _public_markdown_files():
        text = path.read_text(encoding="utf-8")
        for index, match in enumerate(FENCE_RE.finditer(text), start=1):
            language = (match.group("lang") or "").strip().lower()
            if language not in {"python", "py", "python3"}:
                continue
            body = _expand_snippets(match.group("body") or "", cache)
            tree = ast.parse(body, filename=f"{path}:fence-{index}")
            for node in ast.walk(tree):
                modules: list[str] = []
                if isinstance(node, ast.Import):
                    modules.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.append(node.module)
                for module in modules:
                    if module.startswith("calm._") or ".application" in module or ".infrastructure" in module:
                        offenders.append(
                            f"{path.relative_to(ROOT)} fence {index} imports {module}"
                        )
    assert offenders == [], "\n".join(offenders)


def test_entry_pages_use_the_single_project_api_without_overclaiming() -> None:
    offenders: list[str] = []
    for path in ENTRY_PAGES:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_PARALLEL_SURFACES:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)} teaches {token!r}")
    assert offenders == [], "\n".join(offenders)

    readme = README.read_text(encoding="utf-8")
    lower = readme.lower()
    assert "calm.open_project" in readme
    assert "single public api" in lower
    assert "qualification reports" in lower
    assert "synchronous" in lower
    assert "scientific-analysis" in lower
    for phrase in (
        "release candidate",
        "production-ready",
        "complete computational workflow",
        "llnl-code-[tbd]",
    ):
        assert phrase not in lower


def test_public_api_entrypoint_guidance_is_unambiguous() -> None:
    text = PUBLIC_API.read_text(encoding="utf-8")
    lower = " ".join(text.lower().split())
    assert "one project-centered public api" in lower
    assert "supported imports originate from `calm`" in lower
    assert "calm.project.open_workspace" not in text
    assert "beginner api" not in lower
    assert "basic api" not in lower
    assert "advanced api" not in lower

def test_non_docs_public_markdown_local_links_resolve() -> None:
    errors: list[str] = []
    for path in ADDITIONAL_PUBLIC_MARKDOWN:
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw = match.group("target").strip()
            if not raw or raw.startswith(("#", "http://", "https://", "mailto:", "tel:")):
                continue
            target_text = raw.split("#", 1)[0].split("?", 1)[0]
            if not target_text:
                continue
            target = (path.parent / target_text).resolve()
            if not target.exists():
                errors.append(
                    f"{path.relative_to(ROOT)} links to missing local target {raw!r}"
                )
    assert errors == [], "\n".join(errors)
