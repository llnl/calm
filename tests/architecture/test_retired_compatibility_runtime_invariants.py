"""Runtime probes for CALM's machine-readable retirement contract."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "engineering" / "qualification" / "check_package_organization.py"
CONTRACT = ROOT / "engineering" / "architecture" / "current-package-ownership.json"


def _retirement() -> dict[str, object]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    retirement = payload["retirement"]
    assert isinstance(retirement, dict)
    return retirement


def test_retirement_contract_is_enforced_by_package_checker() -> None:
    completed = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "retirement boundaries" in completed.stdout


def test_representative_retired_modules_stay_unimportable() -> None:
    probes = _retirement()["runtime_import_probes"]
    assert isinstance(probes, list)
    assert probes
    for module_name in probes:
        assert isinstance(module_name, str)
        with pytest.raises(ModuleNotFoundError) as caught:
            importlib.import_module(module_name)
        missing = caught.value.name
        assert missing is not None
        assert module_name == missing or module_name.startswith(f"{missing}.")
