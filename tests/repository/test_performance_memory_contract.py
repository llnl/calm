"""Repository guardrails for performance-memory evidence."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "benchmarks" / "benchmarks" / "run_performance_qualification.py"
SUPPORT = ROOT / "benchmarks" / "benchmarks" / "_performance_support.py"
README = ROOT / "benchmarks" / "README.md"
EXACT_KERNEL = ROOT / "calm" / "math2d" / "_exact_rank2.py"
PAIRED_LATTICE = ROOT / "calm" / "math2d" / "paired_lattice.py"


def test_memory_qualification_distinguishes_python_and_resident_peaks() -> None:
    harness = HARNESS.read_text(encoding="utf-8")
    support = SUPPORT.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    exact_source = EXACT_KERNEL.read_text(encoding="utf-8")
    paired_source = PAIRED_LATTICE.read_text(encoding="utf-8")

    assert '"peak_process_bytes": peak_process_bytes()' in harness
    assert '"process_memory_comparison_mode": "cold_process_only"' in harness
    assert "def peak_process_bytes" in support
    assert "ru_maxrss" in support
    assert "`peak_python_bytes` is a Python-allocation metric" in readme
    assert "`cold_process` workers" in readme
    assert "_HNF_CACHE_SIZE = 512" in exact_source
    assert "_COMMON_RIGHT_CACHE_SIZE = 512" in paired_source
