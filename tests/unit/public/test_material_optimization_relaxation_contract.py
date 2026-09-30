from __future__ import annotations

import numpy as np
import pytest

ase = pytest.importorskip("ase")
from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes

from calm.public.workflows.material_optimization import (
    ProjectMaterialOptimizationService,
)
from calm.public.inputs.materials import Material


class _ZeroCalculator(Calculator):
    implemented_properties = ["energy", "forces", "stress"]

    def calculate(
        self,
        atoms=None,
        properties=("energy", "forces"),
        system_changes=all_changes,
    ):
        super().calculate(atoms, properties, system_changes)
        self.results = {
            "energy": 0.0,
            "forces": np.zeros((len(atoms), 3), dtype=float),
            "stress": np.zeros(6, dtype=float),
        }


def _material() -> Material:
    atoms = Atoms(
        "Al",
        positions=[[0.0, 0.0, 0.0]],
        cell=np.eye(3) * 4.0,
        pbc=True,
    )
    return Material.from_ase(atoms, name="Al")


def test_material_optimize_honors_requested_optimizer(monkeypatch) -> None:
    calls: list[str] = []

    class _FakeLBFGS:
        def __init__(self, target, logfile=None):
            del logfile
            self.target = target
            self.nsteps = 0
            calls.append("LBFGS")

        def run(self, *, fmax, steps):
            assert fmax == pytest.approx(0.1)
            assert steps == 2
            return True

    monkeypatch.setattr("ase.optimize.LBFGS", _FakeLBFGS)
    optimized = ProjectMaterialOptimizationService._optimize_structure(
        _material(),
        calculator=_ZeroCalculator(),
        optimizer="LBFGS",
        fmax=0.1,
        steps=2,
        relax_cell=False,
    )

    assert calls == ["LBFGS"]
    assert optimized.state == "optimized_bulk"
    assert optimized.metadata["optimizer"] == "LBFGS"
    assert optimized.metadata["convergence_certificate"]["converged"] is True
    assert optimized.metadata["calculator_identity"]["class"].endswith(
        "_ZeroCalculator"
    )


def test_material_optimize_cell_mode_records_frechet_convention() -> None:
    optimized = ProjectMaterialOptimizationService._optimize_structure(
        _material(),
        calculator=_ZeroCalculator(),
        optimizer="BFGS",
        fmax=0.1,
        steps=2,
        relax_cell=True,
    )

    assert optimized.metadata["cell_filter"] == "FrechetCellFilter"
    assert optimized.metadata["cell_factor_mode"] == "n_atoms"
    assert optimized.metadata["cell_factor"] == pytest.approx(1.0)
    certificate = optimized.metadata["convergence_certificate"]
    assert certificate["residual_satisfied"] is True
