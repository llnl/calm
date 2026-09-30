"""Repository guardrails for search-scoped matching reuse."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR = ROOT / "calm" / "interface" / "matching" / "_orchestrator.py"
PAIR_IDENTITY = ROOT / "calm" / "interface" / "matching" / "_pair_identity.py"
SURFACE_ORBITS = ROOT / "calm" / "interface" / "matching" / "_surface_orbits.py"


def test_matching_reuse_remains_search_scoped() -> None:
    orchestrator = ORCHESTRATOR.read_text(encoding="utf-8")
    pair_identity = PAIR_IDENTITY.read_text(encoding="utf-8")
    surface_orbits = SURFACE_ORBITS.read_text(encoding="utf-8")

    assert "class _CandidateGeometry2D" in orchestrator
    assert "geometry_cache: dict[" in orchestrator
    assert "representative_ranks: dict[" in orchestrator
    assert "if surface_context_a.key == surface_context_b.key:" in orchestrator
    assert "_build_candidate_geometry(" in orchestrator
    assert "_build_source_provenance(" in orchestrator
    assert "class _PairIdentityContext2D" in pair_identity
    assert "_prepare_pair_identity_context_2d" in pair_identity
    assert "class _SurfaceOrbitBuildContext2D" in surface_orbits
    assert "_prepare_surface_orbit_build_context_2d" in surface_orbits
    assert "@lru_cache" not in orchestrator
    assert "@lru_cache" not in pair_identity
    assert "@lru_cache" not in surface_orbits
