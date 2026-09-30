"""Shared static-validation helpers for performance contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("performance matrix must contain one JSON object")
    return value


def workload_mapping(
    payload: object,
    *,
    label: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    prefix = f"{label} " if label else ""
    if not isinstance(payload, list):
        errors.append(f"{prefix}workloads must be a list")
        return result
    for index, workload in enumerate(payload):
        if not isinstance(workload, dict):
            errors.append(f"{prefix}workloads[{index}] must be an object")
            continue
        identifier = str(workload.get("id", ""))
        if not identifier:
            errors.append(f"{prefix}workloads[{index}] has no id")
            continue
        if identifier in result:
            errors.append(f"duplicate {prefix}workload id {identifier!r}")
        result[identifier] = workload
    return result


def unique_string_fields(
    payload: object,
    *,
    label: str,
    errors: list[str],
) -> set[str]:
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list")
        return set()
    fields = {str(value) for value in payload}
    if len(fields) != len(payload):
        errors.append(f"{label} must be unique")
    return fields


def require_fragments(
    text: str,
    fragments: tuple[str, ...],
    *,
    label: str,
    errors: list[str],
) -> None:
    for fragment in fragments:
        if fragment not in text:
            errors.append(f"{label} is missing contract owner {fragment!r}")
