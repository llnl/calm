from __future__ import annotations

import pytest

from calm.calculators.exceptions import CalculatorSpecError
from calm.calculators.providers import (
    LAMMPSProvider,
    _validate_kwargs_for_callable,
)
from calm.calculators.spec import CalculatorSpec


def test_callable_validation_rejects_silently_dropped_options() -> None:
    def constructor(*, supported=None):
        return supported

    with pytest.raises(CalculatorSpecError, match="unsupported"):
        _validate_kwargs_for_callable(
            constructor,
            {"supported": 1, "unsupported": 2},
        )


def test_lammps_rejects_pair_style_owned_by_model_and_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LAMMPSProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    spec = CalculatorSpec(
        family="lammps",
        model="eam/alloy",
        options={"parameters": {"pair_style": "lj/cut"}},
    )

    with pytest.raises(CalculatorSpecError, match="either by spec.model"):
        provider.create(spec)


def test_lammps_rejects_duplicate_parameter_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LAMMPSProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    spec = CalculatorSpec(
        family="lammps",
        model="custom",
        options={
            "parameters": {"pair_coeff": ["* * potential.eam Al"]},
            "pair_coeff": ["* * other.eam Al"],
        },
    )

    with pytest.raises(CalculatorSpecError, match="specified both"):
        provider.create(spec)


def test_lammps_backend_aliases_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = LAMMPSProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)

    for retired in ("lammpsrun", "subprocess", "lammpslib", "inprocess"):
        with pytest.raises(CalculatorSpecError, match="Expected exactly 'run' or 'lib'"):
            provider.create(
                CalculatorSpec(
                    family="lammps",
                    model="custom",
                    options={"backend": retired},
                )
            )
