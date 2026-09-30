"""Shared named-view contracts for datasets and dataset membership."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calm.public.collections.views import ViewSpec


DATASET_SUMMARY_COLUMNS = (
    "dataset_id",
    "name",
    "schema_version",
    "n_items",
    "created_at",
)

DATASET_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "dataset_id",
    "name",
    "schema_version",
    "content_fingerprint",
    "created_at",
    "authority",
)

DATASET_ALL_BASE_COLUMNS = (
    "uid_full",
    "id_short",
    "dataset_id",
    "name",
    "description",
    "schema_version",
    "settings",
    "created_at",
    "authority",
)

DATASET_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=DATASET_SUMMARY_COLUMNS,
        description="Concise dataset identity, schema, and membership count.",
    ),
    ViewSpec(
        name="provenance",
        columns=DATASET_PROVENANCE_COLUMNS,
        description="Dataset identity, content fingerprint, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=DATASET_ALL_BASE_COLUMNS,
        aliases=("full",),
        allow_extra_columns=True,
        description="Complete normalized public dataset row.",
    ),
)


DATASET_ITEM_SUMMARY_COLUMNS = (
    "dataset_index",
    "source_id_short",
    "source_kind",
    "interface_id_short",
    "interface_label",
    "group_id",
    "split",
    "status",
)

DATASET_ITEM_PROVENANCE_COLUMNS = (
    "uid_full",
    "id_short",
    "dataset_uid_full",
    "dataset_index",
    "source_uid_full",
    "source_id_short",
    "source_kind",
    "run_uid_full",
    "interface_uid_full",
    "interface_id_short",
    "prototype_uid_full",
    "group_id",
    "split",
    "artifact_refs",
    "created_at",
    "authority",
)

DATASET_ITEM_LEARNING_BASE_COLUMNS = (
    "dataset_index",
    "source_id",
    "source_kind",
    "interface_id",
    "interface_label",
    "search_name",
    "group_id",
    "split",
)

DATASET_ITEM_ALL_BASE_COLUMNS = (
    "uid_full",
    "id_short",
    "dataset_uid_full",
    "dataset_index",
    "source_uid_full",
    "source_id_short",
    "source_kind",
    "terminal_source_kind",
    "run_uid_full",
    "interface_uid_full",
    "interface_id_short",
    "interface_label",
    "prototype_uid_full",
    "search_name",
    "group_id",
    "split",
    "status",
    "features",
    "targets",
    "artifact_refs",
    "created_at",
    "authority",
)

DATASET_ITEM_VIEW_SPECS = (
    ViewSpec(
        name="summary",
        columns=DATASET_ITEM_SUMMARY_COLUMNS,
        description="Concise dataset membership and split summary.",
    ),
    ViewSpec(
        name="learning",
        columns=DATASET_ITEM_LEARNING_BASE_COLUMNS,
        aliases=("features", "ml", "model"),
        allow_extra_columns=True,
        description="Declared feature and target columns for model development.",
    ),
    ViewSpec(
        name="provenance",
        columns=DATASET_ITEM_PROVENANCE_COLUMNS,
        description="Dataset membership, source lineage, artifacts, and authority.",
    ),
    ViewSpec(
        name="all",
        columns=DATASET_ITEM_ALL_BASE_COLUMNS,
        aliases=("full",),
        allow_extra_columns=True,
        description="Complete normalized public dataset-item row.",
    ),
)


def dataset_learning_columns(settings: Any) -> tuple[str, ...]:
    """Return the declared learning schema, including for an empty dataset."""

    if settings is None:
        return DATASET_ITEM_LEARNING_BASE_COLUMNS
    if isinstance(settings, Mapping):
        features = settings.get("features") or ()
        targets = settings.get("targets") or ()
    else:
        features = getattr(settings, "features", ()) or ()
        targets = getattr(settings, "targets", ()) or ()

    def _name(value: Any) -> str | None:
        if isinstance(value, Mapping):
            item = value.get("name")
        else:
            item = getattr(value, "name", None)
        if item in (None, ""):
            return None
        return str(item)

    extra = tuple(
        f"feature_{name}"
        for value in features
        if (name := _name(value)) is not None
    ) + tuple(
        f"target_{name}"
        for value in targets
        if (name := _name(value)) is not None
    )
    return (*DATASET_ITEM_LEARNING_BASE_COLUMNS, *extra)


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
    raise TypeError(f"Cannot normalize {type(value).__name__} as a dataset row.")


def normalize_dataset_row(value: Any) -> dict[str, Any]:
    """Return one complete dataset row with stable identity aliases."""

    row = _mapping(value)
    row["dataset_id"] = (
        row.get("id_short") or row.get("uid_full") or row.get("name")
    )
    row.setdefault("id", row.get("dataset_id"))
    return row


def normalize_dataset_item_row(value: Any) -> dict[str, Any]:
    """Return one complete dataset-item row with stable identity aliases."""

    row = _mapping(value)
    if row.get("dataset_index") is None:
        row["dataset_index"] = row.get("index")
    if row.get("source_id_short") is None:
        row["source_id_short"] = row.get("source_id")
    if row.get("interface_id_short") is None:
        row["interface_id_short"] = row.get("interface_id")
    row.setdefault("dataset_item_id", row.get("id_short") or row.get("uid_full"))
    row.setdefault("id", row.get("dataset_item_id"))
    return row
