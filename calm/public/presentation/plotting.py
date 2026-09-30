"""Public plotting helpers for CALM result-like objects.

This module maps collection/result rows into the canonical
``calm.viz.plot_pareto_2d`` visualization while preserving explicit
authoritative-versus-computed front semantics. Metric names are exact public
row fields; shorthand aliases are unsupported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from calm.analysis.pareto import (
    AGGREGATE_STRAIN_SIZE_PARETO_POLICY,
    AGGREGATE_STRAIN_SIZE_PARETO_SCOPE,
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    STRAIN_SIZE_PARETO_VERSION,
    strain_size_pareto,
)
from calm.viz.pareto import plot_pareto_2d

from calm.public.projections.strain import project_candidate_strain_metrics


_RETIRED_METRIC_NAMES = frozenset(
    {
        "atoms",
        "n_atoms",
        "size",
        "dsize",
        "mismatch",
        "strain",
        "max_strain",
        "isotropic",
        "deviatoric",
        "shape",
        "area",
    }
)


def require_current_metric_name(name: object, *, argument: str) -> str:
    """Return one exact public row field name and reject retired shorthand."""

    if not isinstance(name, str) or not name:
        raise TypeError(f"{argument} must be a non-empty public row field name.")
    if name in _RETIRED_METRIC_NAMES:
        raise ValueError(
            f"Retired metric shorthand {name!r} is unsupported for {argument}; "
            "use the exact field emitted by to_rows(view='all')."
        )
    return name


# Explicit public plotting controls forwarded to ``plot_pareto_2d``. Keeping
# this list separate from the wrapper-owned arguments prevents misspelled or
# unsupported keywords from being silently ignored while preserving the
# operational styling controls used by the executable examples.
_PLOT_PARETO_FORWARD_KWARGS = frozenset(
    {
        "ids",
        "title",
        "show_title",
        "dpi",
        "annotate_scope",
        "front_style",
        "legend",
        "figsize",
        "candidate_color",
        "pareto_color",
        "candidate_marker",
        "pareto_marker",
        "candidate_alpha",
        "pareto_alpha",
        "candidate_size",
        "pareto_size",
        "front_linewidth",
        "group_by",
        "group_order",
        "group_labels",
        "group_styles",
        "palette",
        "markers",
        "legend_title",
        "front_scope",
        "front_plot_style",
        "global_front_color",
        "front_marker_size",
        "front_markeredgewidth",
        "legend_loc",
        "legend_outside",
        "legend_bbox_to_anchor",
        "legend_ncol",
        "legend_right_margin",
        "legend_fontsize",
        "legend_title_fontsize",
        "group_label_format",
        "group_front_legend",
        "legend_label_maxlen",
    }
)


def _row_atom_count(row: dict[str, Any]) -> Any:
    for key in (
        "n_atoms_interface",
        "n_atoms_estimate",
        "natoms",
        "n_atoms",
    ):
        if row.get(key) is not None:
            return row[key]
    return None


def _has_complete_pareto_provenance(
    rows: list[dict[str, Any]],
) -> bool:
    return bool(rows) and all(
        isinstance(row.get("pareto_policy"), str)
        and row.get("pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
        and isinstance(row.get("pareto_population_scope"), str)
        and row.get("pareto_d_cell_key") is not None
        and row.get("is_pareto") is not None
        for row in rows
    )


def _has_authoritative_pareto_provenance(
    rows: list[dict[str, Any]],
) -> bool:
    return _has_complete_pareto_provenance(rows) and all(
        row.get("pareto_policy") == STRAIN_SIZE_PARETO_POLICY
        and row.get("pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
        and row.get("pareto_population_scope") == STRAIN_SIZE_PARETO_POPULATION_SCOPE
        and row.get("pareto_d_cell_key") is not None
        and row.get("is_pareto") is not None
        for row in rows
    )


def _stored_front_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    if not _has_authoritative_pareto_provenance(rows):
        raise ValueError(
            "Authoritative stored Pareto provenance is unavailable. "
            "Use front='global' for automatic fallback or front='computed' "
            "for a front in the displayed x/y plane."
        )
    return [row for row in rows if bool(row.get("is_pareto"))]


def _search_population_identity(row: dict[str, Any]) -> str | None:
    """Return the durable search identity owning one stored Pareto relation."""

    value = row.get("search_id") or row.get("search_name")
    if value is None:
        return None
    identity = str(value).strip()
    return identity or None


def _spans_multiple_search_populations(rows: list[dict[str, Any]]) -> bool:
    identities = {
        identity
        for row in rows
        if (identity := _search_population_identity(row)) is not None
    }
    return len(identities) > 1


def _computed_front_rows(
    rows: list[dict[str, Any]],
    *,
    policy: str,
    population_scope: str,
) -> list[dict[str, Any]]:
    result = strain_size_pareto(
        rows,
        atom_count=_row_atom_count,
        d_cell="d_cell",
        ids=lambda row: (
            row.get("candidate_uid")
            or row.get("prototype_uid")
            or row.get("uid")
            or row.get("candidate_id")
        ),
        policy=policy,
        population_scope=population_scope,
    )
    return [rows[index] for index in result.front_idx]


def _auto_front_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    # Stored membership is authoritative only within the source search that
    # produced it. The union of multiple per-search fronts is not generally the
    # aggregate front because one search can dominate members of another.
    if _spans_multiple_search_populations(rows):
        return _computed_front_rows(
            rows,
            policy=AGGREGATE_STRAIN_SIZE_PARETO_POLICY,
            population_scope=AGGREGATE_STRAIN_SIZE_PARETO_SCOPE,
        )

    if _has_complete_pareto_provenance(rows):
        return [row for row in rows if bool(row.get("is_pareto"))]

    return _computed_front_rows(
        rows,
        policy="current_plot_strain_size_pareto",
        population_scope="current_plot_population",
    )


def plot_pareto(
    data,
    *,
    x: str = "n_atoms_estimate",
    y: str = "d_cell",
    front: str | bool | None = "global",
    save: str | Path | None = None,
    annotate: str | None = None,
    **kwargs: Any,
):
    """Plot the full candidate set with an optional Pareto-front overlay.

    ``front`` is operational and explicit:

    - ``"authoritative"`` / ``"stored"`` requires CALM's persisted
      full-population ``strain_size_pareto`` membership.
    - ``"global"`` preserves stored membership for one source search,
      computes an aggregate strain--size front across multiple selected
      searches, and otherwise falls back to the current plot population.
    - ``"computed"`` computes a separate front in the displayed x/y plane.
    - ``False`` / ``None`` / ``"none"`` disables the overlay.
    Supported styling and grouping keywords are forwarded explicitly to
    :func:`calm.viz.plot_pareto_2d`; unknown keywords are rejected.
    """
    xkey = require_current_metric_name(x, argument="plot_pareto x")
    ykey = require_current_metric_name(y, argument="plot_pareto y")
    rows = [project_candidate_strain_metrics(row) for row in data]

    if "show_front" in kwargs:
        raise TypeError("Use the public front= argument instead of show_front=.")

    unknown = set(kwargs) - _PLOT_PARETO_FORWARD_KWARGS
    if unknown:
        raise TypeError(f"Unexpected plot_pareto keyword(s): {sorted(unknown)}")

    front_token = (
        str(front).lower() if front is not None and front is not False else "none"
    )
    explicit_front = None
    if front_token in {"authoritative", "stored"}:
        show_front = True
        explicit_front = _stored_front_rows(rows)
    elif front_token in {"global", "true"}:
        show_front = True
        explicit_front = _auto_front_rows(rows)
    elif front_token == "computed":
        show_front = True
    elif front_token in {"none", "false"}:
        show_front = False
    else:
        raise ValueError(
            "front must be 'authoritative', 'stored', 'global', 'computed', "
            "False, None, or 'none'; "
            f"got {front!r}."
        )

    forwarded = {
        key: kwargs[key] for key in _PLOT_PARETO_FORWARD_KWARGS if key in kwargs
    }
    forwarded.setdefault("ids", "candidate_id")

    return plot_pareto_2d(
        rows,
        pareto=explicit_front,
        x=xkey,
        y=ykey,
        show_front=show_front,
        annotate=annotate,
        savepath=save,
        show=False,
        **forwarded,
    )
