"""Calculator specification dataclasses and serialization helpers.

This module defines :class:`CalculatorSpec`, a JSON-serializable value object
used to describe which calculator provider/model/options to use. The class
provides deterministic serialization and a stable fingerprint for provenance.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import types
from dataclasses import dataclass, field
from typing import Any, Mapping

from calm.keys.uid import canonical_json

from ._typing import JsonDict, JsonValue
from .exceptions import CalculatorSpecError

_SPEC_SCHEMA_VERSION = 1
_DEFAULT_FLOAT_DECIMALS = 12
_SPEC_FIELDS = frozenset(
    {
        "schema_version",
        "family",
        "model",
        "version",
        "source",
        "device",
        "dtype",
        "options",
    }
)


def _normalize_family(value: object) -> str:
    if not isinstance(value, str):
        raise CalculatorSpecError("CalculatorSpec.family must be a string.")
    if not value:
        raise CalculatorSpecError("CalculatorSpec.family must be a non-empty string.")
    if value != value.strip():
        raise CalculatorSpecError(
            "CalculatorSpec.family must not contain surrounding whitespace."
        )
    if value != value.lower():
        raise CalculatorSpecError(
            "CalculatorSpec.family must use its canonical lowercase identifier."
        )
    return value


def _normalize_model(value: object) -> str:
    if not isinstance(value, str):
        raise CalculatorSpecError("CalculatorSpec.model must be a string.")
    if not value:
        raise CalculatorSpecError("CalculatorSpec.model must be a non-empty string.")
    if value != value.strip():
        raise CalculatorSpecError(
            "CalculatorSpec.model must not contain surrounding whitespace."
        )
    return value


def _normalize_optional_str(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CalculatorSpecError(f"CalculatorSpec.{name} must be a string or None.")
    s = value.strip()
    return s if s else None


def _freeze_json_value(value: Any, *, path: str) -> JsonValue:
    """
    Return an immutable representation of a JSON-like value:
      - dicts are copied and wrapped in MappingProxyType
      - lists/tuples become tuples
      - primitives are returned as-is

    Raises:
        CalculatorSpecError if a value is not JSON-like.
    """
    if isinstance(value, float) and not math.isfinite(value):
        raise CalculatorSpecError(
            f"CalculatorSpec contains a non-finite float at {path}: {value!r}."
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # dict-like
    if isinstance(value, Mapping):
        out: dict[str, JsonValue] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise CalculatorSpecError(
                    f"CalculatorSpec options must have string keys; got key={k!r} "
                    f"({type(k).__name__}) at {path}."
                )
            out[k] = _freeze_json_value(v, path=f"{path}.{k}")
        return types.MappingProxyType(out)

    # list-like
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json_value(v, path=f"{path}[{i}]") for i, v in enumerate(value)
        )

    raise CalculatorSpecError(
        f"CalculatorSpec contains a non-JSON-serializable value at {path}: "
        f"{value!r} ({type(value).__name__})."
    )


def _thaw_json_value(value: JsonValue) -> JsonValue:
    """
    Convert the frozen JSON-like representation back into a JSON-serializable form:
      - mappings -> dict
      - tuples/lists -> list
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Mapping):
        return {str(k): _thaw_json_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_thaw_json_value(v) for v in value]

    # Should not happen because we only store JsonValue.
    raise TypeError(f"Unexpected JSON value type: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class CalculatorSpec:
    """
    Value object describing *which* calculator / MLIP model to use.

    Design goals:
      - JSON-serializable (for storage in SQLite and atoms.info)
      - Deterministic fingerprint (for provenance and caching)
      - Minimal, extensible core fields with provider-specific `options`
    """

    family: str
    model: str
    version: str | None = None
    source: str | None = None
    device: str | None = None
    dtype: str | None = None
    options: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _normalize_family(self.family))
        object.__setattr__(self, "model", _normalize_model(self.model))
        object.__setattr__(
            self,
            "version",
            _normalize_optional_str("version", self.version),
        )
        object.__setattr__(
            self,
            "source",
            _normalize_optional_str("source", self.source),
        )
        object.__setattr__(
            self,
            "device",
            _normalize_optional_str("device", self.device),
        )
        object.__setattr__(
            self,
            "dtype",
            _normalize_optional_str("dtype", self.dtype),
        )

        opts = self.options
        if not isinstance(opts, Mapping):
            raise CalculatorSpecError(
                "CalculatorSpec.options must be a mapping of str -> JSON-like values."
            )

        frozen = _freeze_json_value(opts, path="options")
        if not isinstance(frozen, Mapping):
            raise CalculatorSpecError(
                "CalculatorSpec.options must freeze to a mapping."
            )
        object.__setattr__(self, "options", frozen)

    def to_dict(self) -> JsonDict:
        """Convert to a JSON-compatible dict (including schema_version)."""
        options = _thaw_json_value(self.options)
        if not isinstance(options, dict):
            raise CalculatorSpecError(
                "Internal error: options did not thaw into a dict."
            )
        return {
            "schema_version": _SPEC_SCHEMA_VERSION,
            "family": self.family,
            "model": self.model,
            "version": self.version,
            "source": self.source,
            "device": self.device,
            "dtype": self.dtype,
            "options": options,
        }

    def options_dict(self) -> JsonDict:
        """Return provider options as a deep-copied, JSON-serializable dict."""
        opts = self.to_dict()["options"]
        if not isinstance(opts, dict):
            raise CalculatorSpecError("Internal error: options is not a dict.")
        return dict(opts)

    def to_json(self, *, float_decimals: int = _DEFAULT_FLOAT_DECIMALS) -> str:
        """Deterministic JSON serialization using calm's canonical JSON encoding."""
        payload = self.to_dict()
        try:
            return canonical_json(payload, float_decimals=int(float_decimals))
        except Exception as e:
            raise CalculatorSpecError(
                f"Failed to serialize CalculatorSpec to JSON: {e}"
            ) from e

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CalculatorSpec":
        if not isinstance(data, Mapping):
            raise CalculatorSpecError(
                f"CalculatorSpec.from_dict expected a mapping, got {type(data).__name__}."
            )

        unexpected = sorted(set(data) - _SPEC_FIELDS)
        if unexpected:
            raise CalculatorSpecError(
                f"CalculatorSpec contains unsupported field(s): {unexpected}."
            )

        schema_version = data.get("schema_version", _SPEC_SCHEMA_VERSION)
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise CalculatorSpecError(
                f"Invalid CalculatorSpec schema_version={schema_version!r}; expected an int."
            )

        if schema_version != _SPEC_SCHEMA_VERSION:
            raise CalculatorSpecError(
                f"Unsupported CalculatorSpec schema_version={schema_version!r}; expected {_SPEC_SCHEMA_VERSION}."
            )

        return cls(
            family=data.get("family"),
            model=data.get("model"),
            version=data.get("version"),
            source=data.get("source"),
            device=data.get("device"),
            dtype=data.get("dtype"),
            options=data.get("options", {}),
        )

    @classmethod
    def from_json(cls, payload: str) -> "CalculatorSpec":
        if not isinstance(payload, str) or not payload.strip():
            raise CalculatorSpecError(
                "CalculatorSpec.from_json expected a non-empty JSON string."
            )
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise CalculatorSpecError(f"Invalid CalculatorSpec JSON: {e}") from e
        if not isinstance(data, Mapping):
            raise CalculatorSpecError(
                f"CalculatorSpec JSON must decode to an object; got {type(data).__name__}."
            )
        return cls.from_dict(data)

    def fingerprint(self, *, float_decimals: int = _DEFAULT_FLOAT_DECIMALS) -> str:
        """Stable identifier for provenance (SHA256 hex digest of canonical JSON)."""
        return hashlib.sha256(
            self.to_json(float_decimals=float_decimals).encode("utf-8")
        ).hexdigest()

    def label(self) -> str:
        """Human-readable short label (not guaranteed unique)."""
        parts = [self.family, self.model]
        if self.version:
            parts.append(f"v={self.version}")
        if self.device:
            parts.append(f"dev={self.device}")
        if self.dtype:
            parts.append(f"dtype={self.dtype}")
        return " | ".join(parts)

    def replace(self, **changes: Any) -> "CalculatorSpec":
        """Return a new spec with fields replaced (like dataclasses.replace)."""
        try:
            return dataclasses.replace(self, **changes)
        except TypeError as e:
            raise CalculatorSpecError(str(e)) from e
