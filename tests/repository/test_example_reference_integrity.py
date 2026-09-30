from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
PUBLIC_PROSE = (ROOT / "README.md", EXAMPLES / "README.md")
EXAMPLE_PATH_RE = re.compile(r"(?P<path>(?:\.\.?/)*examples/[A-Za-z0-9_.\-/]+\.py)")
INVENTORY_ENTRY_RE = re.compile(r"`(?P<name>[0-9]{2}_[A-Za-z0-9_.-]+\.py)`")


def _required_public_prose() -> tuple[Path, ...]:
    missing = [path.relative_to(ROOT).as_posix() for path in PUBLIC_PROSE if not path.is_file()]
    assert missing == [], f"Missing public prose files: {missing}"
    return PUBLIC_PROSE


def _normalize_example_reference(raw: str) -> Path:
    suffix = raw.split("examples/", 1)[1]
    return EXAMPLES / suffix


def test_public_prose_example_script_references_exist() -> None:
    offenders: list[str] = []

    for path in _required_public_prose():
        text = path.read_text(encoding="utf-8")
        for match in EXAMPLE_PATH_RE.finditer(text):
            raw = match.group("path")
            candidate = _normalize_example_reference(raw)
            if not candidate.is_file():
                offenders.append(
                    f"{path.relative_to(ROOT)} references missing example {raw!r}"
                )

    assert offenders == [], "\n".join(offenders)


def test_examples_readme_inventory_matches_numbered_scripts() -> None:
    readme = EXAMPLES / "README.md"
    text = readme.read_text(encoding="utf-8")

    shipped = {path.name for path in EXAMPLES.glob("[0-9][0-9]_*.py")}
    documented = set(INVENTORY_ENTRY_RE.findall(text))

    assert shipped, "Expected numbered example scripts under examples/"
    assert documented == shipped, (
        "examples/README.md inventory drifted from shipped numbered scripts.\n"
        f"Missing from README: {sorted(shipped - documented)}\n"
        f"Stale README entries: {sorted(documented - shipped)}"
    )
