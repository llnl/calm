"""Guardrails for the documented strain-partition alpha convention."""

from __future__ import annotations

from importlib.machinery import ModuleSpec

import importlib.util
import sys
import types

import numpy as np
import pytest

# calm.interface.refinement.strain imports calm.interface.types, which imports calm.symmetry and
# therefore optional ASE/spglib adapters at package import time. These endpoint tests
# exercise only dependency-light SPD(2) strain code, so provide minimal import stubs
# when the optional backend packages are absent.
def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except ValueError:
        return name in sys.modules


def _module_stub(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__spec__ = ModuleSpec(name, loader=None)
    return module


_INSERTED_STUBS: list[str] = []
if not _module_available("spglib"):
    sys.modules["spglib"] = _module_stub("spglib")
    _INSERTED_STUBS.append("spglib")
if not _module_available("ase"):
    ase_stub = _module_stub("ase")

    class Atoms:  # pragma: no cover - import stub only
        pass

    ase_stub.Atoms = Atoms
    sys.modules["ase"] = ase_stub
    _INSERTED_STUBS.append("ase")

try:
    from calm.interface.refinement.strain import compute_strain_2d
    from calm.interface.refinement.partition import scan_geodesic_strain_partitions
finally:
    for _module_name in _INSERTED_STUBS:
        sys.modules.pop(_module_name, None)


def _cell(scale_x: float, scale_y: float) -> np.ndarray:
    cell = np.eye(3, dtype=float)
    cell[0, 0] = float(scale_x)
    cell[1, 1] = float(scale_y)
    return cell


def test_compute_strain_alpha_endpoints_document_target_metric_convention() -> None:
    slab_a = _cell(1.0, 1.0)
    slab_b = _cell(1.2, 0.8)

    alpha0 = compute_strain_2d(slab_a, slab_b, alpha=0.0)
    alpha1 = compute_strain_2d(slab_a, slab_b, alpha=1.0)

    # alpha=0 chooses slab A's metric as target: A is unstrained and B carries mismatch.
    assert alpha0.E_A_rms == pytest.approx(0.0, abs=1e-12)
    assert alpha0.E_B_rms > 0.0

    # alpha=1 chooses slab B's metric as target: B is unstrained and A carries mismatch.
    assert alpha1.E_B_rms == pytest.approx(0.0, abs=1e-12)
    assert alpha1.E_A_rms > 0.0


def test_scan_geodesic_strain_partitions_preserves_endpoint_convention() -> None:
    slab_a = _cell(1.0, 1.0)
    slab_b = _cell(1.2, 0.8)

    def score_fn(state):
        # Prefer the endpoint where side A remains unstrained.
        return float(state.E_A_rms)

    result = scan_geodesic_strain_partitions(
        slab_a,
        slab_b,
        alphas=[0.0, 1.0],
        score_fn=score_fn,
        return_trace=True,
    )

    assert result.best.alpha == 0.0
    assert result.best.strain_state.E_A_rms == pytest.approx(0.0, abs=1e-12)
    assert result.best.strain_state.E_B_rms > 0.0
    assert result.trace is not None
    assert result.trace[0] == pytest.approx((0.0, 0.0), abs=1e-12)
    assert result.trace[1][0] == 1.0
    assert result.trace[1][1] > 0.0
