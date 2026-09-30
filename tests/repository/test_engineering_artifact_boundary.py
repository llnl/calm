"""Repository boundary for executable engineering infrastructure."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "engineering"
QUALIFICATION_MATRIX = ENGINEERING / "qualification" / "qualification-matrix.json"


def test_engineering_tree_contains_no_narrative_markdown() -> None:
    markdown = sorted(path.relative_to(ROOT).as_posix() for path in ENGINEERING.rglob("*.md"))
    assert markdown == []


def test_campaign_closeout_is_not_permanent_qualification_infrastructure() -> None:
    assert not (
        ENGINEERING / "architecture" / "serial-acceleration-closeout-0338f.json"
    ).exists()
    assert not (
        ENGINEERING / "qualification" / "check_serial_acceleration_closeout.py"
    ).exists()

    matrix = json.loads(QUALIFICATION_MATRIX.read_text(encoding="utf-8"))
    ids = {
        check["id"]
        for profile in matrix["profiles"].values()
        for check in profile["checks"]
    }
    assert "serial-acceleration-closeout-contract" not in ids
