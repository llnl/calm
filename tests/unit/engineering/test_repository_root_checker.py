"""Dependency-light mutation tests for repository-root ownership."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from engineering.qualification.check_repository_root import validate


def _write_contract(path: Path) -> Path:
    contract = path
    contract.write_text(
        json.dumps(
            {
                "schema_version": "calm.repository_root_ownership.v1",
                "owned_files": {
                    ".gitignore": "ignore policy",
                    "README.md": "landing page",
                },
                "owned_directories": {
                    "calm": "package",
                },
                "forbidden_root_ignore_suffixes": [".md", ".py"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return contract


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (root / "README.md").write_text("# Example\n", encoding="utf-8")
    (root / "calm").mkdir()
    (root / "calm" / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(root), "add", ".gitignore", "README.md", "calm"],
        check=True,
    )
    return root, _write_contract(tmp_path / "contract.json")


def test_checker_rejects_an_unowned_root_file(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    (root / "debug.py").write_text("", encoding="utf-8")
    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == ["unowned root files in the effective tree: debug.py"]


def test_checker_rejects_an_unowned_root_directory(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    (root / "scratch").mkdir()
    (root / "scratch" / "notes.txt").write_text("temporary\n", encoding="utf-8")

    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == [
        "unowned root directories in the effective tree: scratch"
    ]


def test_checker_rejects_hidden_root_source_patterns(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    (root / ".gitignore").write_text("__pycache__/\n/debug_*.py\n", encoding="utf-8")

    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == [
        ".gitignore must not hide root-level source or documentation files: "
        "/debug_*.py"
    ]


def test_checker_rejects_recursive_patterns_that_hide_root_sources(
    tmp_path: Path,
) -> None:
    root, contract = _repository(tmp_path)
    (root / ".gitignore").write_text("__pycache__/\n**/*.py\n", encoding="utf-8")

    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == [
        ".gitignore must not hide root-level source or documentation files: "
        "**/*.py"
    ]


def test_checker_rejects_hidden_root_document_patterns(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    (root / ".gitignore").write_text("__pycache__/\n/ACTION_*.md\n", encoding="utf-8")

    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == [
        ".gitignore must not hide root-level source or documentation files: "
        "/ACTION_*.md"
    ]


def test_checker_rejects_global_root_document_patterns(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    (root / ".gitignore").write_text("__pycache__/\n*.md\n", encoding="utf-8")

    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == [
        ".gitignore must not hide root-level source or documentation files: *.md"
    ]


def test_checker_ignores_generated_root_directories(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    (root / "build").mkdir()
    (root / "build" / "artifact.txt").write_text("generated\n", encoding="utf-8")

    result = validate(repo_root=root, contract_path=contract)

    assert result["errors"] == []
