from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from calm.serialization.json import canonical_json

from calm.serialization.regression import sha256_hex


def _validate_json_value(value: Any, *, path: str) -> None:
    """Reject values that JSON would coerce or represent non-finitely."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"{path} must be finite.")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings.")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise TypeError(
        f"{path} must contain only JSON-native values; got {type(value).__name__}."
    )


def payload_canonical_json_and_hash(
    payload_obj: dict[str, Any] | None,
) -> tuple[str, str]:
    """Return the exact canonical JSON and hash for one edge payload.

    Provenance payloads are current-schema data, not a best-effort reporting
    surface. Invalid or coercive values therefore raise before any row is
    written instead of being replaced or silently converted.
    """

    payload = {} if payload_obj is None else payload_obj
    if not isinstance(payload, dict):
        raise TypeError("Edge payload must be a dictionary or None.")
    _validate_json_value(payload, path="Edge payload")

    canonical = canonical_json(payload)
    return canonical, sha256_hex(canonical)


def extract_canonical_tilt_metadata(payload: Any) -> dict[str, Any] | None:
    """Return ``payload['atoms']['info']['calm:tilt']`` when present.

    The current slab writer stores tilt provenance at exactly this location.
    Historical atoms-level and top-level layouts are intentionally rejected by
    the repository rather than interpreted as current data.
    """

    if not isinstance(payload, Mapping):
        return None

    atoms = payload.get("atoms")
    if atoms is None:
        return None
    if not isinstance(atoms, Mapping):
        raise TypeError("Slab payload 'atoms' must be a mapping.")

    info = atoms.get("info")
    if info is None:
        return None
    if not isinstance(info, Mapping):
        raise TypeError("Slab payload atoms 'info' must be a mapping.")

    tilt = info.get("calm:tilt")
    if tilt is None:
        return None
    if not isinstance(tilt, Mapping):
        raise TypeError("Slab payload 'calm:tilt' metadata must be a mapping.")
    return dict(tilt)
