from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_relaxation_orchestrator_does_not_fabricate_interface_identity() -> None:
    source = (
        ROOT / "calm" / "project" / "application" / "followups" / "relaxation.py"
    ).read_text(encoding="utf-8")
    assert "iface:synthetic" not in source
    assert "synthetic placeholder UID" not in source
