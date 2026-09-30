"""calm.viz.pareto

Lightweight Pareto-front utilities + plotting helpers.

This module intentionally stays dependency-light (numpy + matplotlib) and avoids
pulling in the full workflow stack.

Current entrypoints
-------------------
- ``pareto_front_2d``: internal structured front computation used by result and
  plotting projections.
- ``plot_pareto_2d``: canonical visualization helper used by public reporting.

Notes on derived metrics
------------------------
The plotting helpers support a small set of *derived* feature names for UX.
Currently:

- ``hencky_norm``: ||E_H||_F = 1/2 * d_cell

This is a scalar derived from the affine-invariant cell similarity distance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Union

import numpy as np

from calm.analysis.pareto import pareto_front_2d_numpy

# matplotlib is only required for plotting, not for Pareto computation.
from ._save import coerce_savepath, save_figure

Feature = Union[str, Callable[[Any], Any]]


def get_feature(obj: Any, feature: Feature, default: Any = None) -> Any:
    """Get a feature value from ``obj``.

    Supports:
    - dict-like objects (``Mapping``)
    - attribute access
    - callables

    In addition, a small set of *derived* feature names are supported:

    - ``hencky_norm``: ``0.5 * d_cell``
    """

    if callable(feature):
        try:
            return feature(obj)
        except Exception:
            return default

    if not isinstance(feature, str):
        return default

    # ---------------------------------------------------------------------
    # Derived / UX-only feature names
    # ---------------------------------------------------------------------
    if feature == "hencky_norm":
        # ||E_H||_F = 1/2 * d_cell
        if isinstance(obj, Mapping):
            d_cell = obj.get("d_cell", None)
        else:
            d_cell = getattr(obj, "d_cell", None)
        if d_cell is None:
            return default
        try:
            return 0.5 * float(d_cell)
        except Exception:
            return default

    # ---------------------------------------------------------------------
    # Direct access
    # ---------------------------------------------------------------------
    if isinstance(obj, Mapping):
        return obj.get(feature, default)

    return getattr(obj, feature, default)


def _to_float(x: Any) -> float:
    try:
        v = float(x)
    except Exception:
        return float("nan")
    return v


def _stair_step_path(
    x_line: np.ndarray,
    y_line: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return an axis-aligned path through Pareto points ordered by x."""
    if x_line.size == 0:
        return x_line, y_line

    x_step = [float(x_line[0])]
    y_step = [float(y_line[0])]
    for index in range(x_line.size - 1):
        x_current = float(x_line[index])
        y_current = float(y_line[index])
        x_next = float(x_line[index + 1])
        y_next = float(y_line[index + 1])

        if x_next == x_current and y_next == y_current:
            continue
        if x_next != x_current:
            x_step.append(x_next)
            y_step.append(y_current)
        if y_next != y_current:
            x_step.append(x_next)
            y_step.append(y_next)

    return np.asarray(x_step, dtype=float), np.asarray(y_step, dtype=float)


@dataclass(frozen=True)
class ParetoFront2DResult:
    """Structured result for ``pareto_front_2d``.

    Attributes
    ----------
    mask
        Boolean mask over the input points (same length as the input sequence).
    front_idx
        Indices of Pareto-optimal points (sorted, deterministic).
    front_ids
        IDs corresponding to ``front_idx``.
    xvals, yvals
        Feature values (in the original, non-negated coordinate system) for the
        front points.
    """

    mask: np.ndarray
    front_idx: list[int]
    front_ids: list[str]
    xvals: np.ndarray
    yvals: np.ndarray


def pareto_front_2d(
    points: Sequence[Any],
    *,
    x: Feature,
    y: Feature,
    ids: Feature = "id",
    strict: bool = True,
    minimize: tuple[bool, bool] = (True, True),
) -> ParetoFront2DResult:
    """Compute a 2D Pareto front from points.

    Parameters
    ----------
    points
        Sequence of points. Each point may be a dict-like mapping or an
        attribute-based object.

    x, y
        Feature selectors for the x/y coordinates.

    ids
        Feature selector for a stable identifier.

    strict
        If True, equal points do **not** dominate each other (so duplicates can
        coexist on the front).

    minimize
        Tuple indicating whether each axis is minimized (True) or maximized
        (False).

    Returns
    -------
    ParetoFront2DResult
        Includes both a full mask over inputs and a sorted list of front points.

    Notes
    -----
    Invalid points (non-finite x/y) are excluded from the dominance calculation
    and are marked as ``False`` in the returned mask.
    """

    if len(minimize) != 2:
        raise ValueError("minimize must be a 2-tuple (min_x, min_y)")

    n = len(points)

    x_all = np.full(n, np.nan, dtype=float)
    y_all = np.full(n, np.nan, dtype=float)
    id_all: list[str] = []

    for i, p in enumerate(points):
        pid = get_feature(p, ids, default=f"{i}")
        id_all.append(str(pid))
        x_all[i] = _to_float(get_feature(p, x, default=np.nan))
        y_all[i] = _to_float(get_feature(p, y, default=np.nan))

    valid = np.isfinite(x_all) & np.isfinite(y_all)

    # If nothing is valid, return a trivial result.
    if not bool(np.any(valid)):
        return ParetoFront2DResult(
            mask=np.zeros(n, dtype=bool),
            front_idx=[],
            front_ids=[],
            xvals=np.array([], dtype=float),
            yvals=np.array([], dtype=float),
        )

    # Convert to a minimization problem for the kernel.
    x_eff = x_all.copy()
    y_eff = y_all.copy()
    if not minimize[0]:
        x_eff[valid] *= -1.0
    if not minimize[1]:
        y_eff[valid] *= -1.0

    idx_valid = np.flatnonzero(valid)

    # NOTE: pareto_front_2d_numpy returns
    #   (mask, pareto_idx, pareto_ids, pareto_x, pareto_y)
    # where pareto_idx is relative to the provided x/y arrays.
    _, front_idx_valid, _, _, _ = pareto_front_2d_numpy(
        x_eff[idx_valid],
        y_eff[idx_valid],
        strict=strict,
        ids=[id_all[int(i)] for i in idx_valid],
    )

    front_idx = [int(idx_valid[int(i)]) for i in front_idx_valid]
    front_ids = [id_all[i] for i in front_idx]

    mask = np.zeros(n, dtype=bool)
    for i in front_idx:
        mask[i] = True

    xvals = x_all[np.asarray(front_idx, dtype=int)]
    yvals = y_all[np.asarray(front_idx, dtype=int)]

    return ParetoFront2DResult(
        mask=mask,
        front_idx=front_idx,
        front_ids=front_ids,
        xvals=xvals,
        yvals=yvals,
    )


def _pareto_subset(
    candidates: Sequence[Any],
    *,
    x: Feature = "n_atoms_interface",
    y: Feature = "d_cell",
    ids: Feature = "uid",
) -> list[Any]:
    """Return the non-dominated points used by the plotting implementation."""

    res = pareto_front_2d(candidates, x=x, y=y, ids=ids)
    return [candidates[i] for i in res.front_idx]


# Axis label defaults used by the example scripts.
_AXIS_LABELS: dict[str, str] = {
    # Atom counts
    "n_atoms_interface": r"Interface cell atoms, $N_\mathrm{interface}$",
    "n_atoms_estimate": r"Estimated atoms, $N_\mathrm{atoms}$",
    "n_atoms": r"Atoms, $N_\mathrm{atoms}$",
    # Cell/shape metrics
    "d_cell": r"Cell similarity metric, $d_\mathrm{cell}$",
    "d_size": r"Size penalty, $d_\mathrm{size}$",
    "d_area": r"Area mismatch metric, $d_\mathrm{area}$",
    "d_shape": r"Shape mismatch metric, $d_\mathrm{shape}$",
    # Strain/derived metrics
    "hencky_norm": r"Hencky strain norm, $\|E_H\|_F$",
    "max_principal_strain": r"Max principal strain, $\max\,\varepsilon_i$",
    "isotropic_strain_norm": r"Isotropic strain norm, $\|E_\mathrm{iso}\|$",
    "deviatoric_strain_norm": r"Deviatoric strain norm, $\|E_\mathrm{dev}\|$",
    # Scores
    "match_score": r"Match score, $s_\mathrm{match}$",
    "score": r"Match score, $s_\mathrm{match}$",
}


def _pretty_label(feature: Feature, *, axis: str) -> str:
    if isinstance(feature, str):
        # If this is a recognized canonical label, return it verbatim so the
        # descriptive phrase and mathtext are preserved. For unknown labels
        # fall back to the raw string.
        return _AXIS_LABELS.get(feature, str(feature))
    # Callable feature: fall back to a generic axis name.
    return "x" if axis == "x" else "y"


def plot_pareto_2d(
    candidates: Sequence[Any],
    *,
    pareto: Optional[Sequence[Any]] = None,
    x: Feature = "n_atoms_interface",
    y: Feature = "d_cell",
    orig_x: Feature | None = None,
    orig_y: Feature | None = None,
    ids: Feature = "uid",
    title: Optional[str] = None,
    show_title: bool = False,
    savepath: Optional[Union[str, Path]] = None,
    dpi: Optional[int] = 300,
    show: bool = True,
    ax: Optional[Any] = None,
    annotate: Optional[Feature] = None,
    annotate_scope: str = "none",
    # Plot styling
    show_front: bool = True,
    front_style: str = "line",
    legend: bool = True,
    figsize: tuple[float, float] = (6.0, 4.0),
    candidate_color: str = "C0",
    pareto_color: str = "C1",
    candidate_marker: str = "o",
    pareto_marker: str = "x",
    candidate_alpha: float = 0.7,
    pareto_alpha: float = 1.0,
    candidate_size: float = 36,
    pareto_size: float = 56,
    front_linewidth: float = 2.0,
    # Grouping support
    group_by: Optional[Feature] = None,
    group_order: Optional[Sequence[Any]] = None,
    group_labels: Optional[Mapping[Any, str]] = None,
    group_styles: Optional[Mapping[Any, Mapping[str, Any]]] = None,
    palette: Optional[Sequence[str]] = None,
    markers: Optional[Sequence[str]] = None,
    legend_title: Optional[str] = None,
    # front_scope: 'global' | 'per_group' | 'both' | 'none'
    front_scope: str = "global",
    # Front appearance controls
    front_plot_style: str | None = "-x",
    global_front_color: Optional[str] = "k",
    front_marker_size: float = 7.0,
    front_markeredgewidth: float = 1.5,
    # Legend placement
    legend_loc: str = "best",
    legend_outside: bool = False,
    legend_bbox_to_anchor: tuple[float, float] | None = None,
    legend_ncol: int = 1,
    legend_right_margin: float = 0.72,
    legend_fontsize: Any | None = "small",
    legend_title_fontsize: Any | None = "small",
    # Group label format
    group_label_format: str = "match_space",  # or 'group_key'
    group_front_legend: bool = False,
    legend_label_maxlen: int | None = 40,
) -> tuple[Any, Any]:
    """Plot a 2D Pareto scatter plot.

    This function is designed to be safe in headless environments. When
    ``show=False`` and no Axes are provided, it avoids importing
    ``matplotlib.pyplot`` and instead creates a Figure backed by an Agg canvas.
    This prevents GUI-backend selection issues during automated test runs.

    Parameters
    ----------
    candidates
        Full candidate list.

    pareto
        Optional explicit Pareto set. If None, computed from candidates.

    x, y
        Feature selectors.

    title
        Plot title. If None and ``show_title`` is True, a default title is used.

    show_title
        Whether to render a title.

    savepath
        Optional output path. If provided, the figure is written via
        :meth:`matplotlib.figure.Figure.savefig`.

    dpi
        Output DPI used when saving figures. Set to ``None`` to defer to
        Matplotlib's default.

    show
        If True, show the plot (only when using pyplot-managed figures).

    front_style
        Pareto-front rendering style: ``"line"``, ``"step"``, or ``"none"``.

    Returns
    -------
    (fig, ax)
    """

    if front_style not in {"line", "step", "none"}:
        front_style = "line"
    if group_label_format not in {"match_space", "group_key"}:
        raise ValueError("group_label_format must be 'match_space' or 'group_key'")

    plt = None  # matplotlib.pyplot, if we end up using it.

    if ax is None:
        if show:
            # Interactive path: use pyplot for proper figure management.
            import matplotlib.pyplot as plt  # type: ignore[import-not-found]

            fig, ax = plt.subplots(figsize=figsize)
        else:
            # Headless/testing path: avoid pyplot and force an Agg canvas.
            from matplotlib.figure import Figure  # type: ignore[import-not-found]

            fig = Figure(figsize=figsize)
            try:
                from matplotlib.backends.backend_agg import (
                    FigureCanvasAgg,  # type: ignore[import-not-found]
                )

                FigureCanvasAgg(fig)
            except Exception:
                # If Agg isn't available, we can still proceed; save/show may fail.
                pass
            ax = fig.add_subplot(111)
    else:
        fig = ax.figure

    _savepath = coerce_savepath(savepath=savepath)

    # Extract candidate data once.
    def _arr_from_points(points: Sequence[Any], feat: Feature) -> np.ndarray:
        vals: list[float] = []
        for p in points:
            vals.append(_to_float(get_feature(p, feat, default=np.nan)))
        return np.asarray(vals, dtype=float)

    x_all = _arr_from_points(candidates, x)
    y_all = _arr_from_points(candidates, y)

    # Determine Pareto set
    if pareto is not None:
        # Explicit pareto provided (may be empty list) -> use it
        explicit_pareto = True
    else:
        explicit_pareto = False

    if explicit_pareto:
        x_p = _arr_from_points(pareto, x)
        y_p = _arr_from_points(pareto, y)
    else:
        if show_front:
            pareto = _pareto_subset(candidates, x=x, y=y, ids=ids)
            x_p = _arr_from_points(pareto, x)
            y_p = _arr_from_points(pareto, y)
        else:
            pareto = []
            x_p = np.array([], dtype=float)
            y_p = np.array([], dtype=float)

    # Grouping support
    _DEFAULT_GROUP_COLORS = ("C0", "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9")
    _DEFAULT_GROUP_MARKERS = ("o", "s", "^", "D", "v", "P", "X", "*", "<", ">")

    def _get_group_key(p):
        if group_by is None:
            return None
        return get_feature(p, group_by, default=None)

    group_keys = None
    if group_by is None:
        # Single-group plotting (legacy behavior)
        ax.scatter(
            x_all,
            y_all,
            marker=candidate_marker,
            s=candidate_size,
            color=candidate_color,
            alpha=candidate_alpha,
            label="Candidates",
        )
    else:
        # Grouped plotting
        keys = [_get_group_key(p) for p in candidates]
        unique = []
        for k in keys:
            if k not in unique:
                unique.append(k)
        if group_order is not None:
            present = tuple(unique)
            ordered = [key for key in group_order if key in present]
            ordered.extend(key for key in present if key not in ordered)
            unique = ordered
        group_keys = unique

        colors = list(palette) if palette is not None else list(_DEFAULT_GROUP_COLORS)
        marks = list(markers) if markers is not None else list(_DEFAULT_GROUP_MARKERS)

        for i, g in enumerate(group_keys):
            idxs = [j for j, k in enumerate(keys) if k == g]
            gx = x_all[idxs]
            gy = y_all[idxs]
            style = {}
            if group_styles and g in group_styles:
                style = dict(group_styles[g])
            color = style.get("color", colors[i % len(colors)])
            marker = style.get("marker", marks[i % len(marks)])
            # Default group label: material_a(hkl)/material_b(hkl) when possible
            if style.get("label"):
                label = style.get("label")
            elif group_labels and g in group_labels:
                label = group_labels[g]
            elif group_label_format == "group_key":
                label = str(g)
            elif group_label_format == "match_space":
                # Attempt to derive label from candidate rows for this group
                subset_rows = [p for p in candidates if _get_group_key(p) == g]

                def _first(k: str):
                    for r in subset_rows:
                        v = get_feature(r, k, default=None)
                        if v is not None:
                            return v
                    return None

                ma = _first("material_a") or _first("material")
                mb = _first("material_b") or None
                ma_h = _first("miller_a") or _first("miller") or None
                mb_h = _first("miller_b") or None

                def _fmt_hkl(h):
                    try:
                        if h is None:
                            return ""
                        if isinstance(h, str):
                            hs = re.sub(r"[()\s]", "", h)
                            parts = hs.split(",")
                            if len(parts) == 3:
                                return f"({parts[0]}{parts[1]}{parts[2]})"
                            return f"({hs})"
                        seq = tuple(int(x) for x in h)
                        return f"({seq[0]}{seq[1]}{seq[2]})"
                    except Exception:
                        return ""

                if ma and mb:
                    # Drop common persisted optimization suffixes for concise labels
                    def _strip_opt(s: str) -> str:
                        try:
                            return re.sub(r"(_opt|-opt)$", "", str(s))
                        except Exception:
                            return str(s)

                    ma_clean = _strip_opt(ma)
                    mb_clean = _strip_opt(mb)

                    # Build plain label first for safe truncation
                    plain_label = (
                        f"{ma_clean}{_fmt_hkl(ma_h)}/{mb_clean}{_fmt_hkl(mb_h)}"
                    )
                    if (
                        legend_label_maxlen
                        and isinstance(plain_label, str)
                        and len(plain_label) > legend_label_maxlen
                    ):
                        trunc = max(0, int(legend_label_maxlen) - 1)
                        label = plain_label[:trunc] + "…"
                    else:
                        # Convert material formula text into math-tex with
                        # subscripts for digits
                        def _format_formula_latex_inner(s: str) -> str:
                            # Return the inner mathtext body (no surrounding $)
                            toks = re.findall(r"([A-Z][a-z]?)(\d*)", str(s))
                            if not toks:
                                return str(s)
                            parts: list[str] = []
                            for el, cnt in toks:
                                if cnt:
                                    parts.append(f"\\mathrm{{{el}}}_{{{cnt}}}")
                                else:
                                    parts.append(f"\\mathrm{{{el}}}")
                            return "".join(parts)

                        def _fmt_hkl_math(h):
                            try:
                                if h is None:
                                    return ""
                                if isinstance(h, str):
                                    hs = re.sub(r"[()\s]", "", h)
                                    parts = hs.split(",")
                                    if len(parts) == 3:
                                        s = "".join(parts)
                                        return f"(\\mathrm{{{s}}})"
                                    return f"(\\mathrm{{{hs}}})"
                                seq = tuple(int(x) for x in h)
                                return f"(\\mathrm{{{seq[0]}{seq[1]}{seq[2]}}})"
                            except Exception:
                                return ""

                        ma_inner = _format_formula_latex_inner(ma_clean)
                        mb_inner = _format_formula_latex_inner(mb_clean)
                        label = (
                            f"${ma_inner}{_fmt_hkl_math(ma_h)}/"
                            f"{mb_inner}{_fmt_hkl_math(mb_h)}$"
                        )
                else:
                    # fallback to group key string
                    label = str(g)

            # truncate long plain labels only (do not truncate mathtext labels)
            if legend_label_maxlen and isinstance(label, str):
                # If label is mathtext (starts and ends with $), skip truncation
                if not (label.startswith("$") and label.endswith("$")):
                    if len(label) > legend_label_maxlen:
                        label = label[: max(0, int(legend_label_maxlen) - 1)] + "…"
            ax.scatter(
                gx,
                gy,
                marker=marker,
                s=style.get("size", candidate_size),
                color=color,
                alpha=style.get("alpha", candidate_alpha),
                label=label,
            )

        # pareto_sc placeholder for grouped case
        # When grouped and a global front is requested, we'll compute it later.
        # Per-group fronts are computed after group iteration.

    # Draw Pareto front(s) depending on front_scope
    if front_scope not in {"global", "per_group", "both", "none"}:
        front_scope = "global"

    def _draw_front(xs, ys, color, label_fmt=None, label_val=None, style=front_style):
        if len(xs) == 0:
            return

        # Plot one attainable objective point per x coordinate. The named CALM
        # policy intentionally retains candidates with equal quantized
        # objectives, but drawing all raw floating-point representatives can
        # introduce zero-width vertical artifacts in the visual envelope.
        order = np.lexsort((ys, xs))
        fx, fy = xs[order], ys[order]
        keep = np.ones(fx.size, dtype=bool)
        keep[1:] = fx[1:] != fx[:-1]
        fx, fy = fx[keep], fy[keep]
        front_label = label_fmt.format(label_val) if label_fmt else None

        def _mark_attainable_points(*, label=None):
            ax.scatter(
                fx,
                fy,
                marker=pareto_marker,
                s=pareto_size,
                color=color,
                alpha=pareto_alpha,
                linewidths=front_markeredgewidth,
                label=label,
                zorder=3,
            )

        if fx.size == 1:
            _mark_attainable_points(label=front_label)
            return

        plot_style = front_plot_style
        # If user provided explicit plot style string, use it (e.g., '-x')
        if plot_style:
            ax.plot(
                fx,
                fy,
                plot_style,
                color=color,
                linewidth=front_linewidth,
                markeredgewidth=front_markeredgewidth,
                markersize=front_marker_size,
                label=front_label,
            )
            return

        # Fallback to linestyle + marker
        if style == "line":
            ax.plot(
                fx,
                fy,
                "-",
                color=color,
                linewidth=front_linewidth,
                marker=pareto_marker,
                markersize=front_marker_size,
                markeredgewidth=front_markeredgewidth,
                label=front_label,
            )
        elif style == "step":
            xs2, ys2 = _stair_step_path(fx, fy)
            ax.plot(
                xs2,
                ys2,
                "-",
                color=color,
                linewidth=front_linewidth,
                label=front_label,
            )
            _mark_attainable_points()

    if group_by is None:
        if (
            front_scope in {"global", "both"}
            and len(x_p) >= 2
            and show_front
            and front_style != "none"
        ):
            fc = global_front_color or pareto_color
            _draw_front(x_p, y_p, fc, label_fmt="Global Pareto")
    else:
        # Group-local envelopes are drawn first. When both scopes are requested,
        # the aggregate envelope is then drawn on top so its black line remains
        # legible where it coincides with a search-local front.
        if front_scope in {"per_group", "both"} and show_front:
            for i, g in enumerate(group_keys):
                subset = [p for p in candidates if _get_group_key(p) == g]
                if not subset:
                    continue
                pf = _pareto_subset(subset, x=x, y=y, ids=ids)
                gx = np.asarray(
                    [_to_float(get_feature(p, x, default=np.nan)) for p in pf]
                )
                gy = np.asarray(
                    [_to_float(get_feature(p, y, default=np.nan)) for p in pf]
                )
                group_style: Mapping[str, Any] = (
                    group_styles.get(g) if group_styles and g in group_styles else {}
                )
                color = group_style.get(
                    "color", _DEFAULT_GROUP_COLORS[i % len(_DEFAULT_GROUP_COLORS)]
                )
                fs = group_style.get("front_style", front_style)

                # The scatter legend already identifies each search by color.
                # Add separate front labels only when explicitly requested.
                label_fmt = "{0} Pareto" if group_front_legend else None
                _draw_front(
                    gx,
                    gy,
                    color,
                    label_fmt=label_fmt,
                    label_val=g,
                    style=fs,
                )

        if front_scope in {"global", "both"} and show_front:
            if explicit_pareto:
                gx = x_p
                gy = y_p
            else:
                pf = _pareto_subset(candidates, x=x, y=y, ids=ids)
                gx = np.asarray(
                    [_to_float(get_feature(p, x, default=np.nan)) for p in pf]
                )
                gy = np.asarray(
                    [_to_float(get_feature(p, y, default=np.nan)) for p in pf]
                )
            fc = global_front_color or pareto_color
            _draw_front(gx, gy, fc, label_fmt="Global Pareto")

    # Preserve explicit lower-level labels when supplied by a direct caller.
    x_label = _pretty_label(orig_x if orig_x is not None else x, axis="x")
    y_label = _pretty_label(orig_y if orig_y is not None else y, axis="y")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    if title is None:
        title = f"Pareto front: {x_label} vs {y_label}"
    if show_title:
        ax.set_title(title)

    # Legend placement
    if legend:
        if legend_outside:
            # place legend to the right outside the plot
            bbox = legend_bbox_to_anchor or (1.02, 0.5)
            ax.legend(
                loc="center left",
                bbox_to_anchor=bbox,
                ncol=legend_ncol,
                title=legend_title,
                fontsize=legend_fontsize,
                title_fontsize=legend_title_fontsize,
            )
            try:
                fig.subplots_adjust(right=legend_right_margin)
            except Exception:
                try:
                    fig.tight_layout()
                except Exception:
                    pass
        else:
            ax.legend(
                loc=legend_loc,
                ncol=legend_ncol,
                title=legend_title,
                fontsize=legend_fontsize,
                title_fontsize=legend_title_fontsize,
            )

    # Annotation (do this before saving so the saved figure includes text)
    if annotate is not None and annotate_scope in {"all", "pareto"}:
        try:
            if annotate_scope == "all":
                for p, xv, yv in zip(candidates, x_all, y_all):
                    lab = get_feature(p, annotate, default=None)
                    if lab is not None:
                        ax.annotate(str(lab), (xv, yv))
            else:  # pareto only
                for p, xv, yv in zip(pareto, x_p, y_p):
                    lab = get_feature(p, annotate, default=None)
                    if lab is not None:
                        ax.annotate(str(lab), (xv, yv))
        except Exception:
            pass

    if _savepath is not None:
        save_figure(fig, _savepath, dpi=dpi)

    if show and plt is not None:
        plt.show()

    return fig, ax
