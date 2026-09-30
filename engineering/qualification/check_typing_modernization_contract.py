#!/usr/bin/env python3
"""Verify the focused Ruff typing-modernization ownership inputs."""

from __future__ import annotations

import json
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]
RESPONSE_FILE = (
    REPO_ROOT / "engineering" / "qualification" / "typing-modernization-files.txt"
)
RUFF_CONFIG = (
    REPO_ROOT / "engineering" / "qualification" / "ruff-typing-modernization.toml"
)
PYPROJECT = REPO_ROOT / "pyproject.toml"
PACKAGE_CONTRACT = (
    REPO_ROOT / "engineering" / "architecture" / "current-package-ownership.json"
)

_QUOTED_CALM_PATH = re.compile(r'^\s*"(?P<path>calm/[^"*?]+\.py)"\s*=')


def _entries() -> list[str]:
    return [
        line.strip()
        for line in RESPONSE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _module_name(relative: str) -> str:
    return ".".join(Path(relative).with_suffix("").parts)


def _load_package_contract() -> dict[str, object]:
    payload = json.loads(PACKAGE_CONTRACT.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "calm.package_ownership.v2":
        raise ValueError("Unsupported package-ownership contract schema")
    return payload


def verify() -> dict[str, object]:
    entries = _entries()
    errors: list[str] = []

    try:
        response_name = str(RESPONSE_FILE.relative_to(REPO_ROOT))
    except ValueError:
        response_name = RESPONSE_FILE.name
    if not entries:
        errors.append(f"{response_name} is empty")
    if entries != sorted(entries):
        errors.append(f"{response_name} must be sorted")
    duplicates = sorted({entry for entry in entries if entries.count(entry) > 1})
    if duplicates:
        errors.append("duplicate response-file entries: " + ", ".join(duplicates))

    contract = _load_package_contract()
    retirement = contract["retirement"]
    if not isinstance(retirement, dict):
        raise TypeError("retirement contract must be a mapping")
    retired_files = {str(value) for value in retirement["retired_files"]}
    retired_trees = tuple(
        str(value) for value in retirement["retired_source_trees"]
    )
    retired_imports = tuple(
        sorted(
            {str(value) for value in retirement["retired_modules"]}
            | {
                str(value)
                for value in retirement[
                    "additional_prohibited_import_prefixes"
                ]
            }
        )
    )

    for entry in entries:
        relative = Path(entry)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"response-file entry is not repository-relative: {entry}")
            continue
        if not entry.startswith("calm/") or relative.suffix != ".py":
            errors.append(f"response-file entry is not a CALM Python source: {entry}")
        if not (REPO_ROOT / relative).is_file():
            errors.append(f"response-file entry does not exist: {entry}")
        if entry in retired_files or any(
            entry == prefix or entry.startswith(f"{prefix}/")
            for prefix in retired_trees
        ):
            errors.append(f"response-file entry uses a retired source path: {entry}")
        module = _module_name(entry)
        if any(
            module == prefix or module.startswith(f"{prefix}.")
            for prefix in retired_imports
        ):
            errors.append(f"response-file entry uses a retired import path: {entry}")

    config_paths = [
        match.group("path")
        for line in RUFF_CONFIG.read_text(encoding="utf-8").splitlines()
        if (match := _QUOTED_CALM_PATH.match(line)) is not None
    ]
    for path in config_paths:
        if not (REPO_ROOT / path).is_file():
            errors.append(f"Ruff per-file ignore targets a missing source: {path}")
        if path not in entries:
            errors.append(f"Ruff per-file ignore is outside the response file: {path}")

    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    for retired in retired_trees:
        if retired in pyproject_text:
            errors.append(f"pyproject.toml references retired source path: {retired}")

    if errors:
        raise AssertionError(
            "Typing-modernization contract violations:\n" + "\n".join(errors)
        )

    return {
        "schema": "calm.typing_modernization_contract_check/v1",
        "response_file": str(RESPONSE_FILE.relative_to(REPO_ROOT)),
        "source_count": len(entries),
        "per_file_ignore_count": len(config_paths),
        "errors": [],
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
