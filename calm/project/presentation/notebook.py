"""Notebook and script UX helpers.

This module intentionally has **no hard dependency** on IPython/Jupyter.
When running inside a notebook environment, tables are displayed as HTML.
Otherwise, they are rendered as a compact plain-text table.

The primary public entrypoint is :func:`display_table`. Domain schema selection
belongs to public named views; this renderer only formats explicitly projected
rows and optional caller-selected columns.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping, Sequence, TextIO


_SUBSCRIPT_DIGITS_TO_ASCII = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def _ascii_table_value(value: Any) -> Any:
    """Return a table-safe value with Unicode subscript digits normalized."""

    if isinstance(value, str):
        return value.translate(_SUBSCRIPT_DIGITS_TO_ASCII)
    return value


def _in_ipython() -> bool:
    try:
        from IPython import get_ipython
    except ImportError:
        return False
    return get_ipython() is not None


def _rich_display_available() -> bool:
    try:
        import IPython.display as ipd  # noqa: F401
        import pandas as pd  # noqa: F401
    except ImportError:
        return False
    else:
        return True


def _coerce_to_dict(row: Any) -> dict[str, Any]:
    """Coerce one supported display row to a dictionary."""

    if row is None:
        return {}
    if isinstance(row, Mapping):
        return dict(row)
    if is_dataclass(row):
        return asdict(row)

    state = getattr(row, "__dict__", None)
    if isinstance(state, dict):
        return dict(state)

    return {"value": row}


def _coerce_rows_to_dicts(rows: Sequence[Any]) -> list[dict[str, Any]]:
    return [_coerce_to_dict(row) for row in rows]


def _truncate(value: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(value) <= max_len:
        return value
    if max_len <= 1:
        return value[:max_len]
    return value[: max_len - 1] + "…"


def _format_cell_value(value: Any) -> str:
    """Format one cell without changing canonical scientific values."""

    if value is None:
        rendered = "—"
    elif isinstance(value, float):
        rendered = f"{value:.4f}"
    else:
        rendered = str(value)
    return rendered.translate(_SUBSCRIPT_DIGITS_TO_ASCII)


def _apply_sort(
    rows: list[dict[str, Any]], sort_by: str | None, descending: bool
) -> None:
    if not sort_by:
        return

    def key_fn(row: dict[str, Any]) -> Any:
        value = row.get(sort_by)
        return (value is None, value)

    rows.sort(key=key_fn, reverse=descending)


def _render_plain_table(
    rows: list[dict[str, Any]],
    *,
    columns: Sequence[str],
    column_labels: Mapping[str, str] | None,
    max_width: int,
    max_col_width: int,
) -> str:
    if not columns:
        return "(no columns)"

    rendered_rows = [
        [_format_cell_value(row.get(column)) for column in columns] for row in rows
    ]

    labels = [
        (column_labels or {}).get(column, column)
        for column in columns
    ]

    widths: list[int] = []
    for index, column in enumerate(columns):
        width = len(labels[index])
        for row in rendered_rows:
            width = max(width, len(row[index]))
        widths.append(min(width, max_col_width))

    if max_width > 0:
        total = sum(widths) + 3 * (len(widths) - 1)
        if total > max_width:
            overflow = total - max_width
            order = sorted(range(len(widths)), key=lambda i: widths[i], reverse=True)
            for index in order:
                if overflow <= 0:
                    break
                min_width = 3
                if widths[index] <= min_width:
                    continue
                delta = min(widths[index] - min_width, overflow)
                widths[index] -= delta
                overflow -= delta

    def format_row(values: list[str]) -> str:
        return " | ".join(
            _truncate(value, widths[index]).ljust(widths[index])
            for index, value in enumerate(values)
        )

    header = format_row(labels)
    separator = "-+-".join("-" * width for width in widths)
    body = "\n".join(format_row(row) for row in rendered_rows)
    return "\n".join([header, separator, body] if body else [header, separator])


def _render_html_table(
    rows: list[dict[str, Any]],
    *,
    columns: Sequence[str],
    column_labels: Mapping[str, str] | None,
    title: str,
) -> Any:
    import IPython.display as ipd
    import pandas as pd

    formatted_rows = [
        {column: _format_cell_value(row.get(column)) for column in columns}
        for row in rows
    ]
    frame = pd.DataFrame(formatted_rows, columns=list(columns))
    frame.columns = [
        (column_labels or {}).get(column, column)
        for column in columns
    ]
    html = frame.to_html(index=False, escape=True)
    if title:
        html = f"<h4>{title}</h4>\n" + html
    return ipd.HTML(html)


def _get_nested(obj: Any, path: str) -> Any:
    """Retrieve one dotted-path value from nested mappings."""

    if not path:
        return None
    current: Any = obj
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _materialize_dotted_columns(
    rows: list[dict[str, Any]], columns: Sequence[str] | None
) -> None:
    if not columns:
        return
    for column in columns:
        if "." not in column:
            continue
        for row in rows:
            if column not in row:
                row[column] = _get_nested(row, column)


@dataclass(frozen=True)
class TableView:
    """A lightweight deferred view returned by public ``to_table()`` methods."""

    rows: list[dict[str, Any]]
    title: str = "Records"
    include: Sequence[str] | None = None
    exclude: Sequence[str] | None = None
    column_labels: Mapping[str, str] | None = None
    max_rows: int = 50
    max_width: int = 120
    max_col_width: int = 40
    sort_by: str | None = None
    descending: bool = False
    file: TextIO | None = None

    def display(self) -> None:
        display_table(
            self.rows,
            title=self.title,
            include=self.include,
            exclude=self.exclude,
            column_labels=self.column_labels,
            max_rows=self.max_rows,
            max_width=self.max_width,
            max_col_width=self.max_col_width,
            sort_by=self.sort_by,
            descending=self.descending,
            file=self.file,
        )


def display_table(
    rows: Sequence[Any] | None,
    *,
    title: str = "Records",
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    column_labels: Mapping[str, str] | None = None,
    max_rows: int = 50,
    max_width: int = 120,
    max_col_width: int = 40,
    sort_by: str | None = None,
    descending: bool = False,
    file: TextIO | None = None,
) -> None:
    """Display explicitly projected rows in notebooks or plain scripts.

    ``display_table`` is a renderer, not a domain schema selector. Public
    collections and workflow results own named views and pass their resolved
    ordered columns through ``include``. Direct callers may provide ``include``
    for an explicit generic projection; otherwise the sorted union of row keys is
    rendered. Dotted paths are supported for nested mappings.
    """

    if rows is None:
        rows = []

    if isinstance(rows, TableView):
        view = rows
        rows = view.rows
        title = view.title
        include = view.include
        exclude = view.exclude
        column_labels = view.column_labels
        max_rows = view.max_rows
        max_width = view.max_width
        max_col_width = view.max_col_width
        sort_by = view.sort_by
        descending = view.descending
        file = view.file

    normalized = _coerce_rows_to_dicts(list(rows))
    wanted = include
    _materialize_dotted_columns(normalized, wanted)

    if wanted is None:
        columns = sorted({key for row in normalized for key in row})
    else:
        columns = list(wanted)

    if exclude:
        excluded = set(exclude)
        columns = [column for column in columns if column not in excluded]

    labels = dict(column_labels or {})
    unknown_labels = sorted(set(labels) - set(columns))
    if unknown_labels:
        names = ", ".join(repr(name) for name in unknown_labels)
        raise KeyError(f"Unknown labeled table columns: {names}.")
    if len(set(labels.values())) != len(labels):
        raise ValueError("Table column labels must be unique.")

    if max_rows >= 0:
        normalized = normalized[:max_rows]

    _materialize_dotted_columns(normalized, columns)
    _apply_sort(normalized, sort_by, descending)

    if _in_ipython() and _rich_display_available():
        obj = _render_html_table(
            normalized,
            columns=columns,
            column_labels=labels,
            title=title,
        )
        import IPython.display as ipd

        ipd.display(obj)
        return

    output = file or sys.stdout
    text = _render_plain_table(
        normalized,
        columns=columns,
        column_labels=labels,
        max_width=max_width,
        max_col_width=max_col_width,
    )
    if title:
        print()
        use_color = os.environ.get("CALM_COLOR", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if use_color:
            print(f"\x1b[1;34m{title}\x1b[0m", file=output)
        else:
            print(title, file=output)
        print()
    print(text, file=output)
