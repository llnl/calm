"""Example 03: Interface matching from persisted surfaces.

This example builds on Example 01 and Example 02 in this repository.

Run order:
  1) examples/01_optimize_materials.py
  2) examples/02_generate_surfaces.py
  3) examples/03_search_interfaces.py  <- this example

This script demonstrates Level 3 (Interface Matching): select two persisted
surfaces, run lattice matching, persist the search result, query candidate rows
from the Project, filter candidates, export tables, and generate a Pareto plot.

Note: This example expects the project and persisted surfaces created by
Example 01/02. If those are missing, the script raises a clear error telling
the user which preparatory example to run first.
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

    project = open_project(PROJECT_DIR, summarize=True)

    # Display persisted surfaces using the public display_table helper.
    # The public API will handle display-mode differences between notebooks
    # and scripts; examples should not implement ad-hoc fallbacks.
    project.surfaces().to_table(title="Persisted surfaces", max_width=200, max_col_width=30).display()

    # --8<-- [start:tutorial-search-workflow]
    # Single-pair example: side A contributes its top face and side B
    # contributes its bottom face. Select the Li2O_opt (100) slab whose
    # interface-facing bottom termination is O.
    surface_a = project.surface(
        material="LiF_opt",
        miller=(1, 0, 0),
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

    search_name = "LiF_Li2O_100_interface_match"

    print(f"Running interface matching: {search_name}")
    search = project.search_interfaces(
        surface_a,
        surface_b,
        settings=settings,
        name=search_name,
    )
    # --8<-- [end:tutorial-search-workflow]

    if search.empty:
        print("No candidates were found.")
        print(search.explain())
        return

    print("Search summary:\n", search.summary())

    # --8<-- [start:tutorial-search-resume-export]
    # Reopen the named persisted search and use its scoped candidate query.
    # This keeps candidate retrieval and readiness reporting on one typed object.
    candidates = search.candidates()

    # Report buildability for the named search using the persisted-search
    # summary API. This is the preferred, non-mutating check to see whether
    # the persisted candidates can produce buildable interfaces.
    summary = search.buildability_summary()
    print("Persisted search readiness summary:\n", summary.summary())

    # Keep routine output focused on comparison metrics. Complete candidate
    # provenance remains available through the full normalized row.
    candidates.to_table(title="Candidates").display()

    # Filter low-strain candidates and export
    low_strain = candidates.where(max_principal_strain=(None, 0.08))

    all_csv = OUTPUT_DIR / "03_candidates_all.csv"
    low_csv = OUTPUT_DIR / "03_candidates_low_strain.csv"
    pareto_png = OUTPUT_DIR / "03_pareto_atoms_vs_mismatch.png"

    candidates.write_table(all_csv)
    low_strain.write_table(low_csv)

    # Plotting requires matplotlib; allow its ImportError to surface so users
    # can install optional plotting dependencies when running examples.
    candidates.plot_pareto(
        x="n_atoms_estimate",
        y="d_cell",
        front_style="step",
        front_plot_style=None,
        save=pareto_png,
    )
    print(f"Pareto plot written to: {pareto_png}")

    print(f"Candidate table written to: {all_csv}")
    print(f"Low-strain table written to: {low_csv}")
    # --8<-- [end:tutorial-search-resume-export]


if __name__ == "__main__":
    main()
