"""Shared helpers for public query collection facades."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence, TextIO

from calm.project.presentation.notebook import TableView, _ascii_table_value
from calm.public.collections.views import (
    ResolvedTableProjection,
    ViewSpec,
    resolve_table_projection,
    resolve_view_spec,
    view_registry,
)
from calm.public.presentation.plotting import plot_pareto as _plot_pareto
from calm.public.records.interfaces import (
    InterfaceCandidate,
    _prototype_to_row,
    _strain_metrics_from_row,
)


def _row(obj: Any) -> dict[str, Any]:
    if isinstance(obj, InterfaceCandidate):
        return obj.to_dict()
    if isinstance(obj, dict):
        return _strain_metrics_from_row(dict(obj))
    return _prototype_to_row(obj)


def _range_ok(value: Any, rng) -> bool:
    if rng is None:
        return True
    lo, hi = rng
    if value is None:
        return False
    x = float(value)
    if lo is not None and x < float(lo):
        return False
    if hi is not None and x > float(hi):
        return False
    return True


class _BaseCollection:
    _items_attr = "_items"
    _default_view = "summary"
    _view_specs = (
        ViewSpec(name="summary", allow_extra_columns=True),
        ViewSpec(name="all", allow_extra_columns=True),
    )

    def _public_item(self, item: Any) -> Any:
        """Convert one internal collection item to its public typed record."""
        raise NotImplementedError

    def records(self) -> list[Any]:
        """Return typed public records for the selected collection items."""
        self._ensure_loaded()
        return [self._public_item(item) for item in getattr(self, self._items_attr)]

    def __iter__(self):
        return iter(self.records())

    def __len__(self):
        self._ensure_loaded()
        return len(getattr(self, self._items_attr))

    def __getitem__(self, idx):
        self._ensure_loaded()
        item = getattr(self, self._items_attr)[idx]
        if isinstance(idx, slice):
            return [self._public_item(value) for value in item]
        return self._public_item(item)

    def _ensure_loaded(self):
        return None

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        """Normalize one internal item to its collection-specific public row."""
        raise NotImplementedError

    @classmethod
    def available_views(cls) -> tuple[str, ...]:
        """Return the canonical named views supported by this collection."""

        view_registry(cls._view_specs)
        return tuple(spec.name for spec in cls._view_specs)

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        """Return unprojected scientific rows for one validated canonical view."""

        self._ensure_loaded()
        return [self._normalize_item(x) for x in getattr(self, self._items_attr)]

    def _extra_columns_for_view(self, view: str) -> tuple[str, ...]:
        """Return domain-declared runtime columns for one extensible view."""

        del view
        return ()

    def _resolve_projection(
        self,
        *,
        view: str | None = None,
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> ResolvedTableProjection:
        spec = resolve_view_spec(
            self._view_specs,
            view=view,
            default_view=self._default_view,
        )
        rows = self._rows_for_view(spec.name)
        return resolve_table_projection(
            spec,
            rows,
            declared_extra_columns=self._extra_columns_for_view(spec.name),
            include=include,
            exclude=exclude,
        )

    def to_rows(self, *, view: str = "summary") -> list[dict[str, Any]]:
        """Return homogeneous rows for one validated named view."""

        return self._resolve_projection(view=view).to_rows()

    def to_table(
        self,
        *,
        view: str = "summary",
        title: str = "Records",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        max_rows: int = 50,
        max_width: int = 120,
        max_col_width: int = 40,
        sort_by: str | None = None,
        descending: bool = False,
        file: TextIO | None = None,
    ) -> TableView:
        """Return a TableView representing this collection.

        This allows callers to defer rendering (e.g., in notebooks) and to
        integrate with the existing display_table helpers.
        """
        projection = self._resolve_projection(
            view=view,
            include=include,
            exclude=exclude,
        )
        return TableView(
            rows=projection.to_rows(),
            title=title,
            include=projection.columns,
            exclude=None,
            column_labels=dict(projection.display_labels),
            max_rows=max_rows,
            max_width=max_width,
            max_col_width=max_col_width,
            sort_by=sort_by,
            descending=descending,
            file=file,
        )

    def to_dataframe(self, *, view: str = "summary"):
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "to_dataframe() requires pandas. Use to_rows() when pandas is unavailable."
            ) from e
        projection = self._resolve_projection(view=view)
        return pd.DataFrame.from_records(
            projection.to_rows(),
            columns=list(projection.columns),
        )

    def write_table(
        self,
        path,
        *,
        view: str = "summary",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        """Write presentation rows to CSV with optional column selection.

        Unicode subscript digits are normalized to plain ASCII in the table
        artifact. Canonical rows returned by ``to_rows()`` remain unchanged.
        """

        projection = self._resolve_projection(
            view=view,
            include=include,
            exclude=exclude,
        )
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not projection.columns:
            p.write_text("", encoding="utf-8")
            return

        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=list(projection.columns),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(
                {
                    key: _ascii_table_value(value)
                    for key, value in row.items()
                }
                for row in projection.rows
            )

    def plot_pareto(
        self,
        *,
        x: str = "n_atoms_estimate",
        y: str = "d_cell",
        front: str = "global",
        save: str | None = None,
        **kwargs,
    ):
        return _plot_pareto(
            self.to_rows(view="all"), x=x, y=y, front=front, save=save, **kwargs
        )

    def where(self, **filters):
        self._ensure_loaded()
        items = []
        for item in getattr(self, self._items_attr):
            # Use collection-specific normalization for filtering rather than
            # the candidate-centric global _row() helper.
            r = self._normalize_item(item)
            ok = True
            for key, val in filters.items():
                col = key
                if isinstance(val, tuple) and len(val) == 2:
                    if not _range_ok(r.get(col), val):
                        ok = False
                        break
                elif isinstance(val, (list, set, tuple)):
                    if r.get(col) not in val:
                        ok = False
                        break
                else:
                    if r.get(col) != val:
                        ok = False
                        break
            if ok:
                items.append(item)
        return self._clone(items)

    def get(self, *args, **filters):
        self._ensure_loaded()
        if args:
            needle = str(args[0])
            matches = []
            for item in getattr(self, self._items_attr):
                r = self._normalize_item(item)
                # Match against common identity fields including label and id_short
                if needle in {
                    str(r.get("id") or ""),
                    str(r.get("uid") or ""),
                    str(r.get("uid_full") or ""),
                    str(r.get("candidate_id") or ""),
                    str(r.get("structure_id") or ""),
                    str(r.get("search_id") or ""),
                    str(r.get("search_name") or ""),
                    str(r.get("interface_id") or ""),
                    str(r.get("dataset_id") or ""),
                    str(r.get("campaign_id") or ""),
                    str(r.get("run_id") or ""),
                    str(r.get("name") or ""),
                    str(r.get("label") or ""),
                    str(r.get("id_short") or ""),
                }:
                    matches.append(item)
        else:
            matches = list(self.where(**filters))
        if not matches:
            raise KeyError(f"No project object matches {args or filters!r}.")
        if len(matches) > 1:
            from calm.public.errors import AmbiguousProjectQueryError

            raise AmbiguousProjectQueryError(
                f"Multiple project objects match {args or filters!r}; add filters to disambiguate."
            )
        return self._public_item(matches[0])

    def one_or_none(self, *args, **filters):
        """Return zero or one matching record.

        ``None`` is returned when no record matches. Ambiguous matches still
        raise ``AmbiguousProjectQueryError``; callers must add filters
        rather than relying on arbitrary ordering.
        """
        try:
            return self.get(*args, **filters)
        except KeyError:
            return None

    def latest(self, **filters):
        self._ensure_loaded()
        if filters:
            selected = self.where(**filters)
            selected._ensure_loaded()
            matches = list(getattr(selected, selected._items_attr))
        else:
            matches = list(getattr(self, self._items_attr))
        if not matches:
            raise KeyError(f"No project object matches {filters!r}.")

        def key(item):
            r = self._normalize_item(item)
            return str(r.get("created_at") or "")

        return self._public_item(sorted(matches, key=key)[-1])

    def _clone(self, items):
        return type(self)(items=items)
