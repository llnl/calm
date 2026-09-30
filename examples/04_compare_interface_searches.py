"""Example 04: Compare interface searches and grouped Pareto plots.

This example continues from Example 03. It runs a second interface search,
then demonstrates grouped Pareto plots comparing the Example 03 search,
the new Example 04 search, and the entire candidate database.

Generated plots are written under the shared ``examples/outputs/`` directory.
"""

from __future__ import annotations

from pathlib import Path

from calm import SearchSettings, open_project


EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    project = open_project(PROJECT_DIR)

    # Example 03 search name (pre-existing)
    search_03 = "LiF_Li2O_100_interface_match"

    # --8<-- [start:tutorial-comparison-workflow]
    # New search: one explicit LiF_opt (110) termination against the same
    # Li2O_opt (100) slab with an O-terminated interface-facing bottom face.
    surface_a = project.surface(
        material="LiF_opt",
        miller=(1, 1, 0),
        termination="LiF",
        termination_shift=0,
    )
    surface_b = project.surface(
        material="Li2O_opt",
        miller=(1, 0, 0),
        termination_bottom="O",
        termination_shift=1,
    )

    settings = SearchSettings(
        max_principal_strain=0.15,
        max_supercell_index=12,
        max_atoms=1000,
        max_candidates=500,
        mismatch_weight=0.5,
    )

    search_04 = "LiF_Li2O_110_100_interface_match"
    print(f"Running new interface matching: {search_04}")
    search4 = project.search_interfaces(
        surface_a,
        surface_b,
        settings=settings,
        name=search_04,
    )
    print("Search 04 summary:\n", search4.summary())

    # Retrieve candidate collections
    c03 = project.candidates().search(search_03)
    c04 = project.candidates().search(search_04)
    allc = project.candidates()

    # Provide per-search buildability summaries as a quick sanity check.
    b03 = project.search(search_03).buildability_summary()
    b04 = search4.buildability_summary()
    print("Search 03 summary:\n", b03.summary())
    print("Search 04 summary:\n", b04.summary())

    # Simple single-search plots
    p03 = OUTPUT_DIR / "04_pareto_search_03.png"
    p04 = OUTPUT_DIR / "04_pareto_search_04.png"
    c03.plot_pareto(
        x="n_atoms_estimate",
        y="d_cell",
        front_style="step",
        front_plot_style=None,
        save=p03,
    )
    c04.plot_pareto(
        x="n_atoms_estimate",
        y="d_cell",
        front_style="step",
        front_plot_style=None,
        save=p04,
    )
    print(f"Wrote: {p03}")
    print(f"Wrote: {p04}")

    # Composite grouped plot comparing the two searches
    pcomp = OUTPUT_DIR / "04_pareto_compare_searches.png"
    allc.where(search_name=[search_03, search_04]).plot_pareto(
        x="n_atoms_estimate",
        y="d_cell",
        group_by="search_name",
        front_scope="both",
        group_styles={
            search_03: {"color": "tab:blue", "marker": "o"},
            search_04: {"color": "tab:orange", "marker": "s"},
        },
        legend_title="Search space",
        front_style="step",
        front_plot_style=None,
        global_front_color="k",
        legend_outside=True,
        show_title=False,
        save=pcomp,
    )
    print(f"Wrote: {pcomp}")
    # --8<-- [end:tutorial-comparison-workflow]

    # Entire database grouped plot (many searches may exist)
    pall = OUTPUT_DIR / "04_pareto_all_database.png"
    allc.plot_pareto(
        x="n_atoms_estimate",
        y="d_cell",
        group_by="search_name",
        front_scope="both",
        front_style="step",
        front_plot_style=None,
        global_front_color="k",
        legend_outside=True,
        show_title=False,
        save=pall,
    )
    print(f"Wrote: {pall}")


if __name__ == "__main__":
    main()
