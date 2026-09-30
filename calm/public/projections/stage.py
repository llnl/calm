"""Public projection helpers for current application-stage results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from calm.project.application.stage_results import normalize_stage_results


def expose_public_stage_targets(
    results: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return public stage rows with explicit target identity.

    Workspace stage adapters retain their established compact prototype-target
    envelope. The Project facade uses this projection so campaign and reopen
    workflows can inspect a uniform target identity without changing the lower-
    level Workspace return contract. Distinct interface targets already emitted
    by the application normalizer are preserved exactly.
    """

    rows: list[dict[str, Any]] = []
    for result in results:
        row = dict(result)
        prototype_uid = row.get("prototype_uid")
        if prototype_uid is not None and row.get("target_uid") is None:
            row["target_uid"] = str(prototype_uid)
            row["target_kind"] = "prototype"
        elif row.get("target_uid") is not None and row.get("target_kind") is None:
            row["target_kind"] = (
                "prototype"
                if str(row["target_uid"]) == str(prototype_uid)
                else "interface"
            )
        rows.append(row)
    return rows


__all__ = ["expose_public_stage_targets", "normalize_stage_results"]
