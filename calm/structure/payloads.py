"""Exact serialization and conversion for current CALM atom payloads."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Integral, Real
from pathlib import Path
from typing import Any

import numpy as np

from calm.exceptions import optional_dependency_error
from calm.serialization.json import json_native

_REQUIRED_FIELDS = frozenset({"numbers", "cell", "scaled_positions", "pbc"})
_OPTIONAL_FIELDS = frozenset({"info"})
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


def _sequence(name: str, value: Any, *, length: int | None = None) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"Current atoms payload field {name!r} must be a sequence.")
    result = list(value)
    if length is not None and len(result) != length:
        raise ValueError(
            f"Current atoms payload field {name!r} must contain {length} values."
        )
    return result


def _finite_real(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real number.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def canonical_atoms_payload(value: Any) -> dict[str, Any]:
    """Validate and copy CALM's exact current persisted atoms payload."""

    if not isinstance(value, Mapping):
        raise TypeError("Current atoms payload must be a mapping.")
    stored = dict(value)
    missing = sorted(_REQUIRED_FIELDS - stored.keys())
    unknown = sorted(stored.keys() - _ALLOWED_FIELDS)
    if missing:
        raise ValueError(
            "Current atoms payload is missing required field(s): "
            + ", ".join(missing)
            + "."
        )
    if unknown:
        raise ValueError(
            "Current atoms payload contains unsupported field(s): "
            + ", ".join(str(item) for item in unknown)
            + "."
        )

    numbers_raw = _sequence("numbers", stored["numbers"])
    if not numbers_raw:
        raise ValueError("Current atoms payload must contain at least one atom.")
    numbers: list[int] = []
    for index, item in enumerate(numbers_raw):
        if isinstance(item, bool) or not isinstance(item, Integral):
            raise TypeError(f"numbers[{index}] must be a positive integer.")
        number = int(item)
        if number <= 0:
            raise ValueError(f"numbers[{index}] must be positive.")
        numbers.append(number)

    cell_rows = _sequence("cell", stored["cell"], length=3)
    cell: list[list[float]] = []
    for row_index, row_raw in enumerate(cell_rows):
        row = _sequence(f"cell[{row_index}]", row_raw, length=3)
        cell.append(
            [
                _finite_real(f"cell[{row_index}][{column_index}]", item)
                for column_index, item in enumerate(row)
            ]
        )

    positions_raw = _sequence("scaled_positions", stored["scaled_positions"])
    if len(positions_raw) != len(numbers):
        raise ValueError(
            "Current atoms payload scaled_positions length must equal numbers length."
        )
    scaled_positions: list[list[float]] = []
    for row_index, row_raw in enumerate(positions_raw):
        row = _sequence(f"scaled_positions[{row_index}]", row_raw, length=3)
        scaled_positions.append(
            [
                _finite_real(f"scaled_positions[{row_index}][{column_index}]", item)
                for column_index, item in enumerate(row)
            ]
        )

    pbc_raw = _sequence("pbc", stored["pbc"], length=3)
    if any(not isinstance(item, bool) for item in pbc_raw):
        raise TypeError("Current atoms payload pbc values must be booleans.")
    pbc = [bool(item) for item in pbc_raw]

    info_raw = stored.get("info")
    info: dict[str, Any] | None = None
    if info_raw is not None:
        if not isinstance(info_raw, Mapping):
            raise TypeError("Current atoms payload info must be a mapping.")
        info = {}
        for key, item in info_raw.items():
            if not isinstance(key, str) or not key.startswith("calm"):
                raise ValueError(
                    "Current atoms payload info keys must be CALM-owned strings."
                )
            info[key] = json_native(item, path=f"$.info.{key}")

    result: dict[str, Any] = {
        "numbers": numbers,
        "cell": cell,
        "scaled_positions": scaled_positions,
        "pbc": pbc,
    }
    if info is not None:
        result["info"] = info
    return result


def _sanitize_for_json(
    obj: Any,
    *,
    _depth: int = 0,
    _path: str = "$.info",
    _active: set[int] | None = None,
) -> Any:  # noqa: C901
    """Convert one CALM-owned provenance value to exact JSON primitives.

    Explicit representation adapters are supported, but adapter failures,
    non-finite values, cycles, and unsupported objects raise. Persisted
    provenance is never replaced by a string representation.
    """

    if _depth > 32:
        raise ValueError(f"CALM provenance at {_path} exceeds maximum nesting depth.")
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if not isfinite(obj):
            raise ValueError(f"CALM provenance value at {_path} must be finite.")
        return obj
    if isinstance(obj, np.generic):
        return _sanitize_for_json(
            obj.item(), _depth=_depth, _path=_path, _active=_active
        )
    if isinstance(obj, np.ndarray):
        return _sanitize_for_json(
            obj.tolist(), _depth=_depth + 1, _path=_path, _active=_active
        )
    if isinstance(obj, Path):
        return str(obj)

    active = set() if _active is None else _active
    identity = id(obj)
    if identity in active:
        raise ValueError(f"CALM provenance at {_path} contains a reference cycle.")

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        active.add(identity)
        try:
            return {
                field.name: _sanitize_for_json(
                    getattr(obj, field.name),
                    _depth=_depth + 1,
                    _path=f"{_path}.{field.name}",
                    _active=active,
                )
                for field in dataclasses.fields(obj)
            }
        finally:
            active.remove(identity)

    if isinstance(obj, Mapping):
        active.add(identity)
        try:
            out: dict[str, Any] = {}
            for key, value in obj.items():
                if not isinstance(key, str):
                    raise TypeError(
                        f"CALM provenance mapping key at {_path} must be a string."
                    )
                out[key] = _sanitize_for_json(
                    value,
                    _depth=_depth + 1,
                    _path=f"{_path}.{key}",
                    _active=active,
                )
            return out
        finally:
            active.remove(identity)

    if isinstance(obj, (list, tuple)):
        active.add(identity)
        try:
            return [
                _sanitize_for_json(
                    value,
                    _depth=_depth + 1,
                    _path=f"{_path}[{index}]",
                    _active=active,
                )
                for index, value in enumerate(obj)
            ]
        finally:
            active.remove(identity)

    for hook_name in ("to_payload", "to_json_dict", "model_dump", "dict"):
        hook = getattr(obj, hook_name, None)
        if not callable(hook):
            continue
        active.add(identity)
        try:
            converted = hook()
            if converted is obj:
                raise TypeError(
                    f"{type(obj).__name__}.{hook_name}() returned the original "
                    f"object at {_path}."
                )
            return _sanitize_for_json(
                converted,
                _depth=_depth + 1,
                _path=_path,
                _active=active,
            )
        finally:
            active.remove(identity)

    raise TypeError(
        "CALM provenance values must be JSON-native, NumPy carriers, paths, "
        "dataclasses, or expose an exact mapping conversion hook; unsupported "
        f"{type(obj).__name__} at {_path}."
    )


def atoms_to_dict(atoms: Any) -> dict[str, Any]:
    """Serialize an ASE ``Atoms`` object into CALM's exact current payload.

    Only CALM-owned ``Atoms.info`` keys are persisted. Their values must have an
    exact JSON representation; unsupported or failing provenance objects raise
    rather than being stringified.
    """

    dct: dict[str, Any] = {
        "numbers": atoms.numbers.tolist(),
        "cell": atoms.cell.tolist(),
        "scaled_positions": atoms.get_scaled_positions(wrap=False).tolist(),
        "pbc": atoms.pbc.tolist(),
    }

    info = getattr(atoms, "info", None)
    if info is not None and not isinstance(info, Mapping):
        raise TypeError("ASE Atoms.info must be a mapping.")
    if info:
        calm_info: dict[str, Any] = {}
        for key, value in info.items():
            if not isinstance(key, str) or not key.startswith("calm"):
                continue
            calm_info[key] = _sanitize_for_json(
                value,
                _path=f"$.info.{key}",
            )
        if calm_info:
            dct["info"] = calm_info

    return canonical_atoms_payload(dct)


def atoms_from_dict(value: Mapping[str, Any]):
    """Reconstruct ``ase.Atoms`` from one exact current CALM payload."""

    payload = canonical_atoms_payload(value)
    try:
        from ase import Atoms  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise optional_dependency_error(
            missing="ase",
            extra="science",
            symbol="persisted atom structure decoding",
        ) from exc

    atoms = Atoms(
        numbers=payload["numbers"],
        cell=payload["cell"],
        scaled_positions=payload["scaled_positions"],
        pbc=payload["pbc"],
    )
    info = payload.get("info")
    if info is not None:
        atoms.info.update(dict(info))
    return atoms


def dict_to_atoms(value: Any):
    """Decode current persisted atoms, returning ``None`` only for absence.

    ``None`` represents an explicitly absent structure. Any present non-current
    or malformed value raises instead of being converted into missing state.
    """

    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError("Current atoms payload must be a mapping or None.")
    return atoms_from_dict(value)
