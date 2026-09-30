"""Repository guardrails for bounded correspondence acceleration."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORRESPONDENCE = ROOT / "calm" / "interface" / "matching" / "_correspondence.py"
ORCHESTRATOR = ROOT / "calm" / "interface" / "matching" / "_orchestrator.py"


def test_correspondence_uses_bounded_exact_determinant_screening() -> None:
    source = CORRESPONDENCE.read_text(encoding="utf-8")

    assert "_VECTOR_DETERMINANT_PAIR_THRESHOLD = 4096" in source
    assert "_VECTOR_DETERMINANT_TARGET_BYTES = 4 * 1024 * 1024" in source
    assert "_INT64_DETERMINANT_SAFE_COMPONENT" in source
    assert "_enumerate_vectorized_determinants" in source
    assert "_enumerate_scalar_pairs" in source
    assert "determinant_chunks" in source
    assert "numba" not in source.lower()


def test_coupled_matching_reuses_prepared_correspondence_metrics() -> None:
    source = ORCHESTRATOR.read_text(encoding="utf-8")

    assert "correspondence_metric_cache" in source
    assert "_prepare_correspondence_metric_2d" in source
    assert "_enumerate_basis_correspondence_records_prepared_2d" in source
    assert "enumerate_basis_correspondences_2d(" not in source
