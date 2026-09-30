"""Repository contracts for the exact tracked root ownership boundary."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-repository-root.json"
CHECKER = ROOT / "engineering" / "qualification" / "check_repository_root.py"


def test_repository_root_checker_accepts_the_current_tree() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECKER), "--show-current"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload_text, summary = completed.stdout.rsplit("\n", 2)[0:2]
    payload = json.loads(payload_text)
    assert payload["errors"] == []
    assert payload["schema"] == "calm.repository_root_ownership.v1"
    assert payload["effective_root_files"] == [
        ".gitignore",
        ".gitlab-ci.yml",
        "LICENSE",
        "MANIFEST.in",
        "NOTICE",
        "README.md",
        "mkdocs.yml",
        "public_api.md",
        "pyproject.toml",
        "pytest.ini",
    ]
    assert payload["effective_root_directories"] == [
        ".github",
        "archive",
        "benchmarks",
        "calm",
        "conda-recipe",
        "docs",
        "engineering",
        "environments",
        "examples",
        "tests",
    ]
    assert summary.startswith("CALM repository-root ownership is consistent:")


def test_repository_root_contract_roles_are_nonempty_and_sorted() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "calm.repository_root_ownership.v1"
    for key in ("owned_files", "owned_directories"):
        values = payload[key]
        assert list(values) == sorted(values)
        assert all(role.strip() for role in values.values())


def test_gitignore_does_not_hide_root_sources_or_documents() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["forbidden_root_ignore_suffixes"] == [".md", ".py"]
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    root_patterns = [
        line.strip()
        for line in gitignore
        if line.strip().startswith("/")
        and "/" not in line.strip()[1:].rstrip("/")
    ]
    assert not any(
        pattern.lower().endswith((".md", ".py"))
        for pattern in root_patterns
    )
