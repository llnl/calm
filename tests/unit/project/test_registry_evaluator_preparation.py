from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.calculators.spec import CalculatorSpec
from calm.interface.refinement.registry import monte_carlo_registry_search
from calm.project.application.followups import registry_search


def _spec() -> CalculatorSpec:
    return CalculatorSpec(family="test", model="deterministic")


class _Context:
    def __init__(self) -> None:
        self.enter_count = 0
        self.exit_count = 0

    def __enter__(self):
        self.enter_count += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exit_count += 1


def _periodic_score(translation: np.ndarray) -> float:
    target = np.asarray([0.2, 0.7], dtype=float)
    delta = (np.asarray(translation, dtype=float) - target + 0.5) % 1.0 - 0.5
    return float(delta @ delta)


def test_registry_evaluator_prepares_uow_geometry_and_area_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _Context()
    prepared = SimpleNamespace(
        c1=np.asarray([2.0, 0.0, 0.0]),
        c2=np.asarray([0.5, 3.0, 0.0]),
    )
    calls = 0

    def prepare(*args, **kwargs):
        nonlocal calls
        calls += 1
        return prepared

    monkeypatch.setattr(
        "calm.project.application.followups.interface_energy."
        "prepare_interface_from_prototype_with_strain",
        prepare,
    )
    calc = object()
    evaluator = registry_search._prepare_registry_energy_evaluator(
        context,
        prototype_uid="proto:test",
        calc_spec=_spec(),
        calc=calc,
        alpha=0.4,
        z_padding=1.5,
        vacuum_padding=2.0,
    )

    assert calls == 1
    assert context.enter_count == context.exit_count == 1
    assert evaluator.prepared_interface is prepared
    assert evaluator.calc is calc
    assert evaluator.area_A2 == 6.0


def test_registry_evaluator_reuses_prepared_geometry_calculator_and_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = object()
    atoms = object()
    calc = object()
    spec = _spec()
    build_calls: list[tuple[object, tuple[float, float]]] = []
    energy_calls: list[tuple[object, CalculatorSpec, object]] = []

    def build(value, *, translation_frac):
        build_calls.append((value, translation_frac))
        return SimpleNamespace(atoms=atoms)

    def energy(value, value_spec, *, relax, calc):
        assert relax is False
        energy_calls.append((value, value_spec, calc))
        return 12.0

    monkeypatch.setattr(
        "calm.interface.building._kernel.build_prepared_interface_atoms",
        build,
    )
    monkeypatch.setattr(
        "calm.project.application.followups.interface_energy."
        "compute_interface_energy",
        energy,
    )
    evaluator = registry_search._PreparedRegistryEvaluator(
        prepared_interface=prepared,
        calc_spec=spec,
        calc=calc,
        area_A2=4.0,
    )

    result = registry_search._registry_energy_density(
        evaluator,
        np.asarray([1.25, -0.5]),
    )

    assert result == 3.0
    assert build_calls == [(prepared, (1.25, -0.5))]
    assert energy_calls == [(atoms, spec, calc)]


def test_registry_orchestrator_prepares_once_and_preserves_seeded_trajectory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestrator = object.__new__(registry_search.RegistrySearchOrchestrator)
    orchestrator._uow = _Context()
    calc = object()
    evaluator = object()
    counts = {"calculator": 0, "prepare": 0, "evaluate": 0}

    def make_calculator(_specification):
        counts["calculator"] += 1
        return calc

    def prepare(*args, **kwargs):
        counts["prepare"] += 1
        assert kwargs["calc"] is calc
        return evaluator

    def evaluate(value, translation):
        assert value is evaluator
        counts["evaluate"] += 1
        return _periodic_score(translation)

    monkeypatch.setattr(registry_search, "_make_registry_calculator", make_calculator)
    monkeypatch.setattr(
        registry_search,
        "_prepare_registry_energy_evaluator",
        prepare,
    )
    monkeypatch.setattr(registry_search, "_registry_energy_density", evaluate)

    observed = orchestrator._compute_monte_carlo_trace(
        base="run:test",
        n_steps=8,
        prototype_uid_full="proto:test",
        calc_spec=_spec(),
        alpha=0.5,
        translation0=(0.0, 0.0),
        step_scale=0.15,
        temperature=0.05,
        seed=123,
    )
    expected = monte_carlo_registry_search(
        _periodic_score,
        n_steps=8,
        step_scale=0.15,
        temperature=0.05,
        seed=123,
        x0=(0.0, 0.0),
        keep_trace=True,
        score_units="eV_per_A2",
    )

    assert counts == {"calculator": 1, "prepare": 1, "evaluate": 9}
    assert observed.translation == expected.translation
    assert observed.score == expected.score
    assert observed.n_accepted == expected.n_accepted
    assert observed.trace == expected.trace
    assert observed.proposal_trace == expected.proposal_trace
