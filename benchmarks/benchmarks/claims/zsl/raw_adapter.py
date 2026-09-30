"""Lossless JSON capture of pymatgen ``ZSLMatch`` records."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from ..schemas import RawExternalMatch


ZSL_CAPTURE_SUMMARY_SCHEMA = "calm.zsl_source_capture_summary/v1"
ZSL_TOOL_ID = "pymatgen_zsl"

# These are the scientific fields exposed by current pymatgen ``ZSLMatch``.
# They are captured explicitly even when ``as_dict()`` is also available so the
# output remains readable across pymatgen MSON schema changes.
_ZSL_MATCH_FIELDS = (
    "film_sl_vectors",
    "substrate_sl_vectors",
    "film_vectors",
    "substrate_vectors",
    "film_transformation",
    "substrate_transformation",
    "match_transformation",
    "match_area",
)


def _qualified_type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def json_compatible(value: Any, *, field_name: str = "value") -> Any:
    """Return a deterministic JSON-compatible representation.

    Known scientific values are converted without lossy stringification.
    Unknown objects are represented by their qualified type and ``repr`` so a
    capture never fails merely because a future pymatgen release adds metadata.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite float")
        return value
    if isinstance(value, np.generic):
        return json_compatible(value.item(), field_name=field_name)
    if isinstance(value, np.ndarray):
        return json_compatible(value.tolist(), field_name=field_name)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return json_compatible(dataclasses.asdict(value), field_name=field_name)
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            converted[key_text] = json_compatible(
                item,
                field_name=f"{field_name}.{key_text}",
            )
        return converted
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [
            json_compatible(item, field_name=f"{field_name}[{index}]")
            for index, item in enumerate(value)
        ]
    if hasattr(value, "as_dict") and callable(value.as_dict):
        try:
            return json_compatible(value.as_dict(), field_name=field_name)
        except Exception as exc:  # pragma: no cover - external-tool behavior
            return {
                "__type__": _qualified_type_name(value),
                "__repr__": repr(value),
                "__as_dict_error__": f"{type(exc).__name__}: {exc}",
            }
    return {
        "__type__": _qualified_type_name(value),
        "__repr__": repr(value),
    }


def raw_match_id(*, fixture_id: str, run_id: str, raw_index: int) -> str:
    """Return a stable identifier local to one captured ZSL invocation."""

    if raw_index < 0:
        raise ValueError("raw_index must be nonnegative")
    if not fixture_id.strip() or not run_id.strip():
        raise ValueError("fixture_id and run_id must be nonempty")
    return f"pymatgen_zsl:{fixture_id}:{run_id}:{raw_index}"


def _read_field(match: Any, name: str) -> tuple[bool, Any, str | None]:
    if isinstance(match, Mapping) and name in match:
        return True, match[name], "mapping"
    if hasattr(match, name):
        try:
            return True, getattr(match, name), "attribute"
        except Exception as exc:  # pragma: no cover - external property failure
            return (
                False,
                {
                    "error": f"{type(exc).__name__}: {exc}",
                    "field": name,
                },
                "attribute_error",
            )
    return False, None, None


def _mson_payload(match: Any) -> tuple[Any | None, str | None]:
    if not hasattr(match, "as_dict") or not callable(match.as_dict):
        return None, None
    try:
        return json_compatible(match.as_dict(), field_name="mson_payload"), None
    except Exception as exc:  # pragma: no cover - external-tool behavior
        return None, f"{type(exc).__name__}: {exc}"


def capture_raw_zsl_match(
    match: Any,
    *,
    tool_version: str,
    fixture_id: str,
    run_id: str,
    raw_index: int,
    generator_settings: Mapping[str, Any],
    invocation: Mapping[str, Any],
) -> RawExternalMatch:
    """Capture one external match before any CALM-specific normalization."""

    source_match_id = raw_match_id(
        fixture_id=fixture_id,
        run_id=run_id,
        raw_index=raw_index,
    )
    fields: dict[str, Any] = {}
    field_sources: dict[str, str] = {}
    missing_fields: list[str] = []
    field_errors: dict[str, Any] = {}
    for name in _ZSL_MATCH_FIELDS:
        present, value, source = _read_field(match, name)
        if present:
            fields[name] = json_compatible(value, field_name=name)
            if source is not None:
                field_sources[name] = source
        elif source == "attribute_error":
            field_errors[name] = json_compatible(value, field_name=name)
        else:
            missing_fields.append(name)

    mson_payload, mson_error = _mson_payload(match)
    payload: dict[str, Any] = {
        "source_match_id": source_match_id,
        "raw_type": _qualified_type_name(match),
        "generator_settings": json_compatible(
            dict(generator_settings),
            field_name="generator_settings",
        ),
        "invocation": json_compatible(dict(invocation), field_name="invocation"),
        "fields": fields,
        "field_sources": field_sources,
        "missing_fields": missing_fields,
        "field_errors": field_errors,
        "mson_payload": mson_payload,
        "mson_error": mson_error,
    }
    if isinstance(match, Mapping):
        payload["raw_mapping"] = json_compatible(match, field_name="raw_mapping")
    elif isinstance(match, Sequence) and not isinstance(
        match,
        (str, bytes, bytearray),
    ):
        payload["raw_sequence"] = json_compatible(
            match,
            field_name="raw_sequence",
        )

    return RawExternalMatch(
        tool=ZSL_TOOL_ID,
        tool_version=tool_version,
        fixture_id=fixture_id,
        raw_index=raw_index,
        payload=payload,
    )
