from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("ase")

from ase import Atoms
from ase.calculators.calculator import Calculator, all_changes

from calm.calculators.spec import CalculatorSpec
from calm.project.application.followups.energy_backends import RealEnergyBackend


class _Uow:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Calc(Calculator):
    implemented_properties = ["energy", "forces"]

    def calculate(
        self,
        atoms=None,
        properties=("energy", "forces"),
        system_changes=all_changes,
    ):
        super().calculate(atoms, properties, system_changes)
        self.results = {
            "energy": -1.25,
            "forces": np.zeros((len(atoms), 3), dtype=float),
        }


def test_real_backend_relaxes_fixed_cell_surface(monkeypatch) -> None:
    class _BFGS:
        def __init__(self, atoms, logfile=None):
            self.atoms = atoms
            self.logfile = logfile
            self.nsteps = 1

        def run(self, fmax=None, steps=None):
            positions = self.atoms.get_positions().copy()
            positions[0, 0] += 0.01
            self.atoms.set_positions(positions)
            return True

    monkeypatch.setattr("ase.optimize.BFGS", _BFGS)
    monkeypatch.setattr("calm.calculators.api.make_calculator", lambda spec: _Calc())
    monkeypatch.setattr(
        "calm.project.application.followups.calculator_resolution."
        "require_calculator_from_prototype",
        lambda uow, prototype_uid: CalculatorSpec(
            family="test",
            model="relaxed-reference",
        ),
    )

    atoms = Atoms(
        "Al2",
        scaled_positions=[[0.0, 0.0, 0.45], [0.5, 0.5, 0.55]],
        cell=[[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 10.0]],
        pbc=True,
    )
    initial_cell = atoms.cell.array.copy()
    result = RealEnergyBackend().compute(
        run_uid="run:1",
        prototype_uid="proto:1",
        target_uid="reference:1",
        config={
            "target_atoms": atoms,
            "reference_relaxation": {
                "fmax": 0.05,
                "steps": 5,
                "relax_cell": False,
            },
        },
        uow=_Uow(),
    )

    assert result.energy == pytest.approx(-1.25)
    assert result.n_steps == 1
    assert result.relaxation_summary["converged"] is True
    assert result.relaxation_summary["relax_cell"] is False
    assert result.relaxation_summary["protocol"].startswith("cleaved_fixed_cell")
    assert np.array_equal(result.relaxed_atoms.cell.array, initial_cell)
    assert result.relaxed_atoms.positions[0, 0] == pytest.approx(0.01)
    roles = [payload.get("role") for payload in result.artifact_payloads]
    assert roles == ["relaxed_surface_summary", "relaxed_surface_atoms"]
    assert result.artifact_payloads[1]["atoms"]["numbers"] == [13, 13]
