"""Repository guardrails for packaging and public installation prose."""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from calm.calculators.registry import default_registry


REPO_ROOT = Path(__file__).resolve().parents[2]
EXTRA_REF_RE = re.compile(r"calm\[([^\]]+)\]")
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".rst", ".txt"}
PUBLIC_TEXT_ROOTS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "examples" / "README.md",
    REPO_ROOT / "environments",
    REPO_ROOT / "calm",
)
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "site",
    "calm.egg-info",
}
DEFERRED_FRAMEWORKS = {"m3gnet", "matgl", "sevennet", "nequip", "mattersim", "orb"}


def _pyproject_extras() -> set[str]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return set(data.get("project", {}).get("optional-dependencies", {}))


def _iter_public_text_files() -> list[Path]:
    paths: list[Path] = []
    for root in PUBLIC_TEXT_ROOTS:
        assert root.exists(), f"Missing public packaging/prose surface: {root}"
        if root.is_file():
            paths.append(root)
            continue
        for path in root.rglob("*"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                paths.append(path)
    return sorted(paths)


def _documented_extra_refs() -> dict[str, list[Path]]:
    refs: dict[str, list[Path]] = {}
    for path in _iter_public_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in EXTRA_REF_RE.finditer(text):
            extra = match.group(1).strip()
            if "{" in extra or "}" in extra or extra == "...":
                continue
            refs.setdefault(extra, []).append(path.relative_to(REPO_ROOT))
    return refs


def test_all_documented_pip_extras_exist_in_pyproject() -> None:
    extras = _pyproject_extras()
    refs = _documented_extra_refs()
    missing = {
        extra: sorted(str(path) for path in paths)
        for extra, paths in refs.items()
        if extra not in extras
    }
    assert missing == {}, (
        "Found documented `calm[...]` extras that are not declared in pyproject.toml: "
        f"{missing}"
    )


def test_registered_calculator_families_are_listed_in_readme() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    missing = [family for family in default_registry().families() if family.lower() not in text]
    assert missing == [], f"README.md omits registered calculator families: {missing}"


def test_unregistered_frameworks_have_no_calm_environment_recipes() -> None:
    registered = set(default_registry().families())
    assert registered.isdisjoint(DEFERRED_FRAMEWORKS)

    guide = (REPO_ROOT / "environments" / "README.md").read_text(
        encoding="utf-8"
    ).lower()
    for framework in DEFERRED_FRAMEWORKS:
        assert framework in guide
        assert not (
            REPO_ROOT / "environments" / f"calm-{framework}.yml"
        ).exists()
    assert "does not" in guide
    assert "maintain source environment recipes" in guide


def test_environment_guide_lists_registered_and_unregistered_families() -> None:
    text = (REPO_ROOT / "environments" / "README.md").read_text(
        encoding="utf-8"
    ).lower()
    missing_registered = sorted(
        family for family in default_registry().families() if family not in text
    )
    missing_unregistered = sorted(
        name for name in DEFERRED_FRAMEWORKS if name not in text
    )

    assert missing_registered == []
    assert missing_unregistered == []
    assert "not registered" in text
    assert "one primary provider" in text


def test_environment_guide_does_not_teach_unregistered_spec_values() -> None:
    forbidden = tuple(
        token
        for family in DEFERRED_FRAMEWORKS
        for token in (f'family="{family}"', f"family='{family}'")
    )
    text = (REPO_ROOT / "environments" / "README.md").read_text(
        encoding="utf-8"
    ).lower()
    found = [token for token in forbidden if token in text]

    assert found == []


def test_greenfield_contract_requires_calculator_reference_to_track_registry() -> None:
    documentation = json.loads(
        (REPO_ROOT / "engineering" / "architecture" / "current-documentation-site.json").read_text(
            encoding="utf-8"
        )
    )
    requirement = documentation["content_requirements"]["calculator_registry"]
    assert requirement == {
        "owner": "reference/calculator-support.md",
        "source": "calm.calculators.registry.default_registry()",
        "must_track_all_registered_families": True,
    }
    assert set(default_registry().families()) == {"ase", "chgnet", "grace", "lammps", "mace"}
