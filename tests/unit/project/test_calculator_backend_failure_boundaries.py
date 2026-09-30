from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest

from calm.calculators.exceptions import (
    CalculatorBuildError,
    CalculatorExecutionError,
    OptionalDependencyError,
)
from calm.calculators.spec import CalculatorSpec
from calm.project.application.followups.energy_backends import (
    _attach_real_calculator,
    _compute_real_single_point,
    _real_target_atoms,
)
from calm.project.application.followups import interface_energy, registry_search
from calm.project.application.followups.strain_scan import (
    StrainPartitionScanOrchestrator,
)


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def _spec(model: str = "model") -> CalculatorSpec:
    return CalculatorSpec(family="test", model=model)


@pytest.fixture(autouse=True)
def _stub_partition_geometry(monkeypatch: pytest.MonkeyPatch) -> None:
    def geometry(_prototype, *, alpha: float):
        total = (-0.02, 0.04)
        side_a = tuple(sorted(float(alpha) * value for value in total))
        side_b = tuple(sorted(-(1.0 - float(alpha)) * value for value in total))
        return SimpleNamespace(
            X=np.diag([2.0, 3.0]),
            side_a_principal_log_strains=side_a,
            side_b_principal_log_strains=side_b,
            side_a_max_abs_principal_log_strain=max(abs(value) for value in side_a),
            side_b_max_abs_principal_log_strain=max(abs(value) for value in side_b),
            side_a_airm_distance=2.0 * sum(value * value for value in side_a) ** 0.5,
            side_b_airm_distance=2.0 * sum(value * value for value in side_b) ** 0.5,
        )

    monkeypatch.setattr(
        interface_energy,
        "_strain_partition_geometry",
        geometry,
    )


def test_real_energy_target_copy_failure_is_not_silently_ignored() -> None:
    class BrokenTarget:
        def copy(self):
            raise RuntimeError("copy failed")

    with pytest.raises(CalculatorExecutionError, match="Could not detach"):
        _real_target_atoms(
            config={"target_atoms": BrokenTarget()},
            uow=object(),
            prototype_uid="proto:test",
            builder=lambda *args, **kwargs: None,
        )


def test_real_energy_calculator_dependency_error_is_preserved() -> None:
    def missing(spec, *, quiet):
        del spec, quiet
        raise OptionalDependencyError("backend package is missing")

    with pytest.raises(OptionalDependencyError, match="backend package is missing"):
        _attach_real_calculator(
            atoms=SimpleNamespace(calc=None),
            calc_spec=_spec(),
            maker=missing,
        )


def test_real_energy_rejects_nonfinite_evaluator_result() -> None:
    with pytest.raises(CalculatorExecutionError, match="non-finite"):
        _compute_real_single_point(
            atoms=object(),
            calc_spec=_spec(),
            calc=object(),
            evaluator=lambda *args, **kwargs: float("nan"),
        )


def _prepared_registry_evaluator() -> registry_search._PreparedRegistryEvaluator:
    prepared = SimpleNamespace(
        c1=np.array([1.0, 0.0, 0.0]),
        c2=np.array([0.0, 1.0, 0.0]),
    )
    return registry_search._PreparedRegistryEvaluator(
        prepared_interface=prepared,
        calc_spec=_spec(),
        calc=object(),
        area_A2=1.0,
    )


def test_registry_objective_raises_instead_of_returning_infinite_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "calm.interface.building._kernel.build_prepared_interface_atoms",
        lambda *args, **kwargs: SimpleNamespace(atoms=object()),
    )
    monkeypatch.setattr(
        interface_energy,
        "compute_interface_energy",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            CalculatorExecutionError("calculator kernel failed")
        ),
    )

    with pytest.raises(CalculatorExecutionError, match="calculator kernel failed"):
        registry_search._registry_energy_density(
            _prepared_registry_evaluator(),
            np.asarray([0.0, 0.0]),
        )


def test_registry_preparation_preserves_geometry_failure_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        interface_energy,
        "prepare_interface_from_prototype_with_strain",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("invalid interface geometry")
        ),
    )

    with pytest.raises(ValueError, match="invalid interface geometry"):
        registry_search._prepare_registry_energy_evaluator(
            _Context(),
            prototype_uid="proto:test",
            calc_spec=_spec(),
            calc=object(),
            alpha=0.5,
            z_padding=1.5,
            vacuum_padding=None,
        )


def test_registry_search_preserves_calculator_execution_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = object.__new__(registry_search.RegistrySearchOrchestrator)
    orchestrator._uow = _Context()
    monkeypatch.setattr(
        registry_search,
        "_make_registry_calculator",
        lambda spec: object(),
    )
    monkeypatch.setattr(
        registry_search,
        "_prepare_registry_energy_evaluator",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        registry_search,
        "_registry_energy_density",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            CalculatorExecutionError("evaluation failed")
        ),
    )

    with pytest.raises(CalculatorExecutionError, match="evaluation failed"):
        orchestrator._compute_monte_carlo_trace(
            base="run:test",
            n_steps=1,
            prototype_uid_full="proto:test",
            calc_spec=_spec(),
        )


def test_strain_scan_does_not_fall_back_to_an_attached_calculator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Atoms:
        calc = object()
        energy_calls = 0

        def get_potential_energy(self):
            self.energy_calls += 1
            return -1.0

    atoms = Atoms()
    monkeypatch.setattr(
        interface_energy,
        "load_interface_prototype",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        interface_energy,
        "_build_loaded_interface_prototype",
        lambda *args, **kwargs: atoms,
    )
    monkeypatch.setattr(
        interface_energy,
        "construct_calculator",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            CalculatorBuildError("requested calculator failed")
        ),
    )

    with pytest.raises(CalculatorBuildError, match="requested calculator failed"):
        interface_energy.compute_strain_scan_energy_point(
            _Context(),
            "proto:test",
            alpha=0.5,
            calc_spec=_spec(),
            calc=None,
        )
    assert atoms.energy_calls == 0


def test_optional_strained_bulk_geometry_failure_is_not_a_calculator_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Atoms:
        calc = None

        def get_potential_energy(self):
            return 12.0

        def get_cell(self):
            return np.diag([2.0, 3.0, 10.0])

    prototype = SimpleNamespace(
        slab_a=SimpleNamespace(bulk=None),
        slab_b=SimpleNamespace(bulk=None),
    )
    monkeypatch.setattr(
        interface_energy,
        "load_interface_prototype",
        lambda *args, **kwargs: prototype,
    )
    monkeypatch.setattr(
        interface_energy,
        "_build_loaded_interface_prototype",
        lambda *args, **kwargs: Atoms(),
    )

    pipeline = types.ModuleType("calm.interface.pipeline")
    pipeline.compute_strain_state = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("gamma pipeline must not run")
    )
    pipeline.build_interface = lambda *args, **kwargs: object()
    pipeline.compute_interfacial_energy = lambda *args, **kwargs: object()
    monkeypatch.setitem(sys.modules, "calm.interface.pipeline", pipeline)

    uow = SimpleNamespace()
    result = interface_energy.compute_strain_scan_energy_point(
        uow,
        "proto:test",
        alpha=0.5,
        calc_spec=_spec(),
        calc=object(),
    )

    assert result["potential_energy_eV"] == pytest.approx(12.0)
    assert np.isnan(result["gamma_eV_per_A2"])
    assert np.isnan(result["gamma_J_per_m2"])


def test_unexpected_strained_bulk_geometry_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Atoms:
        calc = None

        def get_potential_energy(self):
            return 12.0

        def get_cell(self):
            return np.diag([2.0, 3.0, 10.0])

    prototype = SimpleNamespace(
        slab_a=SimpleNamespace(bulk=object()),
        slab_b=SimpleNamespace(bulk=object()),
    )
    monkeypatch.setattr(
        interface_energy,
        "load_interface_prototype",
        lambda *args, **kwargs: prototype,
    )
    monkeypatch.setattr(
        interface_energy,
        "_build_loaded_interface_prototype",
        lambda *args, **kwargs: Atoms(),
    )

    pipeline = types.ModuleType("calm.interface.pipeline")
    pipeline.compute_strain_state = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("invalid strained geometry")
    )
    pipeline.build_interface = lambda *args, **kwargs: object()
    pipeline.compute_interfacial_energy = lambda *args, **kwargs: object()
    monkeypatch.setitem(sys.modules, "calm.interface.pipeline", pipeline)

    uow = SimpleNamespace()
    with pytest.raises(RuntimeError, match="invalid strained geometry"):
        interface_energy.compute_strain_scan_energy_point(
            uow,
            "proto:test",
            alpha=0.5,
            calc_spec=_spec(),
            calc=object(),
        )


def test_optional_strained_bulk_calculator_failure_still_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Atoms:
        calc = None

        def get_potential_energy(self):
            return 12.0

        def get_cell(self):
            return np.diag([2.0, 3.0, 10.0])

    prototype = SimpleNamespace(
        slab_a=SimpleNamespace(bulk=object()),
        slab_b=SimpleNamespace(bulk=object()),
    )
    monkeypatch.setattr(
        interface_energy,
        "load_interface_prototype",
        lambda *args, **kwargs: prototype,
    )
    monkeypatch.setattr(
        interface_energy,
        "_build_loaded_interface_prototype",
        lambda *args, **kwargs: Atoms(),
    )

    pipeline = types.ModuleType("calm.interface.pipeline")
    pipeline.compute_strain_state = lambda *args, **kwargs: object()
    pipeline.build_interface = lambda *args, **kwargs: object()
    pipeline.compute_interfacial_energy = lambda *args, **kwargs: (_ for _ in ()).throw(
        CalculatorExecutionError("calculator evaluation failed")
    )
    monkeypatch.setitem(sys.modules, "calm.interface.pipeline", pipeline)

    uow = SimpleNamespace()
    with pytest.raises(
        CalculatorExecutionError,
        match="calculator evaluation failed",
    ):
        interface_energy.compute_strain_scan_energy_point(
            uow,
            "proto:test",
            alpha=0.5,
            calc_spec=_spec(),
            calc=object(),
        )


def test_strain_scan_run_spec_owns_exact_calculator_identity() -> None:
    first = _spec("model-one").to_dict()
    second = _spec("model-two").to_dict()
    targets = [
        {
            "prototype_uid_full": "proto:test",
            "target_uid_full": "proto:test",
            "target_kind": "prototype",
        }
    ]

    first_spec = StrainPartitionScanOrchestrator._create_run_spec(
        targets,
        {"target_metric": "potential_energy_density_eV_per_A2"},
        [0.5],
        {"proto:test": first},
    )
    second_spec = StrainPartitionScanOrchestrator._create_run_spec(
        targets,
        {"target_metric": "potential_energy_density_eV_per_A2"},
        [0.5],
        {"proto:test": second},
    )

    assert first_spec["calculator_specs"]["proto:test"] == first
    assert second_spec["calculator_specs"]["proto:test"] == second
    assert (
        first_spec["calculator_fingerprints"]["proto:test"]
        != second_spec["calculator_fingerprints"]["proto:test"]
    )


def test_strain_scan_rejects_disappearing_prototype() -> None:
    uow = SimpleNamespace(prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: None))

    with pytest.raises(KeyError, match="Prototype not found"):
        interface_energy.compute_strain_scan_energy_point(
            uow,
            "proto:test",
            alpha=0.5,
            calc_spec=_spec(),
            calc=object(),
        )
