"""Shared reporting helpers for internal synchronous stage adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def summarize_stage_results(results: Any) -> dict[str, Any]:
    """Return result count and available status counts for one stage."""

    if not isinstance(results, (list, tuple)):
        return {"n_results": 0}
    summary: dict[str, Any] = {"n_results": len(results)}
    statuses: dict[str, int] = {}
    for result in results:
        if isinstance(result, Mapping):
            status = result.get("status") or result.get("state")
            if status is not None:
                statuses[str(status)] = statuses.get(str(status), 0) + 1
    if statuses:
        summary["statuses"] = statuses
    return summary
