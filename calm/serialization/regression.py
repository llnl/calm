"""Deterministic signatures / fingerprints for regression testing.

The primary goal of this module is to provide:

1. A canonical JSON serialization for nested python structures that may contain
   numpy scalars/arrays and dataclasses.
2. A stable SHA-256 fingerprint built from that serialization.

This module retains the historical version-1 regression normalization contract.
It is separate from scientific and persistence identity and is not an alias for
the type-tagged canonical identity serialization version 2.

These utilities are intended for:

- CI regression tests ("did anything change?")
- reproducibility artifacts ("what exact set of candidates did I get?")

They should *not* be used for core algorithmic decisions (pruning, ranking,
matching) because they introduce hidden rounding/tolerance behavior.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

import numpy as np


def _normalize_for_json(obj: Any, *, float_ndigits: int) -> Any:
    """Normalize an object into JSON-serializable primitives."""

    # dataclasses -> dict
    if dataclasses.is_dataclass(obj):
        return _normalize_for_json(dataclasses.asdict(obj), float_ndigits=float_ndigits)

    # numpy arrays/scalars
    if isinstance(obj, np.ndarray):
        return _normalize_for_json(obj.tolist(), float_ndigits=float_ndigits)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        obj = float(obj)

    # floats (including those coerced from numpy)
    if isinstance(obj, float):
        if not np.isfinite(obj):
            # JSON has no NaN/Inf: encode as strings for deterministic debug.
            return "NaN" if np.isnan(obj) else ("+Inf" if obj > 0 else "-Inf")
        return float(round(obj, int(float_ndigits)))

    # common containers
    if isinstance(obj, dict):
        # enforce string keys for JSON + deterministic ordering via sort_keys later
        out: dict[str, Any] = {}
        for k, v in obj.items():
            out[str(k)] = _normalize_for_json(v, float_ndigits=float_ndigits)
        return out
    if isinstance(obj, (list, tuple)):
        normalized_list: list[Any] = []
        for v in obj:
            normalized_list.append(_normalize_for_json(v, float_ndigits=float_ndigits))
        return normalized_list

    # cheap coercions
    if isinstance(obj, (int, str, bool)) or obj is None:
        return obj

    # fallback: try stringification (still deterministic)
    return str(obj)


def deterministic_json(obj: Any, *, float_ndigits: int = 12) -> str:
    """Serialize ``obj`` with the frozen version-1 regression JSON contract.

    Parameters
    ----------
    obj
        Any nested structure of dict/list/tuple/scalars/np.ndarray/dataclasses.
    float_ndigits
        Number of decimal digits to retain when serializing floats.
    """

    normalized = _normalize_for_json(obj, float_ndigits=int(float_ndigits))
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def fingerprint_json(obj: Any, *, float_ndigits: int = 12) -> str:
    """Return a version-1 regression fingerprint of ``deterministic_json``."""

    s = deterministic_json(obj, float_ndigits=int(float_ndigits))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def sha256_hex(data: str | bytes) -> str:
    """Return the SHA-256 hex digest of *data*.

    Parameters
    ----------
    data
        Text (encoded as UTF-8) or raw bytes.
    """

    if isinstance(data, str):
        b = data.encode("utf-8")
    else:
        b = data
    return hashlib.sha256(b).hexdigest()
