"""Calculator-specific exception types.

Defines small exception classes used by the calculator subsystem; kept
separate to avoid circular imports and to provide clear exception semantics.
"""

from __future__ import annotations

from calm.exceptions import CALMError
from calm.exceptions import OptionalDependencyError as CALMOptionalDependencyError


class CalculatorError(CALMError):
    """Base error for calm.calculators."""


class CalculatorSpecError(CalculatorError, ValueError):
    """Raised when a CalculatorSpec is invalid or cannot be serialized."""


class CalculatorRegistryError(CalculatorError, KeyError):
    """Raised when providers are missing or ambiguous."""


class OptionalDependencyError(CalculatorError, CALMOptionalDependencyError):
    """Raised when a requested calculator provider is not installed."""


class CalculatorBuildError(CalculatorError, RuntimeError):
    """Raised when a provider fails while constructing a calculator instance."""


class CalculatorExecutionError(CalculatorError, RuntimeError):
    """Raised when a constructed calculator fails during scientific execution."""


class CalculatorFingerprintError(CalculatorError, ValueError):
    """Raised when a live calculator cannot provide an exact stable identity."""


class CalculatorProvenanceError(CalculatorError, RuntimeError):
    """Raised when authoritative persisted calculator provenance is unavailable."""
