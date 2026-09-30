"""Strict dependency-light JSON canonicalization for current CALM contracts.

This module owns deterministic serialization for current workflow declarations
and scientific payloads that are already required to be JSON-native. It does
not replace frozen historical identity serializers whose coercion or rounding
rules are part of an older persisted identity contract.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from math import isfinite
from typing import Any


def json_native(value: Any, *, path: str = "$") -> Any:
    """Return a strict JSON-native projection or raise at ``path``.

    Tuples are accepted as immutable sequence inputs and represented as JSON
    arrays. Mapping keys must already be strings. Unsupported objects are never
    stringified because doing so would hide identity-bearing type errors.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"JSON value at {path} must be finite.")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON mapping key at {path} must be a string.")
            normalized[key] = json_native(item, path=f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            json_native(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(
        "JSON-native values must be scalars, mappings, lists, or tuples; "
        f"unsupported {type(value).__name__} at {path}."
    )


def canonical_json(value: Any) -> str:
    """Serialize strict JSON-native content deterministically."""

    return json.dumps(
        json_native(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


__all__ = ["canonical_json", "json_native"]
