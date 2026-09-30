#!/usr/bin/env python3
"""Plot completed LiF/Li2O refinement/relaxation results during a live run.

This helper is deliberately read-only with respect to the CALM project. It
combines candidate-specific refinement CSV files with authoritative completed
relaxation records exposed by CALM's public API. It never launches a calculator
or a workflow and writes its outputs to a separate ``partial-plots`` directory.

Run once::

    python lif_li2o_plot_partial_refine_relax.py

Refresh every two minutes until interrupted with Ctrl-C::

    python lif_li2o_plot_partial_refine_relax.py --watch 120

Use ``--summary-only`` to skip the larger strain-partition and Monte Carlo
small-multiple figures. Use ``--show-legend`` for self-contained panels.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from math import ceil, isclose, isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, PercentFormatter

from calm import open_project


# -----------------------------------------------------------------------------
# Default paths
# -----------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
WORK_DIR = SCRIPT_DIR / "work" / "lif-li2o-low-index-pareto"
PROJECT_DIR = WORK_DIR / "lif-li2o-low-index-grace.calm"
RESULTS_DIR = WORK_DIR / "outputs-grace" / "refine-relax"
CANDIDATE_TABLE = WORK_DIR / "outputs-grace" / "candidates-all.csv"
OUTPUT_DIR = RESULTS_DIR / "partial-plots"

EXPECTED_REGISTRY_OBJECTIVE = (
    "unrelaxed_total_energy_density_eV_per_A2"
)
EXPECTED_REGISTRY_UNITS = "eV_per_A2"


# -----------------------------------------------------------------------------
# Figure configuration
# -----------------------------------------------------------------------------

FIGURE_WIDTH_IN = 5.6
AXES_WIDTH_TO_HEIGHT = 1.25
LEFT_MARGIN_IN = 0.86
RIGHT_MARGIN_IN = 0.14
BOTTOM_MARGIN_IN = 0.70
TOP_MARGIN_IN = 0.10
LEGEND_BAND_HEIGHT_IN = 0.42

DETAIL_FIGURE_WIDTH_IN = 7.2
DETAIL_NCOLS = 2
DETAIL_PANEL_HEIGHT_IN = 2.45

LEGEND_FONT_SIZE = 9.0
AXIS_LABEL_FONT_SIZE = 12.0
TICK_LABEL_FONT_SIZE = 10.0
DETAIL_TITLE_FONT_SIZE = 9.0

CANDIDATE_ALPHA = 1.0
CANDIDATE_SIZE = 46
CANDIDATE_EDGE_WIDTH = 0.7

MILLERS = (
    (1, 0, 0),
    (1, 1, 0),
    (1, 1, 1),
)
LIF_COLORS = {
    (1, 0, 0): "#0072B2",
    (1, 1, 0): "#D55E00",
    (1, 1, 1): "#009E73",
}
LI2O_MARKERS = {
    (1, 0, 0): "o",
    (1, 1, 0): "s",
    (1, 1, 1): "^",
}
SEARCH_PATTERN = re.compile(
    r"-lif-(100|110|111)-li2o-(100|110|111)$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=PROJECT_DIR,
        help="CALM project directory (default: %(default)s)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=RESULTS_DIR,
        help="Active refine-relax output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--candidate-table",
        type=Path,
        default=CANDIDATE_TABLE,
        help="Aggregate enumerated-candidate CSV (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Separate partial-plot output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--watch",
        type=float,
        metavar="SECONDS",
        help="Refresh repeatedly at this interval until Ctrl-C",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Create only the three relaxation-versus-strain figures",
    )
    parser.add_argument(
        "--show-legend",
        action="store_true",
        help="Include the factorized orientation legend in summary figures",
    )
    args = parser.parse_args()
    if args.watch is not None and args.watch <= 0.0:
        parser.error("--watch must be greater than zero")
    return args


def read_csv_snapshot(path: Path, *, attempts: int = 3) -> list[dict[str, str]]:
    """Read one CSV while tolerating a writer briefly replacing its contents."""

    if not path.is_file() or path.stat().st_size == 0:
        return []
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with path.open(newline="", encoding="utf-8") as stream:
                return [dict(row) for row in csv.DictReader(stream)]
        except (OSError, UnicodeError, csv.Error) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.1)
    raise RuntimeError(f"Could not read a stable snapshot of {path}") from last_error


def ordered_fieldnames(
    rows: Sequence[Mapping[str, Any]],
    preferred: Sequence[str] = (),
) -> list[str]:
    keys = {str(key) for row in rows for key in row}
    fields = [name for name in preferred if name in keys]
    fields.extend(sorted(keys.difference(fields)))
    return fields


def atomic_write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    preferred: Sequence[str] = (),
) -> None:
    """Replace a CSV only after its new contents are completely written."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    fields = ordered_fieldnames(rows, preferred)
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        if fields:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    temporary.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def as_float(value: Any, *, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is missing or non-numeric") from exc
    if not isfinite(result):
        raise ValueError(f"{name} is non-finite")
    return result


def as_int(value: Any, *, name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is missing or non-integral") from exc
    return result


def is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def orientation_from_search(
    search_name: str,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    match = SEARCH_PATTERN.search(search_name)
    if match is None:
        raise ValueError(f"Cannot parse orientations from {search_name!r}")
    return (
        tuple(int(value) for value in match.group(1)),
        tuple(int(value) for value in match.group(2)),
    )


def compact_hkl(miller: tuple[int, int, int]) -> str:
    return "".join(str(value) for value in miller)


def candidate_metadata(
    candidate: Mapping[str, Any],
    *,
    candidate_key: str,
) -> dict[str, Any]:
    search_name = str(candidate["search_name"])
    miller_a, miller_b = orientation_from_search(search_name)
    candidate_uid = (
        candidate.get("candidate_uid")
        or candidate.get("project_prototype_uid")
        or candidate.get("prototype_uid")
    )
    return {
        "candidate_key": candidate_key,
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "candidate_uid": str(candidate_uid or ""),
        "project_prototype_id": str(
            candidate.get("project_prototype_id") or ""
        ),
        "search_name": search_name,
        "lif_surface": f"({compact_hkl(miller_a)})",
        "li2o_surface": f"({compact_hkl(miller_b)})",
        "lif_miller": compact_hkl(miller_a),
        "li2o_miller": compact_hkl(miller_b),
        "n_atoms_estimate": as_int(
            candidate["n_atoms_estimate"],
            name="n_atoms_estimate",
        ),
        "strain_norm": as_float(
            candidate["strain_norm"],
            name="strain_norm",
        ),
        "isotropic_strain_norm": as_float(
            candidate["isotropic_strain_norm"],
            name="isotropic_strain_norm",
        ),
        "deviatoric_strain_norm": as_float(
            candidate["deviatoric_strain_norm"],
            name="deviatoric_strain_norm",
        ),
    }


def candidate_index(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv_snapshot(path)
    if not rows:
        raise RuntimeError(f"Candidate table is missing or empty: {path}")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        prototype_id = str(
            row.get("project_prototype_id")
            or row.get("prototype_id")
            or ""
        )
        if prototype_id:
            result[prototype_id] = row
    if not result:
        raise RuntimeError(f"Candidate table lacks prototype IDs: {path}")
    return result


def add_metadata(
    rows: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> list[dict[str, Any]]:
    return [{**dict(metadata), **dict(row)} for row in rows]


def collect_refinement_files(
    results_dir: Path,
    candidates: Mapping[str, Mapping[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    """Collect stable candidate CSV snapshots and relaxation target metadata."""

    strain_points: list[dict[str, Any]] = []
    registry_trace: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    selected_candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    candidate_root = results_dir / "candidates"
    if not candidate_root.is_dir():
        return strain_points, registry_trace, targets, selected_candidates, [
            f"Candidate output directory does not exist yet: {candidate_root}"
        ]

    for directory in sorted(path for path in candidate_root.iterdir() if path.is_dir()):
        try:
            registry_rows = read_csv_snapshot(
                directory / "registry_search_results.csv"
            )
            interface_rows = read_csv_snapshot(
                directory / "registry_refined_interfaces.csv"
            )
            strain_rows = read_csv_snapshot(
                directory / "strain_partition_results.csv"
            )
            trace_rows = read_csv_snapshot(
                directory / "registry_search_trace.csv"
            )
            if not registry_rows or not interface_rows:
                warnings.append(f"{directory.name}: refinement files incomplete")
                continue
            registry = registry_rows[0]
            interface = interface_rows[0]
            prototype_id = str(registry.get("prototype_id") or "")
            candidate = candidates.get(prototype_id)
            if candidate is None:
                warnings.append(
                    f"{directory.name}: prototype {prototype_id!r} is not in "
                    "the candidate table"
                )
                continue
            metadata = candidate_metadata(
                candidate,
                candidate_key=directory.name,
            )
            annotated_candidate = {**dict(candidate), **metadata}
            selected_candidates.append(annotated_candidate)
            strain_points.extend(add_metadata(strain_rows, metadata))
            registry_trace.extend(add_metadata(trace_rows, metadata))

            objective = (
                trace_rows[0].get("objective") if trace_rows else None
            )
            units = (
                trace_rows[0].get("objective_units") if trace_rows else None
            )
            if objective and objective != EXPECTED_REGISTRY_OBJECTIVE:
                warnings.append(
                    f"{directory.name}: unsupported registry objective "
                    f"{objective!r}"
                )
                continue
            if units and units != EXPECTED_REGISTRY_UNITS:
                warnings.append(
                    f"{directory.name}: unsupported registry units {units!r}"
                )
                continue

            selected_alpha_rows = [
                row for row in strain_rows if is_true(row.get("is_selected"))
            ]
            selected_alpha = (
                as_float(selected_alpha_rows[0]["alpha"], name="alpha")
                if len(selected_alpha_rows) == 1
                else None
            )
            targets.append(
                {
                    **metadata,
                    "registry_interface_id": str(interface["id_short"]),
                    "n_atoms": as_int(interface["n_atoms"], name="n_atoms"),
                    "interface_area_A2": as_float(
                        interface["area_A2"],
                        name="area_A2",
                    ),
                    "unrelaxed_energy_density_eV_per_A2": as_float(
                        registry["score"],
                        name="registry score",
                    ),
                    "registry_shift_frac_a": registry.get(
                        "registry_shift_frac_a"
                    ),
                    "selected_alpha": selected_alpha,
                }
            )
        except (KeyError, RuntimeError, ValueError) as exc:
            warnings.append(f"{directory.name}: {exc}")

    selected_candidates.sort(
        key=lambda row: (
            int(row["n_atoms_estimate"]),
            float(row["strain_norm"]),
            str(row["candidate_uid"]),
        )
    )
    return (
        strain_points,
        registry_trace,
        targets,
        selected_candidates,
        warnings,
    )


def complete_relaxation_rows(project: Any) -> list[dict[str, Any]]:
    """Read completed relaxation records through the public API."""

    return project.relaxation_results().to_rows(view="all")


def interface_uid_by_short_id(project: Any) -> dict[str, str]:
    """Map persisted registry-refined short IDs to full authoritative UIDs."""

    rows = project.refined_interfaces(
        stage="registry_refined"
    ).to_rows(view="all")
    return {
        str(row["id_short"]): str(row["uid_full"])
        for row in rows
        if row.get("id_short") and row.get("uid_full")
    }


def usable_relaxation(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("status") or "") in {"done", "completed"}
        and is_true(row.get("converged"))
        and row.get("failure") in (None, "", {})
        and row.get("final_energy_eV") is not None
    )


def choose_relaxation(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate_key: str,
    warnings: list[str],
) -> Mapping[str, Any] | None:
    usable = [row for row in rows if usable_relaxation(row)]
    if not usable:
        return None
    energies = [
        as_float(row["final_energy_eV"], name="final_energy_eV")
        for row in usable
    ]
    if len(usable) > 1 and not all(
        isclose(value, energies[0], rel_tol=1.0e-12, abs_tol=1.0e-10)
        for value in energies[1:]
    ):
        warnings.append(
            f"{candidate_key}: multiple completed relaxations have different "
            "energies; no result was selected"
        )
        return None
    return sorted(usable, key=lambda row: str(row.get("uid_full") or ""))[-1]


def assemble_summary(
    project: Any,
    targets: Sequence[Mapping[str, Any]],
    warnings: list[str],
) -> list[dict[str, Any]]:
    """Join refinement targets to completed persistent relaxation records."""

    interface_uids = interface_uid_by_short_id(project)
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in complete_relaxation_rows(project):
        target_uid = row.get("target_uid_full")
        if target_uid:
            grouped[str(target_uid)].append(row)

    summary: list[dict[str, Any]] = []
    for target in targets:
        candidate_key = str(target["candidate_key"])
        target_uid = interface_uids.get(str(target["registry_interface_id"]))
        if target_uid is None:
            warnings.append(
                f"{candidate_key}: registry interface is not currently readable "
                "from the project"
            )
            continue
        relaxed = choose_relaxation(
            grouped.get(target_uid, []),
            candidate_key=candidate_key,
            warnings=warnings,
        )
        if relaxed is None:
            continue
        area = float(target["interface_area_A2"])
        density = float(target["unrelaxed_energy_density_eV_per_A2"])
        n_atoms = int(target["n_atoms"])
        unrelaxed_energy = density * area
        relaxed_energy = as_float(
            relaxed["final_energy_eV"],
            name="final_energy_eV",
        )
        delta_energy = relaxed_energy - unrelaxed_energy
        summary.append(
            {
                **dict(target),
                "registry_interface_uid": target_uid,
                "relaxation_result_uid": relaxed.get("uid_full"),
                "unrelaxed_energy_source": (
                    "registry_selected_objective_times_area"
                ),
                "unrelaxed_energy_eV": unrelaxed_energy,
                "relaxed_energy_eV": relaxed_energy,
                "relaxation_energy_eV": delta_energy,
                "relaxation_energy_eV_per_atom": delta_energy / n_atoms,
                "relaxation_converged": True,
                "relaxation_steps": relaxed.get("n_steps"),
                "max_force_eV_per_A": relaxed.get("max_force_eV_per_A"),
            }
        )
    summary.sort(
        key=lambda row: (
            int(row["n_atoms"]),
            float(row["strain_norm"]),
            str(row["candidate_uid"]),
        )
    )
    return summary


def figure_size(*, show_legend: bool) -> tuple[float, float]:
    axes_width = FIGURE_WIDTH_IN - LEFT_MARGIN_IN - RIGHT_MARGIN_IN
    axes_height = axes_width / AXES_WIDTH_TO_HEIGHT
    legend_height = LEGEND_BAND_HEIGHT_IN if show_legend else 0.0
    return (
        FIGURE_WIDTH_IN,
        BOTTOM_MARGIN_IN + axes_height + legend_height + TOP_MARGIN_IN,
    )


def configure_panel_layout(fig: Any, ax: Any) -> None:
    figure_width, figure_height = fig.get_size_inches()
    axes_width = figure_width - LEFT_MARGIN_IN - RIGHT_MARGIN_IN
    axes_height = axes_width / AXES_WIDTH_TO_HEIGHT
    fig.subplots_adjust(
        left=LEFT_MARGIN_IN / figure_width,
        right=1.0 - RIGHT_MARGIN_IN / figure_width,
        bottom=BOTTOM_MARGIN_IN / figure_height,
        top=(BOTTOM_MARGIN_IN + axes_height) / figure_height,
    )
    ax.set_box_aspect(1.0 / AXES_WIDTH_TO_HEIGHT)


def style_axes(ax: Any, *, grid_axis: str = "both") -> None:
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color="0.90", linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(direction="out", width=0.8, labelsize=TICK_LABEL_FONT_SIZE)


def orientation_legend_handles() -> list[Line2D]:
    lif_handles = [
        Line2D(
            [],
            [],
            color=LIF_COLORS[miller],
            linewidth=4.0,
            solid_capstyle="butt",
            label=(
                rf"LiF: $({compact_hkl(miller)})$"
                if index == 0
                else rf"$({compact_hkl(miller)})$"
            ),
        )
        for index, miller in enumerate(MILLERS)
    ]
    li2o_handles = [
        Line2D(
            [],
            [],
            linestyle="none",
            marker=LI2O_MARKERS[miller],
            markersize=5.5,
            markerfacecolor="0.35",
            markeredgecolor="none",
            label=(
                rf"Li$_2$O: $({compact_hkl(miller)})$"
                if index == 0
                else rf"$({compact_hkl(miller)})$"
            ),
        )
        for index, miller in enumerate(MILLERS)
    ]
    return lif_handles + li2o_handles


def add_orientation_legend(fig: Any, *, show_legend: bool) -> None:
    if not show_legend:
        return
    figure_height = fig.get_figheight()
    fig.legend(
        handles=orientation_legend_handles(),
        loc="upper center",
        bbox_to_anchor=(0.5, 1.0 - TOP_MARGIN_IN / figure_height),
        ncol=6,
        frameon=False,
        fontsize=LEGEND_FONT_SIZE,
        borderaxespad=0.0,
        handlelength=1.1,
        handletextpad=0.35,
        columnspacing=0.8,
        markerfirst=False,
    )


def save_figure(fig: Any, output_dir: Path, stem: str) -> None:
    """Atomically refresh vector and high-resolution raster plots."""

    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix, options in ((".pdf", {}), (".png", {"dpi": 300})):
        target = output_dir / f"{stem}{suffix}"
        temporary = target.with_name(f".{stem}.tmp{suffix}")
        fig.savefig(temporary, **options)
        temporary.replace(target)
    plt.close(fig)


def panel_label(index: int) -> str:
    label = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(97 + remainder) + label
    return label


def detail_title(metadata: Mapping[str, Any], index: int) -> str:
    return (
        f"{panel_label(index)}) {metadata['candidate_id']}  "
        f"LiF{metadata['lif_surface']}/Li$_2$O{metadata['li2o_surface']}  "
        f"$N={metadata['n_atoms_estimate']}$"
    )


def detail_figure(n_panels: int) -> tuple[Any, list[Any]]:
    ncols = min(DETAIL_NCOLS, max(1, n_panels))
    nrows = ceil(n_panels / ncols)
    height = 0.85 + nrows * DETAIL_PANEL_HEIGHT_IN
    fig, axes_array = plt.subplots(
        nrows,
        ncols,
        figsize=(DETAIL_FIGURE_WIDTH_IN, height),
        squeeze=False,
    )
    axes = list(axes_array.flat)
    fig.subplots_adjust(
        left=0.105,
        right=0.985,
        bottom=0.075,
        top=1.0 - 0.20 / height,
        wspace=0.30,
        hspace=0.48,
    )
    for ax in axes:
        ax.set_box_aspect(0.80)
    return fig, axes


def plot_strain_partition_grid(
    rows: Sequence[Mapping[str, Any]],
    metadata_by_key: Mapping[str, Mapping[str, Any]],
    order: Sequence[str],
    output_dir: Path,
) -> None:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["candidate_key"])].append(row)
    keys = [key for key in order if grouped.get(key)]
    if not keys:
        return

    fig, axes = detail_figure(len(keys))
    for index, key in enumerate(keys):
        ax = axes[index]
        metadata = metadata_by_key[key]
        miller_a, miller_b = orientation_from_search(
            str(metadata["search_name"])
        )
        points = sorted(grouped[key], key=lambda row: float(row["alpha"]))
        energies = [
            float(row["potential_energy_density_eV_per_A2"])
            for row in points
        ]
        reference = min(energies)
        relative = [1000.0 * (value - reference) for value in energies]
        alphas = [float(row["alpha"]) for row in points]
        ax.plot(
            alphas,
            relative,
            color=LIF_COLORS[miller_a],
            linewidth=1.3,
            marker=LI2O_MARKERS[miller_b],
            markersize=3.8,
            markeredgewidth=0.0,
        )
        for position, row in enumerate(points):
            if is_true(row.get("is_selected")):
                ax.scatter(
                    [alphas[position]],
                    [relative[position]],
                    s=48,
                    marker=LI2O_MARKERS[miller_b],
                    facecolor=LIF_COLORS[miller_a],
                    edgecolor="black",
                    linewidth=CANDIDATE_EDGE_WIDTH,
                    zorder=5,
                )
        ax.set_title(
            detail_title(metadata, index),
            fontsize=DETAIL_TITLE_FONT_SIZE,
            loc="left",
        )
        ax.set_xlim(-0.02, 1.02)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        style_axes(ax)

    for ax in axes[len(keys) :]:
        ax.set_visible(False)
    fig.supxlabel(
        r"Strain-partition parameter, $\alpha$",
        fontsize=AXIS_LABEL_FONT_SIZE,
        y=0.015,
    )
    fig.supylabel(
        r"Energy above minimum (meV $\mathrm{\AA}^{-2}$)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        x=0.018,
    )
    save_figure(fig, output_dir, "strain-partition-energy-vs-alpha")


def plot_registry_trace_grid(
    rows: Sequence[Mapping[str, Any]],
    metadata_by_key: Mapping[str, Mapping[str, Any]],
    order: Sequence[str],
    output_dir: Path,
) -> None:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["candidate_key"])].append(row)
    keys = [key for key in order if grouped.get(key)]
    if not keys:
        return

    fig, axes = detail_figure(len(keys))
    for index, key in enumerate(keys):
        ax = axes[index]
        metadata = metadata_by_key[key]
        miller_a, _ = orientation_from_search(str(metadata["search_name"]))
        trace = sorted(grouped[key], key=lambda row: int(row["step"]))
        reference = min(float(row["best_score"]) for row in trace)
        steps = [int(row["step"]) for row in trace]
        current = [
            1000.0 * (float(row["current_score"]) - reference)
            for row in trace
        ]
        best = [
            1000.0 * (float(row["best_score"]) - reference)
            for row in trace
        ]
        ax.plot(steps, current, color="0.65", linewidth=0.8, alpha=0.75)
        ax.plot(steps, best, color=LIF_COLORS[miller_a], linewidth=1.5)
        ax.set_title(
            detail_title(metadata, index),
            fontsize=DETAIL_TITLE_FONT_SIZE,
            loc="left",
        )
        ax.set_xlim(min(steps), max(steps))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        style_axes(ax)

    for ax in axes[len(keys) :]:
        ax.set_visible(False)
    fig.supxlabel("Monte Carlo step", fontsize=AXIS_LABEL_FONT_SIZE, y=0.015)
    fig.supylabel(
        r"Energy above best (meV $\mathrm{\AA}^{-2}$)",
        fontsize=AXIS_LABEL_FONT_SIZE,
        x=0.018,
    )
    save_figure(fig, output_dir, "registry-monte-carlo-energy-trace")


def y_limits_with_zero(values: Sequence[float]) -> tuple[float, float]:
    lower = min(values)
    upper = max(max(values), 0.0)
    span = upper - lower
    if span <= 0.0:
        span = max(abs(lower), 0.01)
    padding = 0.08 * span
    return lower - padding, upper + padding


def plot_relaxation_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    x_key: str,
    x_label: str,
    stem: str,
    output_dir: Path,
    show_legend: bool,
) -> None:
    if not rows:
        return
    fig, ax = plt.subplots(figsize=figure_size(show_legend=show_legend))
    for row in rows:
        miller_a, miller_b = orientation_from_search(str(row["search_name"]))
        ax.scatter(
            [float(row[x_key])],
            [float(row["relaxation_energy_eV_per_atom"])],
            s=CANDIDATE_SIZE,
            marker=LI2O_MARKERS[miller_b],
            facecolor=LIF_COLORS[miller_a],
            edgecolor="black",
            linewidth=CANDIDATE_EDGE_WIDTH,
            alpha=CANDIDATE_ALPHA,
            zorder=4,
        )

    x_values = [float(row[x_key]) for row in rows]
    y_values = [float(row["relaxation_energy_eV_per_atom"]) for row in rows]
    x_upper = max(x_values)
    if x_upper <= 0.0:
        x_upper = 0.01
    ax.set_xlim(-0.025 * x_upper, 1.06 * x_upper)
    ax.set_ylim(*y_limits_with_zero(y_values))
    ax.axhline(0.0, color="0.35", linewidth=0.8, zorder=1)
    ax.set_xlabel(x_label)
    ax.set_ylabel(
        r"Relaxation energy per atom, $\Delta E_\mathrm{relax}/N$ "
        r"(eV atom$^{-1}$)"
    )
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=1))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.xaxis.label.set_size(AXIS_LABEL_FONT_SIZE)
    ax.yaxis.label.set_size(AXIS_LABEL_FONT_SIZE)
    style_axes(ax)
    configure_panel_layout(fig, ax)
    add_orientation_legend(fig, show_legend=show_legend)
    save_figure(fig, output_dir, stem)


def make_figures(
    strain_points: Sequence[Mapping[str, Any]],
    registry_trace: Sequence[Mapping[str, Any]],
    selected_candidates: Sequence[Mapping[str, Any]],
    summary: Sequence[Mapping[str, Any]],
    *,
    output_dir: Path,
    summary_only: bool,
    show_legend: bool,
) -> None:
    metadata_by_key = {
        str(row["candidate_key"]): row for row in selected_candidates
    }
    order = [str(row["candidate_key"]) for row in selected_candidates]
    if not summary_only:
        plot_strain_partition_grid(
            strain_points,
            metadata_by_key,
            order,
            output_dir,
        )
        plot_registry_trace_grid(
            registry_trace,
            metadata_by_key,
            order,
            output_dir,
        )

    plot_relaxation_summary(
        summary,
        x_key="strain_norm",
        x_label=r"Logarithmic strain norm, $\|\mathbf{E}\|_\mathrm{F}$ (%)",
        stem="relaxation-energy-vs-log-strain",
        output_dir=output_dir,
        show_legend=show_legend,
    )
    plot_relaxation_summary(
        summary,
        x_key="isotropic_strain_norm",
        x_label=(
            r"Isotropic logarithmic strain norm, "
            r"$\|\mathbf{E}_\mathrm{iso}\|_\mathrm{F}$ (%)"
        ),
        stem="relaxation-energy-vs-isotropic-log-strain",
        output_dir=output_dir,
        show_legend=show_legend,
    )
    plot_relaxation_summary(
        summary,
        x_key="deviatoric_strain_norm",
        x_label=(
            r"Deviatoric logarithmic strain norm, "
            r"$\|\mathbf{E}_\mathrm{dev}\|_\mathrm{F}$ (%)"
        ),
        stem="relaxation-energy-vs-deviatoric-log-strain",
        output_dir=output_dir,
        show_legend=show_legend,
    )


def scan_once(project: Any, args: argparse.Namespace) -> None:
    candidates = candidate_index(args.candidate_table)
    (
        strain_points,
        registry_trace,
        targets,
        selected_candidates,
        warnings,
    ) = collect_refinement_files(args.results_dir, candidates)
    summary = assemble_summary(project, targets, warnings)

    make_figures(
        strain_points,
        registry_trace,
        selected_candidates,
        summary,
        output_dir=args.output_dir,
        summary_only=args.summary_only,
        show_legend=args.show_legend,
    )
    preferred = (
        "candidate_key",
        "candidate_id",
        "candidate_uid",
        "search_name",
        "lif_surface",
        "li2o_surface",
        "n_atoms",
        "strain_norm",
        "isotropic_strain_norm",
        "deviatoric_strain_norm",
        "unrelaxed_energy_eV",
        "relaxed_energy_eV",
        "relaxation_energy_eV",
        "relaxation_energy_eV_per_atom",
    )
    atomic_write_csv(
        args.output_dir / "partial-relaxation-energy-summary.csv",
        summary,
        preferred=preferred,
    )
    timestamp = datetime.now(timezone.utc).isoformat()
    status = {
        "updated_utc": timestamp,
        "candidate_directories": len(
            [
                path
                for path in (args.results_dir / "candidates").glob("*")
                if path.is_dir()
            ]
        ),
        "refinements_read": len(targets),
        "complete_relaxation_pairs": len(summary),
        "pending_or_incomplete": max(0, len(targets) - len(summary)),
        "warnings": len(warnings),
    }
    atomic_write_csv(
        args.output_dir / "partial-status.csv",
        [status],
        preferred=tuple(status),
    )
    atomic_write_text(
        args.output_dir / "partial-read-warnings.txt",
        "\n".join(warnings) + ("\n" if warnings else ""),
    )
    print(
        f"[{timestamp}] Read {len(targets)} refinements and "
        f"{len(summary)} complete relaxation pairs."
    )
    print(f"Partial outputs: {args.output_dir}")
    if warnings:
        print(
            f"Skipped or pending items: {len(warnings)}; see "
            f"{args.output_dir / 'partial-read-warnings.txt'}"
        )


def main() -> None:
    args = parse_args()
    if not args.project_dir.is_dir():
        raise FileNotFoundError(f"CALM project not found: {args.project_dir}")
    if not args.results_dir.is_dir():
        raise FileNotFoundError(
            f"Refine-relax output directory not found: {args.results_dir}"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    project = open_project(args.project_dir, summarize=False)

    if args.watch is None:
        scan_once(project, args)
        return

    print(
        f"Watching partial results every {args.watch:g} s. "
        "Press Ctrl-C to stop."
    )
    try:
        while True:
            try:
                scan_once(project, args)
            except Exception as exc:
                timestamp = datetime.now(timezone.utc).isoformat()
                print(f"[{timestamp}] Snapshot failed: {exc}")
                print("The active writer was not interrupted; retrying.")
            time.sleep(args.watch)
    except KeyboardInterrupt:
        print("\nStopped partial-result watcher.")


if __name__ == "__main__":
    main()
