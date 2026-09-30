"""Repository guardrails for exact rank-two acceleration ownership."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXACT_KERNEL = ROOT / "calm" / "math2d" / "_exact_rank2.py"
PAIRED_LATTICE = ROOT / "calm" / "math2d" / "paired_lattice.py"


def test_exact_rank_two_acceleration_uses_bounded_pure_function_caches() -> None:
    exact_source = EXACT_KERNEL.read_text(encoding="utf-8")
    paired_source = PAIRED_LATTICE.read_text(encoding="utf-8")

    assert "_HNF_CACHE_SIZE = 512" in exact_source
    assert "@lru_cache(maxsize=_HNF_CACHE_SIZE)" in exact_source
    assert "_COMMON_RIGHT_CACHE_SIZE = 512" in paired_source
    assert "@lru_cache(maxsize=_COMMON_RIGHT_CACHE_SIZE)" in paired_source
    assert "np.empty" not in exact_source
    assert "numba" not in exact_source.lower()
