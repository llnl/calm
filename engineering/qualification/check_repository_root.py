#!/usr/bin/env python3
"""Validate the exact CALM repository-root ownership contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "engineering" / "architecture" / "current-repository-root.json"
_SCHEMA_VERSION = "calm.repository_root_ownership.v1"
_CONTRACT_KEYS = frozenset(
    {
        "schema_version",
        "owned_files",
        "owned_directories",
        "forbidden_root_ignore_suffixes",
    }
)


def _string_mapping(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
) -> dict[str, str]:
    value = payload.get(name)
    if not isinstance(value, dict):
        errors.append(f"{name} must be a JSON object")
        return {}
    result: dict[str, str] = {}
    for key, role in value.items():
        if not isinstance(key, str) or not key:
            errors.append(f"{name} keys must be nonempty strings")
            continue
        if (
            PurePosixPath(key).name != key
            or "/" in key
            or "\\" in key
            or key in {".", ".."}
        ):
            errors.append(
                f"{name} key must be one repository-root entry: {key!r}"
            )
            continue
        if not isinstance(role, str) or not role.strip():
            errors.append(f"{name}[{key!r}] must have a nonempty role")
            continue
        result[key] = role
    if list(value) != sorted(value):
        errors.append(f"{name} keys must be sorted")
    return result


def _string_list(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
) -> list[str]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"{name} must be a list of nonempty strings")
        return []
    if value != sorted(value):
        errors.append(f"{name} must be sorted")
    if len(value) != len(set(value)):
        errors.append(f"{name} must not contain duplicates")
    return list(value)


def _effective_root_entries(repo_root: Path) -> tuple[set[str], set[str]]:
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    files: set[str] = set()
    directories: set[str] = set()
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative_text = raw.decode("utf-8")
        if not (repo_root / relative_text).exists():
            continue
        relative = PurePosixPath(relative_text)
        if len(relative.parts) == 1:
            files.add(relative.name)
        else:
            directories.add(relative.parts[0])
    return files, directories


def validate(
    *,
    repo_root: Path = REPO_ROOT,
    contract_path: Path | None = None,
) -> dict[str, object]:
    root = repo_root.resolve()
    path = (
        contract_path.resolve()
        if contract_path is not None
        else root / "engineering" / "architecture" / "current-repository-root.json"
    )
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": _SCHEMA_VERSION,
            "errors": [f"unable to read repository-root contract: {exc}"],
        }
    if not isinstance(payload, dict):
        return {
            "schema": _SCHEMA_VERSION,
            "errors": ["repository-root contract must be a JSON object"],
        }

    observed_keys = set(payload)
    if observed_keys != _CONTRACT_KEYS:
        errors.append(
            "repository-root contract keys must be exactly "
            f"{sorted(_CONTRACT_KEYS)}, observed {sorted(observed_keys)}"
        )
    if payload.get("schema_version") != _SCHEMA_VERSION:
        errors.append(f"schema_version must be {_SCHEMA_VERSION!r}")

    expected_files = _string_mapping(payload, "owned_files", errors)
    expected_directories = _string_mapping(payload, "owned_directories", errors)
    forbidden_suffixes = _string_list(
        payload, "forbidden_root_ignore_suffixes", errors
    )
    for suffix in forbidden_suffixes:
        if not suffix.startswith(".") or "/" in suffix or "*" in suffix:
            errors.append(
                "forbidden_root_ignore_suffixes entries must be simple file "
                f"suffixes: {suffix!r}"
            )
    overlap = sorted(set(expected_files) & set(expected_directories))
    if overlap:
        errors.append(
            "owned_files and owned_directories must be disjoint: "
            + ", ".join(overlap)
        )

    for name in expected_files:
        if not (root / name).is_file():
            errors.append(f"declared root file is missing or not a file: {name}")
    for name in expected_directories:
        if not (root / name).is_dir():
            errors.append(f"declared root directory is missing: {name}")

    try:
        observed_files, observed_directories = _effective_root_entries(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"unable to inspect effective repository paths: {exc}")
        observed_files, observed_directories = set(), set()

    missing_files = sorted(set(expected_files) - observed_files)
    extra_files = sorted(observed_files - set(expected_files))
    missing_directories = sorted(set(expected_directories) - observed_directories)
    extra_directories = sorted(observed_directories - set(expected_directories))
    if missing_files:
        errors.append(
            "declared root files are absent from the effective tree: "
            + ", ".join(missing_files)
        )
    if extra_files:
        errors.append(
            "unowned root files in the effective tree: "
            + ", ".join(extra_files)
        )
    if missing_directories:
        errors.append(
            "declared root directories are absent from the effective tree: "
            + ", ".join(missing_directories)
        )
    if extra_directories:
        errors.append(
            "unowned root directories in the effective tree: "
            + ", ".join(extra_directories)
        )

    gitignore_path = root / ".gitignore"
    if gitignore_path.is_file():
        hidden_source_patterns: list[str] = []
        for raw_line in gitignore_path.read_text(encoding="utf-8").splitlines():
            pattern = raw_line.strip()
            if not pattern or pattern.startswith(("#", "!")):
                continue
            root_pattern = pattern.removeprefix("/").rstrip("/")
            while root_pattern.startswith("**/"):
                root_pattern = root_pattern[3:]
            if "/" in root_pattern:
                continue
            if any(
                root_pattern.lower().endswith(suffix.lower())
                for suffix in forbidden_suffixes
            ):
                hidden_source_patterns.append(pattern)
        if hidden_source_patterns:
            errors.append(
                ".gitignore must not hide root-level source or documentation files: "
                + ", ".join(sorted(hidden_source_patterns))
            )

    return {
        "schema": _SCHEMA_VERSION,
        "effective_root_files": sorted(observed_files),
        "effective_root_directories": sorted(observed_directories),
        "forbidden_root_ignore_suffixes": forbidden_suffixes,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-current",
        action="store_true",
        help="print the validated root projection even when it is valid",
    )
    args = parser.parse_args(argv)
    result = validate()
    if args.show_current or result["errors"]:
        print(json.dumps(result, indent=2, sort_keys=True))
    if result["errors"]:
        print("CALM repository-root ownership is inconsistent.")
        return 1
    print(
        "CALM repository-root ownership is consistent: "
        f"{len(result['effective_root_files'])} files and "
        f"{len(result['effective_root_directories'])} directories."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
