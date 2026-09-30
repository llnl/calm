"""Typed collections for authoritative project persistence records."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

from calm.public.collections.base import _BaseCollection
from calm.public.records.campaign_views import (
    CAMPAIGN_RUN_VIEW_SPECS,
    normalize_campaign_run_row,
)
from calm.public.records.dataset_views import (
    DATASET_ITEM_VIEW_SPECS,
    normalize_dataset_item_row,
)
from calm.public.records.persistence_views import (
    ARTIFACT_VIEW_SPECS,
    EDGE_VIEW_SPECS,
    FOLLOWUP_VIEW_SPECS,
    RUN_VIEW_SPECS,
    SEARCH_VIEW_SPECS,
    normalize_artifact_row,
    normalize_edge_row,
    normalize_followup_row,
    normalize_run_row,
    normalize_search_row,
)
from calm.public.records.persistence import (
    ProjectArtifact,
    ProjectCampaignRun,
    ProjectDatasetItem,
    ProjectEdge,
    ProjectEnergyResult,
    ProjectFollowupResult,
    ProjectReferenceEnergyResult,
    ProjectRelaxationResult,
    ProjectThermodynamicResult,
    ProjectRun,
    ProjectSearch,
)
from calm.public.records.result_views import (
    RAW_ENERGY_RESULT_VIEW_SPECS,
    REFERENCE_ENERGY_RESULT_VIEW_SPECS,
    RELAXATION_RESULT_VIEW_SPECS,
    THERMODYNAMIC_RESULT_VIEW_SPECS,
)


class SearchCollection(_BaseCollection):
    """Provide typed, chainable access to persisted search records.

    Positional ``get()`` resolves a unique search by name, scientific
    identity, short run ID, or full run UID. Keyword filters use the shared
    collection query interface. Ambiguous matches raise rather than selecting
    an arbitrary record.
    """

    _view_specs = SEARCH_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectSearch:
        return (
            item if isinstance(item, ProjectSearch) else ProjectSearch.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_search_row(self._public_item(item))

    def _clone(self, items):
        return SearchCollection(items)

    def get(self, *args, **filters):
        if args:
            needle = str(args[0])
            matches = [
                item
                for item in self.records()
                if needle
                in {
                    item.name,
                    str(item.search_identity or ""),
                    str(item.id_short or ""),
                    str(item.uid_full or ""),
                }
            ]
            if not matches:
                raise KeyError(f"No persisted search matches {needle!r}.")
            if len(matches) > 1:
                from calm.public.errors import AmbiguousProjectQueryError

                raise AmbiguousProjectQueryError(
                    f"Multiple persisted searches match {needle!r}; use a full run UID."
                )
            return matches[0]
        return super().get(**filters)


class RunCollection(_BaseCollection):
    """Provide typed, chainable access to authoritative workflow runs.

    Use ``type()``, ``status()``, or the shared collection filters to create
    read-only subsets without mutating persisted run state.
    """

    _view_specs = RUN_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectRun:
        return item if isinstance(item, ProjectRun) else ProjectRun.from_item(item)

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_run_row(self._public_item(item))

    def _clone(self, items):
        return RunCollection(items)

    def type(self, run_type: str):
        return self.where(run_type=run_type)

    def status(self, status: str):
        return self.where(status=status)


class FollowupCollection(_BaseCollection):
    """Provide typed, chainable access to authoritative follow-up results.

    The collection supports kind and status filters and can isolate structured
    failures while preserving the underlying persisted records.
    """

    _view_specs = FOLLOWUP_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectFollowupResult:
        return (
            item
            if isinstance(item, ProjectFollowupResult)
            else ProjectFollowupResult.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_followup_row(self._public_item(item))

    def _clone(self, items):
        return FollowupCollection(items)

    def kind(self, kind: str):
        return self.where(kind=kind)

    def status(self, status: str):
        return self.where(status=status)

    def failures(self):
        return self._clone(
            [item for item in self.records() if item.failure is not None]
        )


class RelaxationResultCollection(_BaseCollection):
    """Typed collection of authoritative structural-relaxation results."""

    _view_specs = RELAXATION_RESULT_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectRelaxationResult:
        return (
            item
            if isinstance(item, ProjectRelaxationResult)
            else ProjectRelaxationResult.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return self._public_item(item).to_dict()

    def _clone(self, items):
        return RelaxationResultCollection(items)

    def failures(self):
        return self._clone(
            [item for item in self.records() if item.failure is not None]
        )

    def completed(self):
        return self._clone([item for item in self.records() if item.succeeded])


class EnergyResultCollection(_BaseCollection):
    """Typed collection of authoritative raw total-energy results."""

    _view_specs = RAW_ENERGY_RESULT_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectEnergyResult:
        return (
            item
            if isinstance(item, ProjectEnergyResult)
            else ProjectEnergyResult.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return self._public_item(item).to_dict()

    def _clone(self, items):
        return EnergyResultCollection(items)

    def failures(self):
        return self._clone(
            [item for item in self.records() if item.failure is not None]
        )

    def completed(self):
        return self._clone([item for item in self.records() if item.succeeded])

    def interface(self, identifier: str):
        """Return results whose authoritative target matches *identifier*."""
        needle = str(identifier)
        return self._clone(
            [
                item
                for item in self.records()
                if needle
                in {
                    str(item.target_uid_full or ""),
                    str(item.metadata.get("interface_id") or ""),
                    str(item.metadata.get("interface_uid") or ""),
                    str(item.metadata.get("build_uid") or ""),
                }
            ]
        )

    def plot_distribution(
        self,
        *,
        metric: str = "energy_eV",
        bins: int = 20,
        save: str | Path | None = None,
        **kwargs,
    ):
        """Plot a finite scalar field from authoritative energy rows."""
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:  # pragma: no cover - optional dependency
            from calm.public.errors import CalmDependencyError

            raise CalmDependencyError(
                "Energy plotting requires matplotlib. Install it with "
                "'pip install matplotlib'."
            ) from exc
        values: list[float] = []
        for row in self.to_rows(view="all"):
            payload = row.get("payload")
            value = row.get(metric)
            if value is None and isinstance(payload, dict):
                value = payload.get(metric)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            numeric = float(value)
            if math.isfinite(numeric):
                values.append(numeric)
        fig, ax = plt.subplots()
        ax.hist(values, bins=max(1, int(bins)))
        ax.set_xlabel(metric)
        ax.set_ylabel("count")
        fig.tight_layout()
        if save is not None:
            path = Path(save)
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path, **kwargs)
        return fig, ax

    def plot_energy_vs_strain(
        self,
        *,
        x: str = "max_principal_strain",
        y: str = "energy_eV",
        save: str | Path | None = None,
        **kwargs,
    ):
        """Plot one finite energy field against one finite strain field."""
        try:
            import matplotlib.pyplot as plt
        except ImportError as exc:  # pragma: no cover - optional dependency
            from calm.public.errors import CalmDependencyError

            raise CalmDependencyError(
                "Energy plotting requires matplotlib. Install it with "
                "'pip install matplotlib'."
            ) from exc
        xs: list[float] = []
        ys: list[float] = []
        for row in self.to_rows(view="all"):
            payload = row.get("payload")
            x_value = row.get(x)
            y_value = row.get(y)
            if isinstance(payload, dict):
                if x_value is None:
                    x_value = payload.get(x)
                if y_value is None:
                    y_value = payload.get(y)
            if (
                isinstance(x_value, bool)
                or isinstance(y_value, bool)
                or not isinstance(x_value, (int, float))
                or not isinstance(y_value, (int, float))
            ):
                continue
            x_numeric = float(x_value)
            y_numeric = float(y_value)
            if not (math.isfinite(x_numeric) and math.isfinite(y_numeric)):
                continue
            xs.append(x_numeric)
            ys.append(y_numeric)
        fig, ax = plt.subplots()
        ax.scatter(xs, ys)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        fig.tight_layout()
        if save is not None:
            path = Path(save)
            path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(path, **kwargs)
        return fig, ax


class ReferenceEnergyResultCollection(_BaseCollection):
    """Typed collection of authoritative per-interface reference energies."""

    _view_specs = REFERENCE_ENERGY_RESULT_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectReferenceEnergyResult:
        return (
            item
            if isinstance(item, ProjectReferenceEnergyResult)
            else ProjectReferenceEnergyResult.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return self._public_item(item).to_dict()

    def _clone(self, items):
        return ReferenceEnergyResultCollection(items)

    def failures(self):
        return self._clone(
            [item for item in self.records() if item.failure is not None]
        )

    def completed(self):
        return self._clone([item for item in self.records() if item.succeeded])

    def reference_kind(self, kind: str):
        return self.where(reference_kind=kind)

    def interface(self, identifier: str):
        return self.where(target_uid_full=str(identifier))


class ThermodynamicResultCollection(_BaseCollection):
    """Typed collection of authoritative derived thermodynamic quantities."""

    _view_specs = THERMODYNAMIC_RESULT_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectThermodynamicResult:
        return (
            item
            if isinstance(item, ProjectThermodynamicResult)
            else ProjectThermodynamicResult.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return self._public_item(item).to_dict()

    def _clone(self, items):
        return ThermodynamicResultCollection(items)

    def failures(self):
        return self._clone(
            [item for item in self.records() if item.failure is not None]
        )

    def completed(self):
        return self._clone([item for item in self.records() if item.succeeded])

    def quantity(self, quantity: str):
        return self.where(quantity=quantity)


class ArtifactCollection(_BaseCollection):
    """Provide typed, read-only access to authoritative run artifacts.

    Collection operations normalize stored rows to ``ProjectArtifact``
    records and preserve their project-relative URIs and provenance.
    """

    _view_specs = ARTIFACT_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectArtifact:
        return (
            item
            if isinstance(item, ProjectArtifact)
            else ProjectArtifact.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_artifact_row(self._public_item(item))

    def _clone(self, items):
        return ArtifactCollection(items)


class EdgeCollection(_BaseCollection):
    """Provide typed, read-only access to authoritative provenance edges.

    Collection operations normalize stored rows to ``ProjectEdge`` records
    for filtering, tabulation, and lineage inspection.
    """

    _view_specs = EDGE_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectEdge:
        return item if isinstance(item, ProjectEdge) else ProjectEdge.from_item(item)

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_edge_row(self._public_item(item))

    def _clone(self, items):
        return EdgeCollection(items)


class DatasetItemCollection(_BaseCollection):
    """Provide typed access to authoritative dataset membership records.

    The collection supports full, summary, and learning-data projections plus
    deterministic split and leakage-group filters. Grouping operations return new
    collections and do not alter membership.
    """

    _default_view = "summary"
    _view_specs = DATASET_ITEM_VIEW_SPECS

    def __init__(
        self,
        items: Iterable[Any] | None = None,
        *,
        learning_columns: Iterable[str] | None = None,
    ):
        self._items = list(items or [])
        self._learning_columns = tuple(learning_columns or ())

    def _public_item(self, item: Any) -> ProjectDatasetItem:
        return (
            item
            if isinstance(item, ProjectDatasetItem)
            else ProjectDatasetItem.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_dataset_item_row(self._public_item(item))

    def _clone(self, items):
        return DatasetItemCollection(
            items,
            learning_columns=self._learning_columns,
        )

    def to_rows(self, *, view: str = "summary") -> list[dict[str, Any]]:
        """Return homogeneous rows for one validated dataset-item view."""

        return self._resolve_projection(view=view).to_rows()

    def _extra_columns_for_view(self, view: str) -> tuple[str, ...]:
        if view == "learning":
            return self._learning_columns
        return ()

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        rows = [self._normalize_item(item) for item in self._items]
        if view == "learning":
            from calm.public.records.dataset_learning import learning_row_projection

            return [learning_row_projection(row) for row in rows]
        return rows

    def split(self, name: str):
        canonical = str(name).strip().lower()
        if canonical not in {"train", "validation", "test"}:
            raise ValueError("split name must be 'train', 'validation', or 'test'.")
        return self.where(split=canonical)

    def group(self, group_id: str):
        return self.where(group_id=str(group_id))

    def groups(self) -> dict[str, "DatasetItemCollection"]:
        grouped: dict[str, list[Any]] = {}
        for item in self._items:
            record = self._public_item(item)
            if record.group_id is None:
                continue
            grouped.setdefault(record.group_id, []).append(item)
        return {
            key: DatasetItemCollection(
                values,
                learning_columns=self._learning_columns,
            )
            for key, values in grouped.items()
        }


class CampaignRunCollection(_BaseCollection):
    """Provide typed, read-only access to persisted campaign runs.

    The collection normalizes campaign-run rows and supports shared filters plus a
    convenience status filter.
    """

    _view_specs = CAMPAIGN_RUN_VIEW_SPECS

    def __init__(self, items: Iterable[Any] | None = None):
        self._items = list(items or [])

    def _public_item(self, item: Any) -> ProjectCampaignRun:
        return (
            item
            if isinstance(item, ProjectCampaignRun)
            else ProjectCampaignRun.from_item(item)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_campaign_run_row(self._public_item(item))

    def _clone(self, items):
        return CampaignRunCollection(items)

    def status(self, status: str):
        return self.where(status=status)
