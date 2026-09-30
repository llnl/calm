"""Dependency-light exact JSON representation helpers for application records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calm.serialization.json import json_native as _strict_json_native


def json_native(obj: Any, *, _path: str = "$") -> Any:
    """Convert application payload values to exact JSON-native objects.

    NumPy carriers and explicit ``tolist()`` providers are representation
    adapters only. Conversion failures and unsupported values propagate instead
    of leaving an opaque object for a later persistence layer to reinterpret.
    """

    try:
        import numpy as np  # type: ignore
    except ImportError:  # pragma: no cover - NumPy is a CALM dependency
        np = None  # type: ignore[assignment]

    if np is not None:
        if isinstance(obj, np.generic):
            return json_native(obj.item(), _path=_path)
        if isinstance(obj, np.ndarray):
            return json_native(obj.tolist(), _path=_path)

    if isinstance(obj, Mapping):
        normalized: dict[str, Any] = {}
        for key, value in obj.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON mapping key at {_path} must be a string.")
            normalized[key] = json_native(value, _path=f"{_path}.{key}")
        return normalized

    if isinstance(obj, (list, tuple)):
        return [
            json_native(value, _path=f"{_path}[{index}]")
            for index, value in enumerate(obj)
        ]

    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        converted = tolist()
        if converted is obj:
            raise TypeError(
                f"tolist() returned the original {type(obj).__name__} at {_path}."
            )
        return json_native(converted, _path=_path)

    return _strict_json_native(obj, path=_path)
