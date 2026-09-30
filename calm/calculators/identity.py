"""Deterministic identities for live calculator instances."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calm.keys.uid import calculator_uid

from .exceptions import CalculatorFingerprintError


def get_calculator_uid(calculator: Any) -> str:
    """Return a deterministic CALM UID for a live calculator or UID string.

    Explicit calculator UIDs are preferred. Otherwise CALM hashes the calculator
    import path together with JSON-like ``parameters`` or ``todict()`` output
    when available. For reproducible workflows, a persisted
    :class:`~calm.calculators.spec.CalculatorSpec` remains the authoritative
    configuration record.
    """

    if calculator is None:
        return "calc:none"

    if isinstance(calculator, str):
        if calculator.startswith("calc:"):
            return calculator
        return calculator_uid({"value": calculator})

    for attribute in ("calm_uid", "calculator_uid", "uid"):
        value = getattr(calculator, attribute, None)
        if isinstance(value, str) and value.strip():
            if value.startswith("calc:"):
                return value
            return calculator_uid({"value": value})

    payload: dict[str, Any] = {
        "type": f"{type(calculator).__module__}.{type(calculator).__qualname__}",
    }

    parameters = getattr(calculator, "parameters", None)
    if parameters is not None:
        if not isinstance(parameters, Mapping):
            raise CalculatorFingerprintError(
                "Live calculator parameters must be a mapping to establish "
                "an exact deterministic identity."
            )
        payload["parameters"] = dict(parameters)
    else:
        to_dict = getattr(calculator, "todict", None)
        if callable(to_dict):
            try:
                serialized = to_dict()
            except Exception as exc:
                raise CalculatorFingerprintError(
                    "Live calculator todict() failed while establishing its "
                    f"deterministic identity: {type(exc).__name__}: {exc}"
                ) from exc
            if not isinstance(serialized, Mapping):
                raise CalculatorFingerprintError(
                    "Live calculator todict() must return a mapping to establish "
                    "an exact deterministic identity."
                )
            payload["parameters"] = dict(serialized)

    if "parameters" not in payload:
        raise CalculatorFingerprintError(
            "Live calculator has no explicit CALM UID and exposes neither a "
            "mapping-valued parameters attribute nor a mapping-valued todict()."
        )

    label = getattr(calculator, "label", None)
    if isinstance(label, str) and label:
        payload["label"] = label

    try:
        return calculator_uid(payload)
    except Exception as exc:
        raise CalculatorFingerprintError(
            "Live calculator settings are not canonically serializable: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
