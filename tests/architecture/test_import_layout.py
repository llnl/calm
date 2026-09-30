"""Import/layout guardrails.

These tests prevent regressions in package layout that can lead to ambiguous
imports (module/package name collisions) or accidental exposure of deprecated
modules.

They are intentionally "mechanical" invariants rather than domain-behavior tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _public_children(root: Path):
    """Yield immediate children of *root* excluding hidden/private entries."""

    for p in root.iterdir():
        name = p.name
        if name.startswith("."):
            continue
        if name.startswith("__"):
            continue
        yield p


def test_no_module_package_name_collisions() -> None:
    import calm

    root = Path(calm.__file__).resolve().parent

    dir_names = {p.name for p in _public_children(root) if p.is_dir()}
    mod_names = {p.stem for p in _public_children(root) if p.is_file() and p.suffix == ".py"}

    collisions = sorted(dir_names & mod_names)
    assert collisions == [], f"Found module/package collisions in calm/: {collisions}"


def test_state_manager_is_not_part_of_core_package() -> None:
    # state_manager is legacy (pickle-based persistence) and must not be importable
    # from the calm core namespace.
    with pytest.raises(ModuleNotFoundError):
        __import__("calm.state_manager", fromlist=["*"])
