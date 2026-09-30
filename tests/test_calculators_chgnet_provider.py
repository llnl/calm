"""Tests for the optional CHGNet calculator provider.

The default test suite must not require the real CHGNet package. These tests use
lightweight fake modules to validate provider behavior and constructor wiring.
"""

from __future__ import annotations

import sys
import types

import pytest

from calm.calculators.api import list_models, list_providers
from calm.calculators.exceptions import CalculatorSpecError
from calm.calculators.providers import CHGNetProvider
from calm.calculators.registry import default_registry
from calm.calculators.spec import CalculatorSpec


class _FakeCHGNet:
    loaded_kwargs: list[dict] = []

    @classmethod
    def load(cls, **kwargs):
        cls.loaded_kwargs.append(dict(kwargs))
        return {"loaded_with": dict(kwargs)}


class _FakeCHGNetCalculator:
    def __init__(self, *, model=None, **kwargs):
        self.model = model
        self.kwargs = dict(kwargs)


@pytest.fixture
def fake_chgnet_modules(monkeypatch):
    _FakeCHGNet.loaded_kwargs.clear()

    root = types.ModuleType("chgnet")
    model_mod = types.ModuleType("chgnet.model")
    dynamics_mod = types.ModuleType("chgnet.model.dynamics")

    model_mod.CHGNet = _FakeCHGNet
    dynamics_mod.CHGNetCalculator = _FakeCHGNetCalculator

    monkeypatch.setitem(sys.modules, "chgnet", root)
    monkeypatch.setitem(sys.modules, "chgnet.model", model_mod)
    monkeypatch.setitem(sys.modules, "chgnet.model.dynamics", dynamics_mod)

    yield

    for name in ("chgnet.model.dynamics", "chgnet.model", "chgnet"):
        sys.modules.pop(name, None)


def test_default_registry_registers_chgnet_provider() -> None:
    reg = default_registry()

    assert reg.has("chgnet")
    assert "chgnet" in {info.family for info in list_providers()}
    assert "0.3.0" in list_models("chgnet")


def test_chgnet_provider_constructs_calculator_with_model_and_device(fake_chgnet_modules, monkeypatch) -> None:
    provider = CHGNetProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)

    calc = provider.create(
        CalculatorSpec(
            family="chgnet",
            model="r2scan",
            device="cpu",
            options={"on_isolated_atoms": "ignore", "return_site_energies": True},
        )
    )

    assert isinstance(calc, _FakeCHGNetCalculator)
    assert _FakeCHGNet.loaded_kwargs == [{"model_name": "r2scan"}]
    assert calc.model == {"loaded_with": {"model_name": "r2scan"}}
    assert calc.kwargs["use_device"] == "cpu"
    assert calc.kwargs["on_isolated_atoms"] == "ignore"
    assert calc.kwargs["return_site_energies"] is True


def test_chgnet_provider_rejects_ambiguous_options(fake_chgnet_modules, monkeypatch) -> None:
    provider = CHGNetProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)

    with pytest.raises(CalculatorSpecError, match="use CalculatorSpec fields"):
        provider.create(
            CalculatorSpec(
                family="chgnet",
                model="0.3.0",
                options={"model_name": "r2scan"},
            )
        )


def test_chgnet_default_alias_is_rejected() -> None:
    provider = CHGNetProvider()
    with pytest.raises(CalculatorSpecError, match="model 'default' is retired"):
        provider.normalize_spec(
            CalculatorSpec(family="chgnet", model="default")
        )
