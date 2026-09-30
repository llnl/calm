"""Repository guardrails for shared claim-benchmark mechanics."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLAIMS_ROOT = ROOT / "benchmarks" / "benchmarks" / "claims"
SUPPORT = CLAIMS_ROOT / "_support.py"

_RETIRED_LOCAL_HELPERS = {
    "_write_jsonl_atomic",
    "_write_csv_atomic",
    "_matrix_payload",
    "_key_text",
    "_slab_from_basis",
}


def _top_level_import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_claim_support_is_mechanical_and_scientifically_independent() -> None:
    assert SUPPORT.is_file()
    text = SUPPORT.read_text(encoding="utf-8")
    assert "scientific policies" in text
    assert "workload selection" in text
    assert "correctness oracles" in text
    assert "calm" not in _top_level_import_roots(SUPPORT)
    assert "pymatgen" not in _top_level_import_roots(SUPPORT)


def test_claim_modules_do_not_redeclare_consolidated_mechanics() -> None:
    offenders: list[str] = []
    for path in sorted(CLAIMS_ROOT.rglob("*.py")):
        if path == SUPPORT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in _RETIRED_LOCAL_HELPERS:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.name}")
    assert offenders == []


def test_claim_families_import_shared_mechanics_from_current_owner() -> None:
    expected = {
        CLAIMS_ROOT / "extension_stability.py": {
            "key_text",
            "matrix_payload",
            "slab_from_basis",
            "write_csv_atomic",
            "write_jsonl_atomic",
        },
        CLAIMS_ROOT / "identity_policy.py": {
            "matrix_payload",
            "write_csv_atomic",
            "write_jsonl_atomic",
        },
        CLAIMS_ROOT / "differential_search.py": {
            "key_text",
            "matrix_payload",
            "slab_from_basis",
            "write_csv_atomic",
            "write_jsonl_atomic",
        },
        CLAIMS_ROOT / "public_api_parity.py": {
            "write_csv_atomic",
            "write_jsonl_atomic",
        },
        CLAIMS_ROOT / "gate_domain.py": {"write_csv_atomic"},
        CLAIMS_ROOT / "zsl" / "oracle_comparison.py": {
            "key_text",
            "slab_from_basis",
            "write_canonical_jsonl_atomic",
            "write_csv_atomic",
        },
        CLAIMS_ROOT / "zsl" / "projection_suite.py": {
            "write_canonical_jsonl_atomic"
        },
        CLAIMS_ROOT / "zsl" / "source_capture.py": {
            "write_canonical_jsonl_atomic"
        },
    }
    for path, names in expected.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module not in {"_support", "benchmarks.benchmarks.claims._support"}:
                continue
            imported.update(alias.name for alias in node.names)
        assert names <= imported, path
