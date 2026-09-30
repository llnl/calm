"""Shared filesystem helpers for the canonical CALM tutorial programs."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from calm import write_json

TUTORIAL_ROOT = Path(__file__).resolve().parent
EXAMPLES_ROOT = TUTORIAL_ROOT.parent
WORK_ROOT = EXAMPLES_ROOT / "work"
EXPECTED_ROOT = TUTORIAL_ROOT / "expected"


def default_work_dir(name: str) -> Path:
    """Return the repository-owned output directory for one tutorial."""

    if not name or name.strip() != name or "/" in name or "\\" in name:
        raise ValueError("tutorial work-directory names must be simple non-empty names")
    return WORK_ROOT / name


def prepare_directory(path: Path, *, reset: bool) -> Path:
    path = path.expanduser().resolve()
    if reset and path.exists():
        shutil.rmtree(path)
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(
            f"Tutorial output directory already exists and is not empty: {path}. "
            "Use --reset to replace it."
        )
    path.mkdir(parents=True, exist_ok=True)
    return path


def expectation(name: str) -> dict[str, Any]:
    path = EXPECTED_ROOT / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_run_summary(output_directory: Path, payload: dict[str, Any]) -> Path:
    destination = output_directory / "run-summary.json"
    write_json(destination, payload, sort_keys=True)
    return destination
