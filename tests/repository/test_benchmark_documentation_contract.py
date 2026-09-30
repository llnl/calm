from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README = REPOSITORY_ROOT / "benchmarks" / "README.md"


def test_benchmark_readme_documents_the_complete_suite_entry_point() -> None:
    text = README.read_text(encoding="utf-8")

    assert "python -m benchmarks.run_full_suite" in text
    assert "python -m benchmarks.run_all" in text
    assert "run_all` is only the cross-tool" in text
    assert "tests/unit/benchmarks" in text
    assert "coupled-smoke.csv" in text
    assert "coupled-square-scaling.csv" in text
    assert "public_api_qualification.json" in text
    assert "oracle_status=pass" in text
    assert "benchmarks/legacy/" in text
    assert "test_legacy_benchmark_contract.py" in text
