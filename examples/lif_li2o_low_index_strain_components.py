#!/usr/bin/env python3
"""Plot isotropic versus deviatoric strain for the nine LiF/Li2O searches.

This plotting-only companion to ``lif_li2o_low_index_pareto.py`` reads the same
persistent CALM project and plots every retained interface candidate in
isotropic-logarithmic-strain-norm versus deviatoric-logarithmic-strain-norm
space. Color identifies the LiF orientation and marker shape identifies the
Li2O orientation.

By default, candidates on the existing global atom-count-versus-total-strain
Pareto front receive black outlines. No new Pareto relation is computed in the
displayed component space. Set ``HIGHLIGHT_GLOBAL_PARETO = False`` to omit that
cross-panel reference.

Run ``lif_li2o_low_index_pareto.py`` first so the shared project contains all
nine completed searches. Generated files are written below
``WORK_DIR / "outputs-grace"``.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path

from calm import open_project
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator, PercentFormatter


# -----------------------------------------------------------------------------
# Shared project and search identity
# -----------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
WORK_DIR = SCRIPT_DIR / "work" / "lif-li2o-low-index-pareto"
PROJECT_DIR = WORK_DIR / "lif-li2o-low-index-grace.calm"
OUTPUT_DIR = WORK_DIR / "outputs-grace"

MILLERS = (
    (1, 0, 0),
    (1, 1, 0),
    (1, 1, 1),
)

SEARCH_PREFIX = "lif-li2o-low-index-v1"
MAX_PRINCIPAL_STRAIN = 0.03


# -----------------------------------------------------------------------------
# Figure configuration
# -----------------------------------------------------------------------------

# Set this to True for a self-contained panel or False when a shared legend is
# supplied during multipanel assembly. Enabling the legend adds a dedicated
# band above the axes instead of shrinking the data region.
SHOW_LEGEND = False

# Physical panel geometry. AXES_WIDTH_TO_HEIGHT controls only the plotting box;
# the exported canvas height is calculated from the axes height, fixed margins,
# and the optional legend band. A ratio of 1.25 gives a balanced 5:4 panel.
FIGURE_WIDTH_IN = 5.6
AXES_WIDTH_TO_HEIGHT = 1.25
LEFT_MARGIN_IN = 0.86
RIGHT_MARGIN_IN = 0.14
BOTTOM_MARGIN_IN = 0.70
TOP_MARGIN_IN = 0.10
LEGEND_BAND_HEIGHT_IN = 0.42

# Display-only padding below the physical lower bound of zero. This keeps
# markers centered on either zero-strain axis from being clipped by the axes.
LOWER_AXIS_PADDING_FRACTION = 0.03

LEGEND_FONT_SIZE = 12.0
AXIS_LABEL_FONT_SIZE = 16.0
TICK_LABEL_FONT_SIZE = 14.0

CANDIDATE_ALPHA = 0.25
CANDIDATE_SIZE = 50

HIGHLIGHT_GLOBAL_PARETO = True
GLOBAL_PARETO_SIZE = 50
GLOBAL_PARETO_EDGE_WIDTH = 1.0

# Color encodes the LiF orientation; marker shape encodes the Li2O
# orientation, matching the atom-count-versus-total-strain companion panel.
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


def compact_hkl(miller: tuple[int, int, int]) -> str:
    """Return a compact Miller label such as ``100`` or ``111``."""

    return "".join(str(value) for value in miller)


def search_name(
    miller_a: tuple[int, int, int],
    miller_b: tuple[int, int, int],
) -> str:
    """Return the stable name shared with the enumeration script."""

    return (
        f"{SEARCH_PREFIX}-lif-{compact_hkl(miller_a)}"
        f"-li2o-{compact_hkl(miller_b)}"
    )


def figure_size() -> tuple[float, float]:
    """Return a canvas size that preserves the requested axes geometry."""

    if FIGURE_WIDTH_IN <= LEFT_MARGIN_IN + RIGHT_MARGIN_IN:
        raise ValueError("Figure width must exceed the horizontal margins.")
    if AXES_WIDTH_TO_HEIGHT <= 0.0:
        raise ValueError("AXES_WIDTH_TO_HEIGHT must be positive.")

    axes_width = FIGURE_WIDTH_IN - LEFT_MARGIN_IN - RIGHT_MARGIN_IN
    axes_height = axes_width / AXES_WIDTH_TO_HEIGHT
    legend_height = LEGEND_BAND_HEIGHT_IN if SHOW_LEGEND else 0.0
    figure_height = (
        BOTTOM_MARGIN_IN + axes_height + legend_height + TOP_MARGIN_IN
    )
    return FIGURE_WIDTH_IN, figure_height


def configure_panel_layout(fig, ax) -> None:
    """Apply inch-based margins without changing the axes aspect ratio."""

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


def print_global_pareto_table(
    pareto_rows: list[dict[str, object]],
) -> None:
    """Print the global size-strain Pareto candidates as a compact table."""

    if not pareto_rows:
        print("\nGlobal Pareto front: no candidates")
        return

    orientations = {
        search_name(miller_a, miller_b): (miller_a, miller_b)
        for miller_a, miller_b in product(MILLERS, repeat=2)
    }
    sorted_rows = sorted(
        pareto_rows,
        key=lambda row: (
            float(row["n_atoms_estimate"]),
            float(row["strain_norm"]),
            str(row.get("search_name", "")),
        ),
    )

    headers = (
        "LiF surface",
        "Li2O surface",
        "N atoms",
        "Strain (%)",
        "Isotropic (%)",
        "Deviatoric (%)",
    )
    table_rows = []
    for row in sorted_rows:
        name = str(row["search_name"])
        miller_a, miller_b = orientations[name]
        table_rows.append(
            (
                f"({compact_hkl(miller_a)})",
                f"({compact_hkl(miller_b)})",
                str(int(round(float(row["n_atoms_estimate"])))),
                f"{100.0 * float(row['strain_norm']):.4f}",
                f"{100.0 * float(row['isotropic_strain_norm']):.4f}",
                f"{100.0 * float(row['deviatoric_strain_norm']):.4f}",
            )
        )

    widths = [
        max(len(headers[index]), *(len(row[index]) for row in table_rows))
        for index in range(len(headers))
    ]
    numeric_columns = {2, 3, 4, 5}

    def format_row(values: tuple[str, ...]) -> str:
        cells = []
        for index, value in enumerate(values):
            alignment = ">" if index in numeric_columns else "<"
            cells.append(f" {value:{alignment}{widths[index]}} ")
        return "|" + "|".join(cells) + "|"

    separator = "|" + "|".join(
        "-" * (width + 2) for width in widths
    ) + "|"

    print("\nGlobal Pareto front: atom count versus total strain")
    print(format_row(headers))
    print(separator)
    for row in table_rows:
        print(format_row(row))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = open_project(PROJECT_DIR, summarize=True)

    names = [
        search_name(miller_a, miller_b)
        for miller_a, miller_b in product(MILLERS, repeat=2)
    ]
    all_candidates = project.candidates().where(search_name=names)
    rows = all_candidates.to_rows(view="all")
    if not rows:
        raise RuntimeError(
            "No candidates were found for the nine low-index searches. Run "
            "lif_li2o_low_index_pareto.py first."
        )

    present_names = {
        str(row["search_name"])
        for row in rows
        if row.get("search_name") is not None
    }
    missing_names = [name for name in names if name not in present_names]
    if missing_names:
        missing = "\n  - ".join(missing_names)
        raise RuntimeError(
            "The shared project does not contain candidates from every "
            f"required search:\n  - {missing}\nRun "
            "lif_li2o_low_index_pareto.py to complete the search set."
        )

    required_metrics = (
        "n_atoms_estimate",
        "strain_norm",
        "isotropic_strain_norm",
        "deviatoric_strain_norm",
    )
    incomplete_rows = [
        row.get("candidate_id") or row.get("candidate_uid") or "unknown"
        for row in rows
        if any(row.get(metric) is None for metric in required_metrics)
    ]
    if incomplete_rows:
        preview = ", ".join(str(value) for value in incomplete_rows[:5])
        raise RuntimeError(
            "CALM did not expose complete strain-component metrics for "
            f"{len(incomplete_rows)} candidates (first values: {preview})."
        )

    all_candidates.write_table(
        OUTPUT_DIR / "candidates-strain-components.csv",
        view="strain",
    )
    global_pareto_rows = (
        all_candidates.pareto(scope="computed").to_rows(view="all")
    )
    print_global_pareto_table(global_pareto_rows)

    group_styles = {}
    for miller_a, miller_b in product(MILLERS, repeat=2):
        name = search_name(miller_a, miller_b)
        group_styles[name] = {
            "color": LIF_COLORS[miller_a],
            "marker": LI2O_MARKERS[miller_b],
        }

    fig, ax = all_candidates.plot_pareto(
        x="isotropic_strain_norm",
        y="deviatoric_strain_norm",
        front=False,
        group_by="search_name",
        group_order=names,
        group_styles=group_styles,
        legend=False,
        figsize=figure_size(),
        candidate_alpha=CANDIDATE_ALPHA,
        candidate_size=CANDIDATE_SIZE,
        show_title=False,
    )

    # Preserve the cross-panel identity of candidates on the global
    # atom-count-versus-total-strain Pareto front. These black outlines do not
    # denote a newly computed Pareto front in the displayed component space.
    if HIGHLIGHT_GLOBAL_PARETO:
        for miller_a, miller_b in product(MILLERS, repeat=2):
            name = search_name(miller_a, miller_b)
            pair_rows = [
                row
                for row in global_pareto_rows
                if row.get("search_name") == name
            ]
            if not pair_rows:
                continue
            ax.scatter(
                [float(row["isotropic_strain_norm"]) for row in pair_rows],
                [float(row["deviatoric_strain_norm"]) for row in pair_rows],
                s=GLOBAL_PARETO_SIZE,
                marker=LI2O_MARKERS[miller_b],
                facecolors=LIF_COLORS[miller_a],
                edgecolors="black",
                linewidths=GLOBAL_PARETO_EDGE_WIDTH,
                alpha=1.0,
                zorder=5,
            )

    ax.set_xlabel(
        r"Isotropic log. strain, "
        r"$\|\mathbf{E}_\mathrm{iso}\|_\mathrm{F}$ (%)"
    )
    ax.set_ylabel(
        r"Deviatoric log. strain, "
        r"$\|\mathbf{E}_\mathrm{dev}\|_\mathrm{F}$ (%)"
    )

    component_bound = (2.0**0.5) * float(MAX_PRINCIPAL_STRAIN)
    lower_axis_padding = LOWER_AXIS_PADDING_FRACTION * component_bound
    component_limit = 1.02 * component_bound
    ax.set_xlim(-lower_axis_padding, component_limit)
    ax.set_ylim(-lower_axis_padding, component_limit)
    ax.xaxis.set_major_locator(MultipleLocator(0.01))
    ax.yaxis.set_major_locator(MultipleLocator(0.01))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))

    ax.set_axisbelow(True)
    ax.grid(color="0.90", linewidth=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(
        direction="out",
        width=0.8,
        labelsize=TICK_LABEL_FONT_SIZE,
    )
    ax.xaxis.label.set_size(AXIS_LABEL_FONT_SIZE)
    ax.yaxis.label.set_size(AXIS_LABEL_FONT_SIZE)

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
    configure_panel_layout(fig, ax)

    if SHOW_LEGEND:
        figure_height = fig.get_figheight()
        fig.legend(
            handles=lif_handles + li2o_handles,
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

    pdf_path = OUTPUT_DIR / "isotropic-vs-deviatoric-strain.pdf"
    png_path = OUTPUT_DIR / "isotropic-vs-deviatoric-strain.png"
    # Preserve the known physical dimensions for matched multipanel assembly.
    # In particular, do not add bbox_inches="tight" to these save calls.
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=300)

    print("\nCompleted isotropic/deviatoric strain plot.")
    print(f"Candidates: {len(all_candidates)}")
    print(f"Project: {PROJECT_DIR}")
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
