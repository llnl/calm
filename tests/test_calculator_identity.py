from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.calculators.exceptions import CalculatorFingerprintError
from calm.calculators.identity import get_calculator_uid


class _ParameterizedCalculator:
    def __init__(self, parameters: dict, *, label: str | None = None) -> None:
        self.parameters = parameters
        self.label = label


def test_calculator_uid_preserves_precomputed_uid() -> None:
    assert get_calculator_uid("calc:already-known") == "calc:already-known"


def test_calculator_uid_prefers_explicit_calculator_uid() -> None:
    calculator = _ParameterizedCalculator({"cutoff": 5.0})
    calculator.calculator_uid = "calc:explicit"
    assert get_calculator_uid(calculator) == "calc:explicit"


def test_calculator_uid_is_deterministic_for_type_and_parameters() -> None:
    first = _ParameterizedCalculator({"cutoff": 5.0, "stress": True}, label="model")
    second = _ParameterizedCalculator({"stress": True, "cutoff": 5.0}, label="model")

    assert get_calculator_uid(first) == get_calculator_uid(second)
    assert get_calculator_uid(first).startswith("calc:")


def test_calculator_uid_rejects_failed_todict() -> None:
    class BrokenCalculator:
        def todict(self):
            raise RuntimeError("serialization failed")

    with pytest.raises(CalculatorFingerprintError, match=r"todict\(\) failed"):
        get_calculator_uid(BrokenCalculator())


def test_calculator_uid_requires_exact_settings_without_explicit_uid() -> None:
    class OpaqueCalculator:
        pass

    with pytest.raises(CalculatorFingerprintError, match="no explicit CALM UID"):
        get_calculator_uid(OpaqueCalculator())


def test_calculator_uid_rejects_nonmapping_parameters() -> None:
    class InvalidCalculator:
        parameters = ["not", "a", "mapping"]

    with pytest.raises(CalculatorFingerprintError, match="must be a mapping"):
        get_calculator_uid(InvalidCalculator())


def test_interfacial_energy_rejects_opaque_calculator_identity() -> None:
    from calm.interface.pipeline import compute_interfacial_energy

    interface = SimpleNamespace(atoms=object(), build_uid="build:test")
    with pytest.raises(CalculatorFingerprintError, match="no explicit CALM UID"):
        compute_interfacial_energy(interface, object())
