"""Registry and provider abstractions for calculator backends.

This module defines interfaces and a simple registry used to map logical
calculator "families" (e.g. "ase", "lammps", "mace") to concrete provider
implementations. It intentionally keeps runtime imports minimal so the registry
can be queried even when optional backends are not installed.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any

from .exceptions import (
    CalculatorBuildError,
    CalculatorError,
    CalculatorRegistryError,
    CalculatorSpecError,
    OptionalDependencyError,
)
from .spec import CalculatorSpec


class CalculatorProvider:
    """Provider interface for constructing ASE-compatible calculators."""

    @property
    def family(self) -> str:  # pragma: no cover
        raise NotImplementedError

    def describe(self) -> str:  # pragma: no cover
        return ""

    def required_extras(self) -> tuple[str, ...]:  # pragma: no cover
        return ()

    def is_available(self) -> bool:  # pragma: no cover
        return True

    def list_models(self) -> tuple[str, ...]:  # pragma: no cover
        return ()

    def normalize_spec(
        self, spec: "CalculatorSpec"
    ) -> "CalculatorSpec":  # pragma: no cover
        """Normalize and validate a spec (default: passthrough).

        Providers may override this to fill declared defaults or validate
        supported models and options. Runtime aliases are unsupported.
        """
        return spec

    def create(self, spec: CalculatorSpec) -> Any:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class ProviderInfo:
    family: str
    available: bool
    description: str
    required_extras: tuple[str, ...]


class CalculatorRegistry:
    """Registry mapping calculator 'families' to providers."""

    def __init__(self) -> None:
        self._providers: dict[str, CalculatorProvider] = {}

    def register(
        self, provider: CalculatorProvider, *, overwrite: bool = False
    ) -> None:
        family = provider.family
        if not isinstance(family, str) or not family:
            raise CalculatorRegistryError("Provider family must be a non-empty string.")
        if family != family.strip() or family != family.lower():
            raise CalculatorRegistryError(
                "Provider family must use its canonical lowercase identifier "
                "without surrounding whitespace."
            )
        if (family in self._providers) and not overwrite:
            raise CalculatorRegistryError(
                f"Provider for family '{family}' is already registered. "
                f"Pass overwrite=True to replace it."
            )
        self._providers[family] = provider

    def has(self, family: str) -> bool:
        return isinstance(family, str) and family in self._providers

    def families(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def provider(self, family: str) -> CalculatorProvider:
        if not isinstance(family, str):
            raise TypeError("Calculator family must be a string.")
        key = family
        if key not in self._providers:
            raise CalculatorRegistryError(
                f"Unknown calculator family '{family}'. Available families: {list(self._providers)}"
            )
        return self._providers[key]

    def info(self) -> tuple[ProviderInfo, ...]:
        out: list[ProviderInfo] = []
        for fam in self.families():
            p = self._providers[fam]
            available = bool(p.is_available())
            out.append(
                ProviderInfo(
                    family=fam,
                    available=available,
                    description=str(p.describe() or ""),
                    required_extras=tuple(p.required_extras() or ()),
                )
            )
        return tuple(out)

    def create(self, spec: CalculatorSpec) -> Any:
        if not isinstance(spec, CalculatorSpec):
            raise TypeError(
                "CalculatorRegistry.create requires a CalculatorSpec instance."
            )
        provider = self.provider(spec.family)
        try:
            normalized = provider.normalize_spec(spec)
            if not isinstance(normalized, CalculatorSpec):
                raise CalculatorRegistryError(
                    f"Provider {provider.family!r} returned an invalid normalized specification."
                )
            return provider.create(normalized)
        except CalculatorError:
            raise
        except Exception as e:
            raise CalculatorBuildError(
                f"Provider '{provider.family}' failed to build calculator for spec: {spec.label()}. "
                f"Underlying error: {type(e).__name__}: {e}"
            ) from e


class ASEProvider(CalculatorProvider):
    """Provider for lightweight ASE built-in calculators (e.g. EMT)."""

    VALID_MODELS: tuple[str, ...] = ("EMT", "LJ", "Morse")
    DEFAULT_MODEL: str = "EMT"

    @property
    def family(self) -> str:
        return "ase"

    def describe(self) -> str:
        return "ASE built-in calculators (emt/lj/morse/...); intended for testing and baselines."

    def required_extras(self) -> tuple[str, ...]:
        return ("ase",)

    def is_available(self) -> bool:
        return importlib.util.find_spec("ase") is not None

    def list_models(self) -> tuple[str, ...]:
        return self.VALID_MODELS

    def create(self, spec: CalculatorSpec) -> Any:
        if not self.is_available():
            raise OptionalDependencyError(
                "ASE is required to build 'ase' calculators. Please install ase."
            )

        model = spec.model
        if model not in self.VALID_MODELS:
            raise CalculatorSpecError(
                f"Unknown ASE calculator model {model!r}. "
                f"Supported models are: {', '.join(self.VALID_MODELS)}."
            )

        options = spec.options_dict()
        if model == "EMT":
            from ase.calculators.emt import EMT

            return EMT(**options)

        if model == "LJ":
            from ase.calculators.lj import LennardJones

            return LennardJones(**options)

        if model == "Morse":
            from ase.calculators.morse import MorsePotential

            return MorsePotential(**options)

        raise AssertionError("Validated ASE model was not dispatched.")


_DEFAULT_REGISTRY: CalculatorRegistry | None = None


def default_registry() -> CalculatorRegistry:
    """Return a process-global registry with calm's built-in providers registered."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        reg = CalculatorRegistry()
        reg.register(ASEProvider())

        # Provider classes are import-light; optional backend imports happen only
        # inside provider ``create`` methods. A broken provider module is a CALM
        # defect and must not be hidden by partial registry construction.
        from .providers import (
            CHGNetProvider,
            GRACEProvider,
            LAMMPSProvider,
            MACEProvider,
        )

        reg.register(MACEProvider())
        reg.register(CHGNetProvider())
        reg.register(GRACEProvider())
        reg.register(LAMMPSProvider())

        _DEFAULT_REGISTRY = reg
    return _DEFAULT_REGISTRY
