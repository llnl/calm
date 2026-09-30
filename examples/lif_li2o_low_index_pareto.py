#!/usr/bin/env python3
"""Enumerate low-index LiF/Li2O interfaces and plot their Pareto fronts.

This standalone program uses only CALM's supported public API. It creates one
persistent project, optimizes the package-owned LiF and Li2O tutorial structures
with GRACE, generates their (100), (110), and (111) surfaces, runs all nine
orientation-pair searches, exports the complete candidate population, and plots
the global Pareto candidates and their discrete envelope in logarithmic-strain-
norm versus estimated-interface-atom-count space.

The bulk optimizations are required provenance for calculator-backed strain
partitioning, registry refinement, energy evaluation, and relaxation. Merely
configuring a calculator after a geometry-only search cannot supply that
provenance retroactively.

Place this file in CALM's ``examples/`` directory to keep generated work under
``examples/work/``. Re-running the program resumes identical completed searches.

Required installation extras::

    python -m pip install -e ".[science,plot,grace]"

Generated artifacts are written below ``WORK_DIR / "outputs-grace"``.
"""

from __future__ import annotations

import csv
from itertools import product
from pathlib import Path

from calm import (
    Material,
    Potential,
    SearchSettings,
    open_project,
    tutorial_structure,
)
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator, PercentFormatter


# -----------------------------------------------------------------------------
# Configuration
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

MATERIAL_A = "LiF_opt"
MATERIAL_B = "Li2O_opt"
SOURCE_MATERIAL_A = "LiF_source"
SOURCE_MATERIAL_B = "Li2O_source"

POTENTIAL_MODEL = "GRACE-1L-OMAT"
POTENTIAL_DEVICE = "cpu"
POTENTIAL_QUIET = True

BULK_OPTIMIZATION_FMAX = 0.01
BULK_OPTIMIZATION_STEPS = 500
BULK_RELAX_CELL = True

# Side A contributes its top face; side B contributes its bottom face.
# These are explicit modeling choices, not surface-stability predictions.
# In particular, the polar (111) pair exposes Li on LiF and O on Li2O.
SURFACE_SELECTORS = {
    (MATERIAL_A, (1, 0, 0)): {"termination_top": "LiF"},
    (MATERIAL_A, (1, 1, 0)): {"termination_top": "LiF"},
    (MATERIAL_A, (1, 1, 1)): {"termination_top": "Li"},
    (MATERIAL_B, (1, 0, 0)): {"termination_bottom": "O"},
    (MATERIAL_B, (1, 1, 0)): {"termination_bottom": "Li₂O"},
    (MATERIAL_B, (1, 1, 1)): {"termination_bottom": "O"},
}

SURFACE_LAYERS = 3
SURFACE_VACUUM_A = 10.0

# These settings define the expanded, low-strain enumeration used for this
# figure. A large retained-result ceiling is used because the figure must
# contain every unique candidate admitted within these bounds. The
# enumeration-audit check below fails loudly if this ceiling is ever reached.
SEARCH_SETTINGS = SearchSettings(
    max_principal_strain=0.03,
    max_supercell_index=50,
    max_atoms=1000,
    max_candidates=100_000,
    mismatch_weight=0.5,
)

SEARCH_PREFIX = "lif-li2o-low-index-v1"

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

# Typography sizes in points at the exported 5.6-inch panel width. If the
# panel will be rescaled during multipanel assembly, increase these values by
# the inverse of that scale factor so the final printed sizes remain legible.
LEGEND_FONT_SIZE = 12.0
AXIS_LABEL_FONT_SIZE = 16.0
TICK_LABEL_FONT_SIZE = 14.0

# Color encodes the LiF orientation; marker encodes the Li2O orientation.
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
    """Return the stable public name for one orientation-pair search."""

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


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write homogeneous summary rows without adding a pandas dependency."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def ensure_optimized_material(
    project,
    potential,
    *,
    tutorial_name: str,
    formula_name: str,
    source_name: str,
    optimized_name: str,
):
    """Return an existing optimized bulk or create it with provenance."""

    try:
        material = project.material(optimized_name)
    except KeyError:
        source = project.add_material(
            Material.from_ase(
                tutorial_structure(tutorial_name),
                name=formula_name,
            ),
            name=source_name,
        )
        return project.optimize_material(
            source,
            potential=potential,
            fmax=BULK_OPTIMIZATION_FMAX,
            steps=BULK_OPTIMIZATION_STEPS,
            relax_cell=BULK_RELAX_CELL,
            name=optimized_name,
        )

    if getattr(material, "optimized_with", None) is None:
        raise RuntimeError(
            f"Material {optimized_name!r} exists without calculator provenance. "
            "Use a new PROJECT_DIR for the calculator-backed workflow."
        )
    print(f"Reusing calculator-backed material {optimized_name!r}.")
    return material


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = open_project(PROJECT_DIR, summarize=True)

    potential = Potential.grace(
        POTENTIAL_MODEL,
        device=POTENTIAL_DEVICE,
        quiet=POTENTIAL_QUIET,
    )
    potential.validate()
    project.configure(mlip="grace", calculator=potential.to_spec())

    # Source structures and GRACE-optimized bulks are persisted separately. The
    # optimized records carry the calculator provenance required by every
    # subsequent calculator-backed interface workflow. Existing optimized
    # records are reused so completed searches retain stable source identities.
    ensure_optimized_material(
        project,
        potential,
        tutorial_name="lif",
        formula_name="LiF",
        source_name=SOURCE_MATERIAL_A,
        optimized_name=MATERIAL_A,
    )
    ensure_optimized_material(
        project,
        potential,
        tutorial_name="li2o",
        formula_name="Li2O",
        source_name=SOURCE_MATERIAL_B,
        optimized_name=MATERIAL_B,
    )

    project.generate_surfaces(
        [MATERIAL_A, MATERIAL_B],
        millers=list(MILLERS),
        layers=SURFACE_LAYERS,
        vacuum=SURFACE_VACUUM_A,
        enumerate_terminations=True,
    )
    project.surfaces().write_table(
        OUTPUT_DIR / "surface-catalog.csv",
        view="all",
    )

    selected_surfaces = {}
    selected_surface_rows: list[dict[str, object]] = []
    for material in (MATERIAL_A, MATERIAL_B):
        for miller in MILLERS:
            selector = SURFACE_SELECTORS[(material, miller)]
            surface = project.surface(
                material=material,
                miller=miller,
                **selector,
            )
            selected_surfaces[(material, miller)] = surface
            selected_surface_rows.append(
                {
                    "material": material,
                    "miller": compact_hkl(miller),
                    "surface_id": surface.id_short,
                    "surface_uid": surface.uid_full,
                    "termination": surface.termination,
                    "termination_top": surface.termination_top,
                    "termination_bottom": surface.termination_bottom,
                    "termination_shift": surface.termination_shift,
                }
            )

    write_csv(OUTPUT_DIR / "selected-surfaces.csv", selected_surface_rows)

    names: list[str] = []
    summary_rows: list[dict[str, object]] = []
    for miller_a, miller_b in product(MILLERS, repeat=2):
        name = search_name(miller_a, miller_b)
        names.append(name)
        surface_a = selected_surfaces[(MATERIAL_A, miller_a)]
        surface_b = selected_surfaces[(MATERIAL_B, miller_b)]

        print(f"\nRunning or resuming {name}")
        search = project.search_interfaces(
            surface_a,
            surface_b,
            settings=SEARCH_SETTINGS,
            name=name,
            resume=False,
        )
        print(search.summary())

        audit = search.enumeration_audit()
        audit.write_tables(OUTPUT_DIR / "enumeration-audits" / name)
        pair_totals = audit.totals["pairs"]

        candidates = search.candidates()
        retained_count = len(candidates)
        unique_count = pair_totals["primitive_classes_created"]
        if retained_count != unique_count:
            raise RuntimeError(
                f"Search {name!r} retained {retained_count} of "
                f"{unique_count} unique admitted candidates. Increase "
                "SEARCH_SETTINGS.max_candidates and use a new SEARCH_PREFIX."
            )

        local_pareto = candidates.pareto(scope="authoritative")
        local_pareto.write_table(
            OUTPUT_DIR / "pair-local-pareto" / f"{name}.csv",
            view="strain",
        )
        pareto_count = len(local_pareto)
        summary_rows.append(
            {
                "search_name": name,
                "lif_miller": compact_hkl(miller_a),
                "li2o_miller": compact_hkl(miller_b),
                "lif_surface_id": surface_a.id_short,
                "li2o_surface_id": surface_b.id_short,
                "lif_contact_face": surface_a.termination_top,
                "li2o_contact_face": surface_b.termination_bottom,
                "candidate_sources_admitted": pair_totals[
                    "candidates_admitted"
                ],
                "unique_candidates": unique_count,
                "retained_candidates": retained_count,
                "pareto_candidates": pareto_count,
            }
        )

    write_csv(OUTPUT_DIR / "search-summary.csv", summary_rows)

    all_candidates = project.candidates().where(search_name=names)
    if len(all_candidates) == 0:
        raise RuntimeError("The nine searches produced no interface candidates.")

    all_candidates.write_table(
        OUTPUT_DIR / "candidates-all.csv",
        view="all",
    )
    aggregate_pareto = all_candidates.pareto(scope="computed")
    aggregate_pareto.write_table(
        OUTPUT_DIR / "candidates-aggregate-pareto.csv",
        view="strain",
    )
    aggregate_pareto_rows = aggregate_pareto.to_rows(view="all")

    group_styles = {}
    for miller_a, miller_b in product(MILLERS, repeat=2):
        name = search_name(miller_a, miller_b)
        group_styles[name] = {
            "color": LIF_COLORS[miller_a],
            "marker": LI2O_MARKERS[miller_b],
        }

    fig, ax = all_candidates.plot_pareto(
        x="n_atoms_estimate",
        y="strain_norm",
        front="global",
        group_by="search_name",
        group_order=names,
        group_styles=group_styles,
        front_scope="global",
        front_style="step",
        front_plot_style=None,
        global_front_color="black",
        legend=False,
        figsize=figure_size(),
        candidate_alpha=0.25,
        candidate_size=50,
        pareto_size=0,
        front_linewidth=1.5,
        show_title=False,
    )

    # Emphasize the global Pareto set while retaining the surface-pair
    # encoding. A black outline distinguishes globally nondominated candidates
    # from the faint background population.
    for miller_a, miller_b in product(MILLERS, repeat=2):
        name = search_name(miller_a, miller_b)
        rows = [
            row
            for row in aggregate_pareto_rows
            if row.get("search_name") == name
        ]
        if not rows:
            continue
        ax.scatter(
            [float(row["n_atoms_estimate"]) for row in rows],
            [float(row["strain_norm"]) for row in rows],
            s=50,
            marker=LI2O_MARKERS[miller_b],
            facecolors=LIF_COLORS[miller_a],
            edgecolors="black",
            linewidths=1.0,
            alpha=1.0,
            zorder=5,
        )

    ax.set_xlabel(r"Atoms in interface cell, $N_\mathrm{atoms}$")
    ax.set_ylabel(
        r"Log. strain, $\|\mathbf{E}\|_\mathrm{F}$ (%)"
    )
    ax.yaxis.set_major_locator(MultipleLocator(0.01))
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0, decimals=0))
    ax.set_ylim(
        0.0,
        1.02 * (2.0**0.5) * float(SEARCH_SETTINGS.max_principal_strain),
    )
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="0.90", linewidth=0.6)
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
    ax.margins(x=0.03)

    # Factorize the surface-pair encoding so readers need not decode nine
    # redundant pair entries. Color denotes LiF orientation and marker shape
    # denotes Li2O orientation. Pair-local Pareto sets are exported above but
    # intentionally not emphasized here: the main panel is organized around
    # the global size-strain trade-off.
    # Use line swatches—not markers—for LiF. This legend explains color only;
    # showing circles here would incorrectly imply that marker shape also
    # encodes the LiF orientation.
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

    # The black outlines and staircase are explained in the caption rather
    # than repeated in a separate status legend. When enabled, the factorized
    # orientation key occupies its own band above the unchanged plotting box.
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

    pdf_path = OUTPUT_DIR / "pareto-strain-norm-vs-atoms.pdf"
    png_path = OUTPUT_DIR / "pareto-strain-norm-vs-atoms.png"
    # Do not use bbox_inches="tight" here: tight cropping changes the known
    # physical dimensions used to assemble matched multipanel figures.
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=300)

    print("\nCompleted all nine LiF/Li2O low-index searches.")
    print(f"Candidates: {len(all_candidates)}")
    print(f"Global Pareto candidates: {len(aggregate_pareto)}")
    print(f"Project: {PROJECT_DIR}")
    print(f"Outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
