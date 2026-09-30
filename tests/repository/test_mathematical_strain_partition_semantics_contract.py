"""Repository guardrails for the strain-partition endpoint convention."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_source_facing_alpha_descriptions_use_target_metric_convention() -> None:
    prohibited = (
        "all strain on slab A",
        "all strain on slab B",
        "0.0 = all on slab A",
        "1.0 = all on slab B",
    )
    offenders: list[str] = []
    for path in (ROOT / "calm").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for phrase in prohibited:
            if phrase in text:
                offenders.append(f"{path.relative_to(ROOT)}: {phrase}")
    assert offenders == []

    owner = (
        ROOT / "calm" / "project" / "application" / "prototype_analysis.py"
    ).read_text(encoding="utf-8")
    assert "alpha=0 leaves A unstrained" in owner
    assert "alpha=1 leaves B unstrained" in owner


def test_finite_alpha_scan_declares_selection_and_failure_policies() -> None:
    source = (
        ROOT / "calm" / "interface" / "refinement" / "partition.py"
    ).read_text(encoding="utf-8")
    assert '"grid_source"' in source
    assert '"objective_name"' in source
    assert '"tie_policy": "first_occurrence_in_alpha_order"' in source
    assert '"nonfinite_score_policy": "raise"' in source
