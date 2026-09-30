"""Exact runtime construction helpers for calculator-backed workflows."""

from __future__ import annotations

from typing import Any

from .spec import CalculatorSpec


def construct_calculator(
    spec: CalculatorSpec,
    *,
    quiet: bool = False,
) -> Any:
    """Construct exactly the requested calculator once.

    Output suppression is a presentation policy only. It never changes the
    selected provider, retries construction, or converts a construction failure
    into a fallback calculator.
    """

    if not isinstance(spec, CalculatorSpec):
        raise TypeError("construct_calculator requires a CalculatorSpec instance.")

    from .api import make_calculator

    if not quiet:
        return make_calculator(spec)

    from .quiet import suppress_mlip_output

    with suppress_mlip_output():
        return make_calculator(spec)
