"""Repository contracts for the focused Ruff ownership inputs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "engineering" / "qualification" / "check_typing_modernization_contract.py"
RESPONSE_FILE = (
    ROOT / "engineering" / "qualification" / "typing-modernization-files.txt"
)
MATRIX = ROOT / "engineering" / "qualification" / "qualification-matrix.json"


def _load_checker():
    spec = importlib.util.spec_from_file_location("typing_contract_checker", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_typing_modernization_checker_accepts_current_owners() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload == {
        "errors": [],
        "per_file_ignore_count": 1,
        "response_file": "engineering/qualification/typing-modernization-files.txt",
        "schema": "calm.typing_modernization_contract_check/v1",
        "source_count": 17,
    }


def test_typing_modernization_response_file_uses_current_source_owners() -> None:
    entries = RESPONSE_FILE.read_text(encoding="utf-8").splitlines()
    assert entries == sorted(entries)
    assert len(entries) == len(set(entries))
    assert all((ROOT / entry).is_file() for entry in entries)
    assert "calm/interface/building/_kernel.py" in entries
    assert "calm/interface/matching/search.py" in entries
    assert "calm/interface/matching/grouping.py" in entries
    assert "calm/interface/refinement/registry.py" in entries
    assert "calm/interface/refinement/partition.py" in entries
    assert not any("calm/interface/matching.py" == entry for entry in entries)
    assert not any("calm/slab/ops" in entry for entry in entries)


def test_checker_rejects_missing_response_file_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checker = _load_checker()
    response_file = tmp_path / "typing-modernization-files.txt"
    response_file.write_text("calm/does_not_exist.py\n", encoding="utf-8")
    monkeypatch.setattr(checker, "RESPONSE_FILE", response_file)

    with pytest.raises(AssertionError, match="does not exist"):
        checker.verify()


def test_qualification_matrix_checks_inputs_before_running_ruff() -> None:
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    checks = payload["profiles"]["contracts"]["checks"]
    ids = [check["id"] for check in checks]
    input_index = ids.index("typing-modernization-input-contract")
    ruff_index = ids.index("ruff-typing-modernization")
    assert input_index < ruff_index
    assert checks[input_index]["command"] == [
        "{python}",
        "engineering/qualification/check_typing_modernization_contract.py",
    ]
