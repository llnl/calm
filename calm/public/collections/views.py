"""Shared named-view and tabular-projection primitives for public reporting.

This module owns the mechanics of resolving a public view into one ordered row
schema. Domain collections and result objects remain responsible for producing
scientific row values and, for explicitly extensible views, declaring any
runtime columns derived from domain metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


def _normalized_names(values: Sequence[str], *, label: str) -> tuple[str, ...]:
    if any(not isinstance(value, str) for value in values):
        raise TypeError(f"{label} values must be strings.")
    names = tuple(values)
    if any(not name or name != name.strip() for name in names):
        raise ValueError(f"{label} values must be non-empty stripped strings.")
    if len(names) != len(set(names)):
        raise ValueError(f"{label} values must not contain duplicates.")
    return names


def _normalized_display_labels(
    values: Sequence[tuple[str, str]],
    *,
    columns: Sequence[str],
    view_name: str,
) -> tuple[tuple[str, str], ...]:
    labels: list[tuple[str, str]] = []
    seen_columns: set[str] = set()
    seen_labels: set[str] = set()
    available = set(columns)
    for item in values:
        if not isinstance(item, tuple) or len(item) != 2:
            raise TypeError(
                f"{view_name} display labels must be (column, label) tuples."
            )
        column, label = item
        if not isinstance(column, str) or not isinstance(label, str):
            raise TypeError(
                f"{view_name} display-label columns and labels must be strings."
            )
        if not column or column != column.strip():
            raise ValueError(
                f"{view_name} display-label columns must be non-empty stripped strings."
            )
        if not label or label != label.strip():
            raise ValueError(
                f"{view_name} display labels must be non-empty stripped strings."
            )
        if column not in available:
            raise ValueError(
                f"{view_name} display label references unknown column {column!r}."
            )
        if column in seen_columns:
            raise ValueError(
                f"{view_name} display label repeats column {column!r}."
            )
        if label in seen_labels:
            raise ValueError(
                f"{view_name} display label {label!r} is not unique."
            )
        labels.append((column, label))
        seen_columns.add(column)
        seen_labels.add(label)

    label_map = dict(labels)
    effective = [label_map.get(column, column) for column in columns]
    if len(effective) != len(set(effective)):
        raise ValueError(
            f"{view_name} effective display labels must be unique."
        )
    return tuple(labels)


def _ordered_union(*groups: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for name in group:
            if name not in seen:
                result.append(name)
                seen.add(name)
    return tuple(result)


@dataclass(frozen=True)
class ViewSpec:
    """Describe one named public row projection.

    ``columns`` declares the stable base schema, including the header emitted
    for an empty result. ``display_labels`` optionally supplies compact terminal
    and HTML headings while canonical row, dataframe, and CSV names remain
    unchanged. ``allow_extra_columns`` is reserved for complete or
    domain-declared dynamic views. Extra fields are appended deterministically
    after the declared base schema; ordinary summary and provenance views must
    keep it false.
    """

    name: str
    columns: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    display_labels: tuple[tuple[str, str], ...] = ()
    allow_extra_columns: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("ViewSpec.name must be a string.")
        name = self.name
        if not name or name != name.strip():
            raise ValueError("ViewSpec.name must be a non-empty stripped string.")
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "columns",
            _normalized_names(self.columns, label=f"{name} columns"),
        )
        object.__setattr__(
            self,
            "aliases",
            _normalized_names(self.aliases, label=f"{name} aliases"),
        )
        object.__setattr__(
            self,
            "display_labels",
            _normalized_display_labels(
                self.display_labels,
                columns=self.columns,
                view_name=name,
            ),
        )
        if name in self.aliases:
            raise ValueError("A view name must not also appear in its aliases.")
        if not isinstance(self.allow_extra_columns, bool):
            raise TypeError("ViewSpec.allow_extra_columns must be a bool.")


@dataclass(frozen=True)
class ResolvedTableProjection:
    """One resolved named view with a deterministic schema and homogeneous rows."""

    view: str
    columns: tuple[str, ...]
    display_labels: tuple[tuple[str, str], ...]
    rows: tuple[dict[str, Any], ...]

    def to_rows(self) -> list[dict[str, Any]]:
        """Return mutable row copies for public callers and renderers."""

        return [dict(row) for row in self.rows]


def view_registry(specs: Sequence[ViewSpec]) -> dict[str, ViewSpec]:
    """Return a validated registry mapping canonical names and aliases to specs."""

    if not specs:
        raise ValueError("At least one public view specification is required.")
    registry: dict[str, ViewSpec] = {}
    canonical: set[str] = set()
    for spec in specs:
        if spec.name in canonical:
            raise ValueError(f"Duplicate public view name {spec.name!r}.")
        canonical.add(spec.name)
        for name in (spec.name, *spec.aliases):
            if name in registry:
                raise ValueError(f"Duplicate public view name or alias {name!r}.")
            registry[name] = spec
    return registry


def resolve_view_spec(
    specs: Sequence[ViewSpec],
    *,
    view: str | None,
    default_view: str,
) -> ViewSpec:
    """Resolve one requested view name or raise with the supported vocabulary."""

    registry = view_registry(specs)
    if view is not None and not isinstance(view, str):
        raise TypeError("Table view names must be strings.")
    requested = default_view if view is None else view
    spec = registry.get(requested)
    if spec is None:
        canonical = sorted({value.name for value in registry.values()})
        choices = ", ".join(repr(name) for name in canonical)
        raise ValueError(
            f"Unknown table view {requested!r}. Supported views: {choices}."
        )
    return spec


def _ordered_row_keys(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for name in row:
            if name not in seen:
                columns.append(name)
                seen.add(name)
    return tuple(columns)


def _selection(
    *,
    available: tuple[str, ...],
    include: Sequence[str] | None,
    exclude: Sequence[str] | None,
) -> tuple[str, ...]:
    included = (
        _normalized_names(include, label="include") if include is not None else None
    )
    excluded = (
        _normalized_names(exclude, label="exclude") if exclude is not None else ()
    )
    available_set = set(available)

    if included is not None:
        unknown = [name for name in included if name not in available_set]
        if unknown:
            raise KeyError(
                "Unknown included table columns: " + ", ".join(repr(x) for x in unknown)
            )
        selected = included
    else:
        selected = available

    unknown_excluded = [name for name in excluded if name not in available_set]
    if unknown_excluded:
        raise KeyError(
            "Unknown excluded table columns: "
            + ", ".join(repr(x) for x in unknown_excluded)
        )
    overlap = set(selected) & set(excluded)
    if included is not None and overlap:
        names = ", ".join(repr(name) for name in sorted(overlap))
        raise ValueError(f"Columns cannot be both included and excluded: {names}.")
    excluded_set = set(excluded)
    return tuple(name for name in selected if name not in excluded_set)


def resolve_table_projection(
    spec: ViewSpec,
    rows: Iterable[Mapping[str, Any]],
    *,
    declared_extra_columns: Sequence[str] | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> ResolvedTableProjection:
    """Resolve one view into an ordered schema shared by every export target.

    Extensible views append domain-declared columns and then any observed row
    keys. This preserves a meaningful header for empty exports while retaining
    complete metadata in ``all`` views and declared feature/metric columns in
    dynamic views.
    """

    normalized = [dict(row) for row in rows]
    for row in normalized:
        if any(not isinstance(key, str) for key in row):
            raise TypeError("Public table row keys must be strings.")

    extra = (
        _normalized_names(declared_extra_columns, label="declared extra columns")
        if declared_extra_columns is not None
        else ()
    )
    if extra and not spec.allow_extra_columns:
        raise ValueError(
            f"View {spec.name!r} does not permit domain-declared extra columns."
        )

    if spec.allow_extra_columns:
        available = _ordered_union(
            spec.columns,
            extra,
            _ordered_row_keys(normalized),
        )
    else:
        available = spec.columns

    columns = _selection(
        available=available,
        include=include,
        exclude=exclude,
    )
    projected = tuple(
        {column: row.get(column) for column in columns} for row in normalized
    )
    selected_columns = set(columns)
    display_labels = tuple(
        (column, label)
        for column, label in spec.display_labels
        if column in selected_columns
    )
    return ResolvedTableProjection(
        view=spec.name,
        columns=columns,
        display_labels=display_labels,
        rows=projected,
    )
