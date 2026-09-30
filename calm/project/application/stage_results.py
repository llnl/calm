"""Exact JSON projection for current typed application-stage results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any


_COMMON_FIELDS = frozenset(
    {
        "prototype_uid",
        "status",
        "run_uid",
        "followup_uid",
        "reason",
        "derived_interface_uid",
        "relaxed_interface_uid",
        "artifact_refs",
    }
)


def normalize_stage_results(results: Iterable[Any]) -> list[dict[str, Any]]:
    """Project current stage dataclasses or mapping test doubles to JSON rows."""

    return [_normalize_stage_result(result) for result in results]


def _normalize_stage_result(result: Any) -> dict[str, Any]:
    if isinstance(result, Mapping):
        row = dict(result)
    elif is_dataclass(result) and not isinstance(result, type):
        row = asdict(result)
    else:
        raise TypeError(
            "Stage results must be dataclass instances or mappings; "
            f"received {type(result).__name__}."
        )

    if "prototype_uid" not in row:
        raise ValueError("Every stage result must define prototype_uid.")

    prototype_uid = row.get("prototype_uid")
    if prototype_uid is not None:
        prototype_uid = str(prototype_uid)
        row["prototype_uid"] = prototype_uid

    target_uid = row.get("target_uid")
    if target_uid is None:
        target_uid = prototype_uid
    target_uid = None if target_uid is None else str(target_uid)

    target_kind = row.get("target_kind")
    if target_kind is None and target_uid is not None:
        target_kind = "prototype"
    target_kind = None if target_kind is None else str(target_kind)

    if target_kind == "prototype" and target_uid == prototype_uid:
        row.pop("target_uid", None)
        row.pop("target_kind", None)
    else:
        row["target_uid"] = target_uid
        row["target_kind"] = target_kind

    status = row.get("status")
    if status is None:
        raise ValueError("Every stage result must define status.")
    row["status"] = str(status)

    run_uid = row.get("run_uid")
    if run_uid is not None:
        row["run_uid"] = str(run_uid)
    else:
        row.setdefault("run_uid", None)

    artifact_refs = row.get("artifact_refs")
    if artifact_refs is not None:
        if not isinstance(artifact_refs, (list, tuple)):
            raise TypeError("artifact_refs must be a list, tuple, or None.")
        row["artifact_refs"] = list(artifact_refs)

    row.setdefault("followup_uid", None)
    row.setdefault("derived_interface_uid", None)
    row.setdefault("relaxed_interface_uid", None)
    row.setdefault("artifact_refs", None)
    row.setdefault("reason", None)

    for key in tuple(row):
        if key not in _COMMON_FIELDS and row[key] is None:
            del row[key]

    return row


__all__ = ["normalize_stage_results"]
