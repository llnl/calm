"""Shared named-view contracts for campaigns and campaign executions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from calm.public.collections.views import ViewSpec


CAMPAIGN_SUMMARY_COLUMNS = (
    "campaign_id",
    "name",
    "n_cases",
    "stages",
    "created_at",
)

CAMPAIGN_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "campaign_id",
    "name",
    "identity_version",
    "created_at",
    "authority",
)

CAMPAIGN_ALL_BASE_COLUMNS = (
    "uid_full",
    "id_short",
    "campaign_id",
    "name",
    "spec",
    "created_at",
    "authority",
)

CAMPAIGN_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=CAMPAIGN_SUMMARY_COLUMNS,
        description="Concise campaign declaration and stage summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=CAMPAIGN_PROVENANCE_COLUMNS,
        description="Campaign identity, specification version, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=CAMPAIGN_ALL_BASE_COLUMNS,
        aliases=("full",),
        allow_extra_columns=True,
        description="Complete normalized public campaign row.",
    ),
)


CAMPAIGN_RUN_SUMMARY_COLUMNS = (
    "run_id",
    "campaign_id",
    "status",
    "backend_id",
    "started_at",
    "finished_at",
)

CAMPAIGN_RUN_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_id",
    "campaign_uid_full",
    "campaign_id",
    "run_spec_hash",
    "backend_id",
    "status",
    "started_at",
    "finished_at",
    "authority",
)

CAMPAIGN_RUN_ALL_BASE_COLUMNS = (
    "uid_full",
    "id_short",
    "run_id",
    "campaign_uid_full",
    "campaign_id",
    "run_spec_hash",
    "backend_id",
    "status",
    "started_at",
    "finished_at",
    "authority",
)

CAMPAIGN_RUN_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=CAMPAIGN_RUN_SUMMARY_COLUMNS,
        description="Concise campaign-run status and timing summary.",
    ),
    ViewSpec(
        name="provenance",
        columns=CAMPAIGN_RUN_PROVENANCE_COLUMNS,
        description="Campaign-run identity, backend, hash, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=CAMPAIGN_RUN_ALL_BASE_COLUMNS,
        aliases=("full",),
        allow_extra_columns=True,
        description="Complete normalized public campaign-run row.",
    ),
)


CAMPAIGN_RESULT_SUMMARY_COLUMNS = (
    "campaign_name",
    "case_name",
    "search_name",
    "status",
    "dataset_name",
    "export_path",
    "failure_type",
    "failure_message",
)

CAMPAIGN_RESULT_PROVENANCE_COLUMNS = (
    "campaign_uid_full",
    "campaign_id_short",
    "campaign_name",
    "campaign_run_uid_full",
    "campaign_run_id_short",
    "case_name",
    "search_name",
    "dataset_uid_full",
    "dataset_id_short",
    "dataset_name",
    "export_path",
    "failure_type",
    "failure_message",
)

CAMPAIGN_RESULT_ALL_COLUMNS = (
    "case",
    "status",
    "stages",
    "dataset",
    "export_path",
    "failure",
    "campaign_uid_full",
    "campaign_run_uid_full",
)


_CAMPAIGN_COMPARISON_VIEW = ViewSpec(
    name="comparison",
    columns=CAMPAIGN_RESULT_SUMMARY_COLUMNS,
    allow_extra_columns=True,
    description="Grid dimensions and scalar stage metrics appended to the case summary.",
)

CAMPAIGN_COMPARISON_VIEW_SPECS = (_CAMPAIGN_COMPARISON_VIEW,)

CAMPAIGN_RESULT_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=CAMPAIGN_RESULT_SUMMARY_COLUMNS,
        description="Reader-facing campaign case execution summary.",
    ),
    _CAMPAIGN_COMPARISON_VIEW,
    ViewSpec(
        name="provenance",
        columns=CAMPAIGN_RESULT_PROVENANCE_COLUMNS,
        description="Campaign, run, dataset, export, and failure lineage.",
    ),
    ViewSpec(
        name="all",
        columns=CAMPAIGN_RESULT_ALL_COLUMNS,
        aliases=("full",),
        description="Complete nested campaign case result.",
    ),
)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    converter = getattr(value, "to_dict", None)
    if callable(converter):
        result = converter()
        if not isinstance(result, Mapping):
            raise TypeError("to_dict() must return a mapping.")
        return dict(result)
    state = getattr(value, "__dict__", None)
    if isinstance(state, dict):
        return {
            str(key): item
            for key, item in state.items()
            if not str(key).startswith("_")
        }
    raise TypeError(f"Cannot normalize {type(value).__name__} as a campaign row.")


def normalize_campaign_row(value: Any) -> dict[str, Any]:
    """Return one complete campaign row with reader-facing derived fields."""

    row = _mapping(value)
    spec = row.get("spec") if isinstance(row.get("spec"), Mapping) else {}
    settings = (
        spec.get("settings")
        if isinstance(spec.get("settings"), Mapping)
        else {}
    )
    cases = spec.get("cases")
    if isinstance(cases, Sequence) and not isinstance(
        cases, (str, bytes, bytearray)
    ):
        row["n_cases"] = len(cases)
    else:
        row.setdefault("n_cases", None)
    stages = settings.get("stages")
    if isinstance(stages, Sequence) and not isinstance(
        stages, (str, bytes, bytearray)
    ):
        row["stages"] = list(stages)
    else:
        row.setdefault("stages", None)
    row["identity_version"] = spec.get("identity_version")
    row["campaign_id"] = (
        row.get("id_short") or row.get("uid_full") or row.get("name")
    )
    row.setdefault("id", row.get("campaign_id"))
    return row


def normalize_campaign_run_row(value: Any) -> dict[str, Any]:
    """Return one complete campaign-run row with stable display aliases."""

    row = _mapping(value)
    row["run_id"] = row.get("id_short") or row.get("uid_full")
    row["campaign_id"] = (
        row.get("campaign_id_short")
        or row.get("campaign_uid_full")
        or row.get("campaign_id")
    )
    row.setdefault("id", row.get("run_id"))
    return row
