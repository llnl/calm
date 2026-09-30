"""Shared SQL repository projection helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def datetime_to_text(value: Any) -> str | None:
    """Project a SQL timestamp into the current domain text representation."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
