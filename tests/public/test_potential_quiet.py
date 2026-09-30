from __future__ import annotations

import sys
import importlib

import pytest

from calm.calculators.exceptions import CalculatorBuildError
from calm.calculators.exceptions import CalculatorProvenanceError
from calm.public.inputs.potentials import Potential


def test_potential_creation_does_not_import_calculators():
    # Creating a Potential should not import the heavy calculators package.
    # Ensure calm.calculators is not present after construction.
    sys.modules.pop("calm.calculators", None)
    p = Potential.grace("GRACE-1L-OMAT", device="cpu", quiet=True)
    assert "calm.calculators" not in sys.modules


def test_potential_calculator_uses_registry_with_quiet(monkeypatch):
    called = {}

    def make_calculator(spec):
        called["made"] = True
        return "FAKE_CALC"

    calculator_api = importlib.import_module("calm.calculators.api")
    monkeypatch.setattr(calculator_api, "make_calculator", make_calculator)

    p = Potential.grace("GRACE-1L-OMAT", device="cpu", quiet=True)
    calc = p.calculator()
    assert calc == "FAKE_CALC"
    assert called.get("made") is True


def test_validate_is_the_only_eager_validation_method(monkeypatch):
    def make_calculator(spec):
        return "FAKE_CALC"

    calculator_api = importlib.import_module("calm.calculators.api")
    monkeypatch.setattr(calculator_api, "make_calculator", make_calculator)

    p = Potential.grace("GRACE-1L-OMAT", device="cpu", quiet=True)
    assert p.validate() is p
    assert not hasattr(Potential, "require")


def test_potential_to_spec_preserves_provider_options() -> None:
    potential = Potential.mace(
        "medium-mpa-0",
        device="cuda",
        stress=False,
        dispersion=True,
    )

    assert potential.to_spec() == {
        "schema_version": 1,
        "family": "mace",
        "model": "medium-mpa-0",
        "version": None,
        "source": None,
        "device": "cuda",
        "dtype": None,
        "options": {"stress": False, "dispersion": True},
    }


def test_mace_default_matches_provider_model_name() -> None:
    assert Potential.mace().model == "medium-mpa-0"


def test_quiet_potential_construction_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calculator_api = importlib.import_module("calm.calculators.api")
    calls = 0

    def fail(spec):
        nonlocal calls
        del spec
        calls += 1
        raise CalculatorBuildError("construction failed")

    monkeypatch.setattr(calculator_api, "make_calculator", fail)
    with pytest.raises(CalculatorBuildError, match="construction failed"):
        Potential.grace(quiet=True).calculator()
    assert calls == 1


def test_external_ase_potential_has_live_identity_but_no_persisted_spec() -> None:
    calculator = type(
        "ExternalCalculator",
        (),
        {"parameters": {"cutoff": 4.5}},
    )()
    potential = Potential.from_ase(calculator, name="external")

    assert len(potential.fingerprint()) == 64
    with pytest.raises(CalculatorProvenanceError, match="reconstructible"):
        potential.to_spec()


def test_support_queries_preserve_provider_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    potential = Potential.grace(quiet=True)

    def fail_check(self, structure=None, *, elements=None):
        del self, structure, elements
        raise CalculatorBuildError("provider construction failed")

    monkeypatch.setattr(Potential, "check", fail_check)

    with pytest.raises(CalculatorBuildError, match="provider construction failed"):
        potential.supports(object())
    with pytest.raises(CalculatorBuildError, match="provider construction failed"):
        potential.unsupported_elements(object())
