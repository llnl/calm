from __future__ import annotations

import sys
from types import ModuleType
from types import SimpleNamespace

import pytest

from calm.calculators.exceptions import (
    CalculatorBuildError,
    CalculatorExecutionError,
    CalculatorProvenanceError,
)
from calm.exceptions import OptionalDependencyError
from calm.public.workflows.material_optimization import (
    ProjectMaterialOptimizationService,
)
from calm.public.inputs.materials import Material
from calm.public.inputs.potentials import Potential


class _Project:
    def __init__(self, material: Material):
        self._material = material
        self.requested = []

    def material(self, selector: str):
        self.requested.append(selector)
        return self._material


class _Saver:
    def __init__(self):
        self.calls = []

    def persist_material(self, material, *, name=None, reporter=None):
        self.calls.append(
            {
                "material": material,
                "name": name,
                "reporter": reporter,
            }
        )
        material.uid_full = "bulk:optimized"
        material.id_short = "b_optimized"
        material.authority = "authoritative"
        return material


def _material() -> Material:
    return Material(
        name="raw",
        label="Raw",
        atoms=SimpleNamespace(),
        formula="X",
    )


def test_project_material_optimization_composes_once_and_persists(monkeypatch) -> None:
    source = _material()
    project = _Project(source)
    saver = _Saver()
    service = ProjectMaterialOptimizationService(project=project, saver=saver)
    optimized = Material(
        name="raw",
        label="Raw",
        atoms=SimpleNamespace(),
        formula="X",
        state="optimized_bulk",
    )
    observed = {}
    calculator = object()

    def optimize(material, **kwargs):
        observed["material"] = material
        observed.update(kwargs)
        return optimized

    monkeypatch.setattr(service, "_optimize_structure", optimize)

    result = service.optimize_material(
        "raw-selector",
        calculator=calculator,
        name="optimized",
        fmax=0.04,
        steps=17,
        relax_cell=False,
        optimizer="FIRE",
    )

    assert project.requested == ["raw-selector"]
    assert observed == {
        "material": source,
        "potential": None,
        "calculator": calculator,
        "fmax": 0.04,
        "steps": 17,
        "relax_cell": False,
        "optimizer": "FIRE",
    }
    assert saver.calls[0]["material"] is optimized
    assert saver.calls[0]["name"] == "optimized"
    assert result is optimized
    assert result.uid_full == "bulk:optimized"


def test_potential_provenance_is_exact_and_project_owned(monkeypatch) -> None:
    source = _material()
    project = _Project(source)
    saver = _Saver()
    service = ProjectMaterialOptimizationService(project=project, saver=saver)
    optimized = Material(
        name="raw",
        label="Raw",
        atoms=SimpleNamespace(),
        formula="X",
        state="optimized_bulk",
    )
    potential = Potential.mace(model="model-one")
    configured = []

    monkeypatch.setattr(
        service,
        "_optimize_structure",
        lambda *_args, **_kwargs: optimized,
    )
    monkeypatch.setattr(
        "calm.public.inputs.project_config.configure",
        lambda project, **kwargs: configured.append((project, kwargs)),
    )

    result = service.optimize_material(source, potential=potential)

    spec = getattr(optimized, "optimized_with")
    assert spec.family == "mace"
    assert spec.model == "model-one"
    assert configured == [
        (
            project,
            {
                "mlip": "mace",
                "calculator": spec.to_dict(),
                "defaults": None,
            },
        )
    ]
    assert result is optimized


def test_material_optimization_rejects_competing_calculator_inputs() -> None:
    with pytest.raises(TypeError, match="exactly one"):
        ProjectMaterialOptimizationService._calculator_from_inputs(
            potential=Potential.mace(),
            calculator=object(),
        )

    with pytest.raises(ValueError, match="requires potential"):
        ProjectMaterialOptimizationService._calculator_from_inputs(
            potential=None,
            calculator=None,
        )


def test_material_optimization_requires_public_potential_type() -> None:
    with pytest.raises(TypeError, match="calm.Potential"):
        ProjectMaterialOptimizationService._calculator_from_inputs(
            potential=SimpleNamespace(calculator=lambda: object()),
            calculator=None,
        )


def test_material_optimization_preserves_calculator_construction_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    potential = Potential.mace()

    def fail(_self):
        raise CalculatorBuildError("requested backend failed")

    monkeypatch.setattr(Potential, "calculator", fail)
    with pytest.raises(CalculatorBuildError, match="requested backend failed"):
        ProjectMaterialOptimizationService._calculator_from_inputs(
            potential=potential,
        )


def test_material_optimization_classifies_missing_ase_optimizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    material = Material(
        name="raw",
        label="Raw",
        atoms=SimpleNamespace(
            copy=lambda: None,
            get_positions=lambda: None,
            get_cell=lambda: None,
        ),
        formula="X",
    )
    real_import = __import__

    def blocked_import(name, *args, **kwargs):
        if name == "ase.optimize":
            raise ImportError("ASE optimizer unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(OptionalDependencyError, match="requires ASE BFGS"):
        ProjectMaterialOptimizationService._optimize_structure(
            material,
            calculator=object(),
            optimizer="BFGS",
            fmax=0.1,
            steps=2,
            relax_cell=False,
        )


def test_material_optimization_classifies_target_copy_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ase_module = ModuleType("ase")
    ase_module.__path__ = []
    optimize_module = ModuleType("ase.optimize")
    optimize_module.BFGS = object
    monkeypatch.setitem(sys.modules, "ase", ase_module)
    monkeypatch.setitem(sys.modules, "ase.optimize", optimize_module)

    class BrokenAtoms:
        def get_positions(self):
            return []

        def get_cell(self):
            return []

        def copy(self):
            raise RuntimeError("copy failed")

    material = Material(
        name="raw",
        label="Raw",
        atoms=BrokenAtoms(),
        formula="X",
    )
    with pytest.raises(CalculatorExecutionError, match="copy failed"):
        ProjectMaterialOptimizationService._optimize_structure(
            material,
            calculator=object(),
            optimizer="BFGS",
            fmax=0.1,
            steps=2,
            relax_cell=False,
        )


def test_material_optimization_decodes_persisted_atoms_before_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DecodedAtoms:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def copy(self):
            raise RuntimeError("decoded atoms reached copy")

    ase_module = ModuleType("ase")
    ase_module.__path__ = []
    ase_module.Atoms = DecodedAtoms
    optimize_module = ModuleType("ase.optimize")
    optimize_module.BFGS = object
    monkeypatch.setitem(sys.modules, "ase", ase_module)
    monkeypatch.setitem(sys.modules, "ase.optimize", optimize_module)

    material = Material(
        name="saved",
        label="Saved",
        atoms={
            "numbers": [29],
            "cell": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "scaled_positions": [[0.0, 0.0, 0.0]],
            "pbc": [True, True, True],
        },
        formula="X",
    )

    with pytest.raises(
        CalculatorExecutionError,
        match="decoded atoms reached copy",
    ):
        ProjectMaterialOptimizationService._optimize_structure(
            material,
            calculator=object(),
            optimizer="BFGS",
            fmax=0.1,
            steps=2,
            relax_cell=False,
        )


def test_material_optimization_rejects_external_calculator_provenance_before_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _material()
    project = _Project(source)
    saver = _Saver()
    service = ProjectMaterialOptimizationService(project=project, saver=saver)
    potential = Potential.from_ase(
        type("ExternalCalculator", (), {"parameters": {}})(),
    )
    called = False

    def optimize(*args, **kwargs):
        nonlocal called
        del args, kwargs
        called = True

    monkeypatch.setattr(service, "_optimize_structure", optimize)
    with pytest.raises(CalculatorProvenanceError, match="reconstructible"):
        service.optimize_material(source, potential=potential)
    assert called is False
    assert saver.calls == []
