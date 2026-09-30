"""Behavior contracts for removed optional workflows."""

from __future__ import annotations

from pathlib import Path


def test_optional_extras_namespace_is_not_shipped() -> None:
    root = Path(__file__).resolve().parents[2]

    assert not any((root / "calm" / "extras").rglob("*.py"))
