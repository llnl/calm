"""Named-view contracts for general persisted project records.

These projections replace the retired renderer table presets. Scientific and
provenance fields are normalized before rendering so the renderer only formats
values and never selects or derives domain columns.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calm.project.ports.ids import format_short_id
from calm.public.collections.views import ViewSpec


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        row = converter()
        if not isinstance(row, Mapping):
            raise TypeError("to_dict() must return a mapping.")
        return dict(row)
    state = getattr(value, "__dict__", None)
    if isinstance(state, dict):
        return {
            str(key): item
            for key, item in state.items()
            if not str(key).startswith("_")
        }
    raise TypeError(f"Cannot normalize {type(value).__name__} as a persisted row.")


_UID_TAGS = {
    "artifact": "a",
    "bulk": "b",
    "calc": "c",
    "calculator": "c",
    "campaign": "c",
    "campaign_run": "r",
    "dataset": "d",
    "dataset_item": "t",
    "edge": "e",
    "followup": "f",
    "interface": "i",
    "proto": "p",
    "prototype": "p",
    "run": "r",
    "slab": "s",
    "surface": "s",
}


def _short_id(
    uid_full: Any,
    *,
    explicit: Any = None,
    kind: str | None = None,
) -> str | None:
    if explicit not in (None, ""):
        return str(explicit)
    if uid_full in (None, ""):
        return None
    uid = str(uid_full)
    prefix = str(kind or uid.split(":", 1)[0]).strip().lower()
    tag = _UID_TAGS.get(prefix, prefix[:1] or "x")
    return format_short_id(tag=tag, uid_full=uid)


SEARCH_SUMMARY_COLUMNS = (
    "id_short",
    "name",
    "status",
    "n_candidates",
    "created_at",
)
SEARCH_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "name",
    "search_identity",
    "run_uid_full",
    "run_id_short",
    "created_at",
    "updated_at",
    "authority",
)
SEARCH_ALL_BASE_COLUMNS = (
    "search_id",
    "search_name",
    "name",
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "search_identity",
    "status",
    "n_candidates",
    "settings",
    "spec",
    "progress",
    "failure",
    "created_at",
    "updated_at",
    "authority",
)
SEARCH_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=SEARCH_SUMMARY_COLUMNS,
        description="Concise persisted interface-search status summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=SEARCH_PROVENANCE_COLUMNS,
        description="Search identity, run lineage, timestamps, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=SEARCH_ALL_BASE_COLUMNS,
        aliases=("full",),
        allow_extra_columns=True,
        description="Complete normalized public search row.",
    ),
)


RUN_SUMMARY_COLUMNS = (
    "id_short",
    "run_type",
    "status",
    "created_at",
)
RUN_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_type",
    "status",
    "created_at",
    "updated_at",
    "authority",
)
RUN_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "run_type",
    "status",
    "spec",
    "progress",
    "failure",
    "created_at",
    "updated_at",
    "authority",
)
RUN_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=RUN_SUMMARY_COLUMNS,
        description="Concise workflow-run status and creation summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=RUN_PROVENANCE_COLUMNS,
        description="Run identity, lifecycle timestamps, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=RUN_ALL_COLUMNS,
        aliases=("full",),
        description="Complete normalized public run row.",
    ),
)


FOLLOWUP_SUMMARY_COLUMNS = (
    "id_short",
    "run_id_short",
    "target_kind",
    "target_id_short",
    "kind",
    "status",
    "best_energy",
    "n_points",
)
FOLLOWUP_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "prototype_id_short",
    "target_uid_full",
    "target_id_short",
    "target_kind",
    "kind",
    "created_at",
    "updated_at",
    "authority",
)
FOLLOWUP_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "kind",
    "status",
    "run_uid_full",
    "run_id_short",
    "prototype_uid_full",
    "prototype_id_short",
    "target_uid_full",
    "target_id_short",
    "target_kind",
    "best_energy",
    "param1",
    "param2",
    "alpha_opt",
    "shift_a",
    "shift_b",
    "n_points",
    "payload",
    "failure",
    "created_at",
    "updated_at",
    "authority",
)
FOLLOWUP_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=FOLLOWUP_SUMMARY_COLUMNS,
        description="Concise generic follow-up result and target summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=FOLLOWUP_PROVENANCE_COLUMNS,
        description="Follow-up run, target, timestamps, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=FOLLOWUP_ALL_COLUMNS,
        aliases=("full",),
        description="Complete normalized public follow-up result row.",
    ),
)


ARTIFACT_SUMMARY_COLUMNS = (
    "id_short",
    "run_id_short",
    "kind",
    "uri",
)
ARTIFACT_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "kind",
    "uri",
    "created_at",
    "authority",
)
ARTIFACT_ALL_COLUMNS = (
    "uid_full",
    "id_short",
    "run_uid_full",
    "run_id_short",
    "kind",
    "uri",
    "metadata",
    "created_at",
    "authority",
)
ARTIFACT_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=ARTIFACT_SUMMARY_COLUMNS,
        description="Concise run-artifact location summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=ARTIFACT_PROVENANCE_COLUMNS,
        description="Artifact identity, parent run, timestamp, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=ARTIFACT_ALL_COLUMNS,
        aliases=("full",),
        description="Complete normalized public artifact row.",
    ),
)


EDGE_SUMMARY_COLUMNS = (
    "src_id_short",
    "dst_id_short",
    "kind",
    "created_at",
)
EDGE_PROVENANCE_COLUMNS = (
    "uid_full",
    "src_uid_full",
    "src_id_short",
    "dst_uid_full",
    "dst_id_short",
    "kind",
    "created_at",
    "authority",
)
EDGE_ALL_COLUMNS = (
    "uid_full",
    "src_uid_full",
    "src_id_short",
    "dst_uid_full",
    "dst_id_short",
    "kind",
    "payload",
    "created_at",
    "authority",
)
EDGE_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=EDGE_SUMMARY_COLUMNS,
        description="Concise directed provenance-edge summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=EDGE_PROVENANCE_COLUMNS,
        description="Edge identity, durable endpoints, timestamp, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=EDGE_ALL_COLUMNS,
        aliases=("full",),
        description="Complete normalized public provenance-edge row.",
    ),
)


def normalize_search_row(value: Any) -> dict[str, Any]:
    return _mapping(value)


def normalize_run_row(value: Any) -> dict[str, Any]:
    return _mapping(value)


def normalize_followup_row(value: Any) -> dict[str, Any]:
    row = _mapping(value)
    row["run_id_short"] = _short_id(
        row.get("run_uid_full"),
        explicit=row.get("run_id_short"),
        kind="run",
    )
    target_kind = str(row.get("target_kind") or "").strip().lower() or None
    row["target_id_short"] = _short_id(
        row.get("target_uid_full"),
        explicit=row.get("target_id_short"),
        kind=target_kind,
    )
    kind = str(row.get("kind") or "")
    row["alpha_opt"] = row.get("param1") if kind == "strain_partition_scan" else None
    row["shift_a"] = row.get("param1") if kind == "registry_search" else None
    row["shift_b"] = row.get("param2") if kind == "registry_search" else None
    return row


def normalize_artifact_row(value: Any) -> dict[str, Any]:
    row = _mapping(value)
    row["run_id_short"] = _short_id(
        row.get("run_uid_full"),
        explicit=row.get("run_id_short"),
        kind="run",
    )
    return row


def normalize_edge_row(value: Any) -> dict[str, Any]:
    row = _mapping(value)
    row["src_id_short"] = _short_id(row.get("src_uid_full"))
    row["dst_id_short"] = _short_id(row.get("dst_uid_full"))
    return row
