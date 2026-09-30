"""Contracts for the standalone deformation-accounting walkthrough."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "examples" / "deformation_accounting.py"


def _load_example_module():
    spec = importlib.util.spec_from_file_location("deformation_accounting_example", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deformation_accounting_example_composes_the_declared_maps() -> None:
    module = _load_example_module()
    result = module.deformation_example()

    gauge = np.asarray(result["gauge"], dtype=float)
    construction_source = np.asarray(result["construction_source"], dtype=float)
    construction_gauge = np.asarray(result["construction_gauge"], dtype=float)
    interface_increment = np.asarray(result["interface_increment"], dtype=float)
    total_pre = np.asarray(result["total_pre_relaxation"], dtype=float)
    relaxation = np.asarray(result["relaxation"], dtype=float)
    total_post = np.asarray(result["total_post_relaxation"], dtype=float)

    assert np.allclose(construction_gauge, gauge @ construction_source @ gauge.T)
    assert np.allclose(total_pre, interface_increment @ construction_gauge)
    assert np.allclose(total_post, relaxation @ total_pre)
    assert float(result["composition_order_difference"]) > 0.0


def test_deformation_accounting_example_runs_from_the_repository_root() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "CALM deformation-accounting example" in completed.stdout
    assert "total after relaxation" in completed.stdout
    assert "ASE row-cell transpose check: passed" in completed.stdout
