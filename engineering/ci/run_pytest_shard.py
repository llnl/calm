#!/usr/bin/env python3
"""Run one deterministic, file-level shard of the CALM pytest suite."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = REPO_ROOT / "tests"


def discover_test_files(test_root: Path = TEST_ROOT) -> list[Path]:
    """Return repository-relative test files in stable lexical order."""

    return sorted(
        path.relative_to(REPO_ROOT)
        for path in test_root.rglob("test_*.py")
        if "__pycache__" not in path.parts
    )


def shard_number(path: Path, *, shard_count: int) -> int:
    """Return the stable, one-based shard number for *path*."""

    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(path.as_posix().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big") % shard_count + 1


def select_shard(
    files: Sequence[Path], *, shard_index: int, shard_count: int
) -> list[Path]:
    """Select exactly the files assigned to a one-based shard index."""

    if not 1 <= shard_index <= shard_count:
        raise ValueError("shard_index must be between 1 and shard_count")
    return [
        path
        for path in sorted(files)
        if shard_number(path, shard_count=shard_count) == shard_index
    ]


def write_manifest(
    path: Path,
    *,
    shard_index: int,
    shard_count: int,
    files: Sequence[Path],
) -> None:
    """Write stable evidence describing one shard's exact file inventory."""

    payload = {
        "schema": "calm.pytest_shard.v1",
        "shard_index": shard_index,
        "shard_count": shard_count,
        "file_count": len(files),
        "files": [item.as_posix() for item in files],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, pytest_args = parser.parse_known_args(argv)
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]

    try:
        files = select_shard(
            discover_test_files(),
            shard_index=args.index,
            shard_count=args.count,
        )
    except ValueError as exc:
        parser.error(str(exc))

    if not files:
        parser.error(f"pytest shard {args.index}/{args.count} contains no files")

    manifest = args.manifest
    if not manifest.is_absolute():
        manifest = REPO_ROOT / manifest
    write_manifest(
        manifest,
        shard_index=args.index,
        shard_count=args.count,
        files=files,
    )

    print(
        f"Running pytest shard {args.index}/{args.count}: "
        f"{len(files)} files; manifest={manifest.relative_to(REPO_ROOT)}"
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        *pytest_args,
        *(path.as_posix() for path in files),
    ]
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
