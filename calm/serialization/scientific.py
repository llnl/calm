"""Strict JSON projection for finite scientific values.

This owner extends the current JSON-native contract to NumPy arrays and
scalars used by scientific provenance. Unsupported values are never
stringified, and non-finite floating-point values are rejected.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

import numpy as np


def scientific_json_native(value: Any, *, path: str = "$") -> Any:
    """Return a strict JSON-native projection of finite scientific data."""

    if isinstance(value, np.generic):
        return scientific_json_native(value.item(), path=path)
    if isinstance(value, np.ndarray):
        return scientific_json_native(value.tolist(), path=path)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"Scientific JSON value at {path} must be finite.")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(
                    f"Scientific JSON mapping key at {path} must be a string."
                )
            normalized[key] = scientific_json_native(
                item,
                path=f"{path}.{key}",
            )
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            scientific_json_native(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(
        "Scientific JSON values must be finite scalars, NumPy values, "
        f"mappings, lists, or tuples; unsupported {type(value).__name__} "
        f"at {path}."
    )


__all__ = ["scientific_json_native"]
