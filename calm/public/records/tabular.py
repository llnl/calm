"""Shared tabular projection mechanics for non-collection public results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TextIO

from calm.project.presentation.notebook import TableView, _ascii_table_value
from calm.public.collections.views import (
    ResolvedTableProjection,
    ViewSpec,
    resolve_table_projection,
    resolve_view_spec,
    view_registry,
)


def resolve_named_projection(
    specs: Sequence[ViewSpec],
    rows: Iterable[Mapping[str, Any]],
    *,
    view: str | None,
    default_view: str = "summary",
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> ResolvedTableProjection:
    """Resolve detached result rows through the shared public view foundation."""

    spec = resolve_view_spec(specs, view=view, default_view=default_view)
    return resolve_table_projection(
        spec,
        rows,
        include=include,
        exclude=exclude,
    )


def projection_table(
    projection: ResolvedTableProjection,
    *,
    title: str,
    max_rows: int = 50,
    max_width: int = 120,
    max_col_width: int = 40,
    sort_by: str | None = None,
    descending: bool = False,
    file: TextIO | None = None,
) -> TableView:
    """Return one deferred table renderer for a resolved result projection."""

    return TableView(
        rows=projection.to_rows(),
        title=title,
        include=projection.columns,
        column_labels=dict(projection.display_labels),
        max_rows=max_rows,
        max_width=max_width,
        max_col_width=max_col_width,
        sort_by=sort_by,
        descending=descending,
        file=file,
    )


def projection_dataframe(projection: ResolvedTableProjection):
    """Return a dataframe with the resolved ordered schema, including when empty."""

    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "to_dataframe() requires pandas. Use to_rows() when pandas is unavailable."
        ) from exc
    return pd.DataFrame.from_records(
        projection.to_rows(),
        columns=list(projection.columns),
    )


def write_projection_csv(path: str | Path, projection: ResolvedTableProjection) -> None:
    """Write one resolved result projection with presentation-only ASCII values."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not projection.columns:
        output.write_text("", encoding="utf-8")
        return
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
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


class TabularResultMixin:
    """Provide named-view rows, tables, dataframes, and CSVs for result objects."""

    _default_view = "summary"
    _view_specs: Sequence[ViewSpec]

    @classmethod
    def available_views(cls) -> tuple[str, ...]:
        """Return the canonical named views supported by this result object."""

        view_registry(cls._view_specs)
        return tuple(spec.name for spec in cls._view_specs)

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        raise NotImplementedError

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
        title: str = "Results",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        max_rows: int = 50,
        max_width: int = 120,
        max_col_width: int = 40,
        sort_by: str | None = None,
        descending: bool = False,
        file: TextIO | None = None,
    ) -> TableView:
        """Return a deferred table renderer for one named result view."""

        projection = self._resolve_projection(
            view=view,
            include=include,
            exclude=exclude,
        )
        return projection_table(
            projection,
            title=title,
            max_rows=max_rows,
            max_width=max_width,
            max_col_width=max_col_width,
            sort_by=sort_by,
            descending=descending,
            file=file,
        )

    def to_dataframe(self, *, view: str = "summary"):
        """Return a dataframe using the same ordered schema as other exports."""

        return projection_dataframe(self._resolve_projection(view=view))

    def write_table(
        self,
        path: str | Path,
        *,
        view: str = "summary",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        """Write one named result view to CSV."""

        write_projection_csv(
            path,
            self._resolve_projection(
                view=view,
                include=include,
                exclude=exclude,
            ),
        )
