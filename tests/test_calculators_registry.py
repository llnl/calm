from __future__ import annotations

import pytest

from calm.calculators.api import list_models, list_providers, make_calculator
from calm.calculators.exceptions import (
    CalculatorBuildError,
    CalculatorRegistryError,
    CalculatorSpecError,
    OptionalDependencyError,
)
from calm.calculators.registry import CalculatorProvider, CalculatorRegistry
from calm.calculators.spec import CalculatorSpec


class DummyProvider(CalculatorProvider):
    @property
    def family(self) -> str:
        return "dummy"

    def describe(self) -> str:
        return "deterministic dummy provider"

    def required_extras(self) -> tuple[str, ...]:
        return ("dummy-extra",)

    def is_available(self) -> bool:
        return True

    def list_models(self) -> tuple[str, ...]:
        return ("normalized",)

    def normalize_spec(self, spec: CalculatorSpec) -> CalculatorSpec:
        return spec.replace(model="normalized")

    def create(self, spec: CalculatorSpec):
        return {"built_for": spec.model}


class FailingProvider(DummyProvider):
    @property
    def family(self) -> str:
        return "failing"

    def create(self, spec: CalculatorSpec):
        raise ValueError("backend failed")


class MissingDependencyProvider(DummyProvider):
    @property
    def family(self) -> str:
        return "missing-dependency"

    def create(self, spec: CalculatorSpec):
        raise OptionalDependencyError("install the requested provider")


class InvalidSpecProvider(DummyProvider):
    @property
    def family(self) -> str:
        return "invalid-spec"

    def normalize_spec(self, spec: CalculatorSpec) -> CalculatorSpec:
        raise CalculatorSpecError("unsupported model selection")


class BrokenAvailabilityProvider(DummyProvider):
    @property
    def family(self) -> str:
        return "broken-availability"

    def is_available(self) -> bool:
        raise RuntimeError("availability probe defect")


def test_registry_is_authoritative_for_creation_and_public_projection() -> None:
    registry = CalculatorRegistry()
    registry.register(DummyProvider())

    spec = CalculatorSpec(family="dummy", model="alias")
    assert make_calculator(spec, registry=registry) == {"built_for": "normalized"}
    assert list_models("dummy", registry=registry) == ("normalized",)

    info = list_providers(registry=registry)
    assert len(info) == 1
    assert info[0].family == "dummy"
    assert info[0].available is True
    assert info[0].description == "deterministic dummy provider"
    assert info[0].required_extras == ("dummy-extra",)


def test_registry_rejects_unknown_family() -> None:
    registry = CalculatorRegistry()
    with pytest.raises(CalculatorRegistryError, match="Unknown calculator family"):
        registry.create(CalculatorSpec(family="missing", model="x"))


def test_registry_wraps_provider_construction_errors() -> None:
    registry = CalculatorRegistry()
    registry.register(FailingProvider())

    with pytest.raises(CalculatorBuildError, match="backend failed"):
        registry.create(CalculatorSpec(family="failing", model="x"))


def test_registry_preserves_optional_dependency_errors() -> None:
    registry = CalculatorRegistry()
    registry.register(MissingDependencyProvider())

    with pytest.raises(OptionalDependencyError, match="install the requested"):
        registry.create(
            CalculatorSpec(family="missing-dependency", model="x")
        )


def test_registry_preserves_invalid_spec_errors() -> None:
    registry = CalculatorRegistry()
    registry.register(InvalidSpecProvider())

    with pytest.raises(CalculatorSpecError, match="unsupported model"):
        registry.create(CalculatorSpec(family="invalid-spec", model="x"))


def test_registry_does_not_hide_broken_availability_checks() -> None:
    registry = CalculatorRegistry()
    registry.register(BrokenAvailabilityProvider())

    with pytest.raises(RuntimeError, match="availability probe defect"):
        registry.info()


def test_calculator_family_identifiers_are_exact() -> None:
    with pytest.raises(CalculatorSpecError, match="canonical lowercase"):
        CalculatorSpec(family="ASE", model="EMT")
    with pytest.raises(CalculatorSpecError, match="surrounding whitespace"):
        CalculatorSpec(family=" ase ", model="EMT")

    registry = CalculatorRegistry()

    class UppercaseProvider(DummyProvider):
        @property
        def family(self) -> str:
            return "DUMMY"

    with pytest.raises(CalculatorRegistryError, match="canonical lowercase"):
        registry.register(UppercaseProvider())


def test_ase_model_aliases_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from calm.calculators.registry import ASEProvider

    provider = ASEProvider()
    monkeypatch.setattr(provider, "is_available", lambda: True)
    for retired in ("emt", "ase.emt", "lennardjones", "morse"):
        with pytest.raises(CalculatorSpecError, match="Unknown ASE calculator model"):
            provider.create(CalculatorSpec(family="ase", model=retired))
