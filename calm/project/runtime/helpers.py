from __future__ import annotations

from typing import Any, Mapping, Optional


def merge_payload(
    *,
    payload: Optional[Mapping[str, Any]] = None,
    label: str | None = None,
) -> dict[str, Any] | None:
    """Merge the current UX payload and optional presentation label."""
    base: dict[str, Any] = {}
    if payload is not None:
        base.update(dict(payload))
    if label is not None:
        base.setdefault("label", label)
    return base or None
