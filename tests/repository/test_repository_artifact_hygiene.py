"""Repository artifact hygiene guardrails."""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

_TRACKED_ARTIFACT_PATTERNS = (
    "site/*",
    "*.egg-info/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    ".mypy_cache/*",
    "__pycache__/*",
    "*/__pycache__/*",
    "*.py[cod]",
    "*.calm/*",
    "*.sqlite",
    "*.db",
    "examples/example_project.calm/*",
    "examples/outputs/*",
    "examples/workspace/*",
    "examples/*_interface.POSCAR",
    "examples/C*_interface.POSCAR",
    "examples/*.png",
    "examples/*.csv",
    "examples/*.cif",
)

_REQUIRED_GITIGNORE_SNIPPETS = (
    "site/",
    "/public/",
    "*.egg-info/",
    ".pytest_cache/",
    ".ruff_cache/",
    "__pycache__/",
    "examples/example_project.calm/",
    "examples/outputs/",
    "examples/workspace/",
    "*.calm/",
)


def _tracked_files() -> list[str]:
    out = subprocess.check_output(["git", "-C", str(REPO_ROOT), "ls-files", "-z"])
    return [p.decode("utf-8") for p in out.split(b"\0") if p]


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def test_generated_artifacts_are_not_tracked() -> None:
    offenders = [path for path in _tracked_files() if _matches_any(path, _TRACKED_ARTIFACT_PATTERNS)]
    assert offenders == [], "Generated artifacts should not be tracked:\n" + "\n".join(offenders)


def test_gitignore_declares_core_generated_artifacts() -> None:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [snippet for snippet in _REQUIRED_GITIGNORE_SNIPPETS if snippet not in text]
    assert missing == [], f"Missing generated-artifact patterns in .gitignore: {missing}"
