"""Public calculator-provider API.

The public helpers in this module delegate to the current calculator registry.
Provider construction, normalization, availability reporting, and model
enumeration each have one authoritative owner in :mod:`calm.calculators.registry`.
"""

from __future__ import annotations

from typing import Any

from .registry import CalculatorRegistry, ProviderInfo, default_registry
from .spec import CalculatorSpec


def make_calculator(
    spec: CalculatorSpec,
    *,
    registry: CalculatorRegistry | None = None,
) -> Any:
    """Construct an ASE-compatible calculator from ``spec``."""

    if not isinstance(spec, CalculatorSpec):
        raise TypeError("make_calculator requires a CalculatorSpec instance.")
    reg = default_registry() if registry is None else registry
    return reg.create(spec)


def list_providers(
    *,
    registry: CalculatorRegistry | None = None,
) -> tuple[ProviderInfo, ...]:
    """Return summaries of the registered calculator providers."""

    reg = default_registry() if registry is None else registry
    return reg.info()


def list_models(
    family: str,
    *,
    registry: CalculatorRegistry | None = None,
) -> tuple[str, ...]:
    """Return the model names explicitly advertised by ``family``."""

    reg = default_registry() if registry is None else registry
    return reg.provider(family).list_models()
