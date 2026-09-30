"""Executable verification for the reviewed single-public-API projection."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "engineering" / "qualification" / "check_public_api_consistency.py"
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_checked_in_public_api_projection_is_consistent() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == "calm.public_api_contract.v4"
    assert contract["release_stage"] == "stable"
    assert contract["persistence"] == {
        "database_schema_version": "v2.0.0",
        "compatibility_policy": "exact_current_regeneration_only",
        "automatic_migration": False,
        "in_place_repair": False,
    }
    assert "tier" not in json.dumps(contract).lower()

    completed = _run()
    assert completed.returncode == 0, completed.stderr
    assert "Public API consistency verified" in completed.stdout

    current = _run("--show-current")
    assert current.returncode == 0, current.stderr
    projection = json.loads(current.stdout)
    assert projection["contract_exports"] == projection["runtime_exports"]
    assert (
        projection["contract_implementations"]
        == projection["runtime_implementations"]
    )
    assert projection["contract_project_methods"] == projection["runtime_project_methods"]
    assert projection["release_stage"] == "stable"
    assert projection["database_schema_version"] == "v2.0.0"
    assert (
        projection["project_compatibility_policy"]
        == "exact_current_regeneration_only"
    )
    assert projection["automatic_project_migration_supported"] is False
    assert projection["in_place_project_repair_supported"] is False
    assert "public_sidecar_schema_version" not in projection


def test_consistency_checker_is_not_a_symbol_count_freeze() -> None:
    source = CHECKER.read_text(encoding="utf-8")
    assert "beta-contract-freeze" not in source
    assert "expected_count" not in source
    assert "frozen" not in source.lower()
    assert "current-public-contract.json" in source
