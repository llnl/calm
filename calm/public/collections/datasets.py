"""Dataset public query collection."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from calm.public.collections.base import _BaseCollection
from calm.public.records.dataset_views import (
    DATASET_VIEW_SPECS,
    dataset_learning_columns,
    normalize_dataset_row,
)
from calm.public.records.persistence import ProjectDataset


class DatasetCollection(_BaseCollection):
    """Public query collection for authoritative persisted datasets."""

    _view_specs = DATASET_VIEW_SPECS

    _items_attr = "_datasets"

    def __init__(
        self,
        workspace: Any | None = None,
        datasets: Iterable[Any] | None = None,
        items: Iterable[Any] | None = None,
        repo: Any | None = None,
        project: Any | None = None,
    ):
        self._ws = workspace
        self._repo = repo
        self._project = project
        source = datasets if datasets is not None else items
        self._datasets = list(source) if source is not None else []
        self._loaded = source is not None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._repo is None:
            raise RuntimeError(
                "DatasetCollection requires an authoritative project repository."
            )
        self._datasets = list(self._repo.list_datasets(limit=500))
        self._loaded = True

    def _public_item(self, item: Any) -> ProjectDataset:
        if isinstance(item, ProjectDataset):
            if item._project is self._project or self._project is None:
                return item
            from dataclasses import replace

            return replace(item, _project=self._project)
        return ProjectDataset.from_item(item, project=self._project)

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        row = normalize_dataset_row(self._public_item(item))
        if self._repo is not None and row.get("authority") == "authoritative":
            identifier = row.get("uid_full") or row.get("id_short")
            if identifier:
                count = len(self._repo.list_dataset_items(str(identifier)))
                row.setdefault("n_items", count)
                row.setdefault("n_structures", count)
                if row.get("schema_version") in {
                    "calm.interface.v1",
                    "calm.interface_learning.v1",
                }:
                    row.setdefault("n_interfaces", count)
                if row.get("schema_version") == "calm.interface_learning.v1":
                    row.setdefault("n_learning_records", count)
        return row

    def _clone(self, items):
        return DatasetCollection(
            workspace=self._ws,
            datasets=items,
            repo=self._repo,
            project=self._project,
        )

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        del view
        self._ensure_loaded()
        return [self._normalize_item(item) for item in self._datasets]

    def items(self, dataset: str | None = None):
        """Return authoritative persisted item records for selected datasets."""
        from calm.public.collections.persistence import DatasetItemCollection

        self._ensure_loaded()
        selected = [self.get(dataset)] if dataset is not None else self.records()
        authoritative: list[Any] = []
        if self._repo is None:
            raise RuntimeError(
                "DatasetCollection requires an authoritative project repository."
            )
        learning_columns: list[str] = []
        seen_columns: set[str] = set()
        for record in selected:
            identifier = record.uid_full or record.id_short
            if identifier is None:
                raise RuntimeError(
                    "Authoritative dataset records must expose durable identity."
                )
            authoritative.extend(self._repo.list_dataset_items(identifier))
            for name in dataset_learning_columns(record.settings):
                if name not in seen_columns:
                    learning_columns.append(name)
                    seen_columns.add(name)
        return DatasetItemCollection(
            authoritative,
            learning_columns=learning_columns,
        )

    def to_item_rows(self, *, view: str = "all") -> list[dict[str, Any]]:
        return self.items().to_rows(view=view)

    def name(self, name: str):
        return self.where(name=name)

    def search(self, name: str | None = None, *, id: str | None = None):
        if name is None and id is None:
            return self
        filters = {}
        if name is not None:
            filters["search_name"] = name
        if id is not None:
            filters["search_id"] = id
        return self.where(**filters)

    def materials(self, *names: str):
        if not names:
            return self
        names_l = {name.lower() for name in names}
        self._ensure_loaded()
        selected = []
        for item in self._datasets:
            row = self._normalize_item(item)
            values = {
                str(row.get("material_a") or "").lower(),
                str(row.get("material_b") or "").lower(),
            }
            if values & names_l:
                selected.append(item)
        return self._clone(selected)

    def tags(self, *tags: str):
        tags_l = {tag.lower() for tag in tags}
        self._ensure_loaded()
        selected = []
        for item in self._datasets:
            row = self._normalize_item(item)
            row_tags = row.get("tags") or []
            if isinstance(row_tags, str):
                row_tags = [row_tags]
            if {str(tag).lower() for tag in row_tags} & tags_l:
                selected.append(item)
        return self._clone(selected)

    def write_manifest(self, path, *, view: str = "all") -> None:
        """Write selected dataset-item rows through the shared view projection."""

        self.items().write_table(path, view=view)

    def plot_dataset_summary(
        self,
        *,
        x: str = "name",
        y: str = "n_interfaces",
        save: str | None = None,
        **kwargs,
    ):
        rows = self.to_rows(view="all")
        try:
            import matplotlib.pyplot as plt
        except ImportError as error:
            raise ImportError("plot_dataset_summary() requires matplotlib.") from error
        fig, ax = plt.subplots()
        labels = [
            str(row.get(x) or row.get("name") or row.get("dataset_id") or index)
            for index, row in enumerate(rows)
        ]
        values = []
        for row in rows:
            try:
                values.append(float(row.get(y)))
            except (TypeError, ValueError):
                values.append(0.0)
        ax.bar(labels, values)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        if labels:
            ax.tick_params(axis="x", labelrotation=45)
        fig.tight_layout()
        if save is not None:
            output = Path(save)
            output.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output, **kwargs)
        return fig, ax
