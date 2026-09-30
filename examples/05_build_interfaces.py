"""Example 05: Build interfaces from a named search (Level 4).

This example demonstrates the pragmatic Level 4 workflow used by the
revised examples: recover persisted candidate rows from a named search,
ensure buildable prototypes are available (or instruct the user to rerun
the named search), build authoritative interfaces using BuildSettings,
persist them through the Project workflow, and export structure files.

The example is intentionally conservative: it will not attempt heavy
recomputations (e.g. a full lattice-matching search) when prerequisites
are missing. Instead it prints clear instructions and exits with success
so automated test harnesses that run examples remain robust.
"""

from __future__ import annotations

from pathlib import Path

from calm import BuildSettings, open_project

EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"

BUILD_TOP = 3


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    project = open_project(PROJECT_DIR, summarize=True)

    # Named search created by Example 03 from explicit persisted surface
    # termination selections.
    search_name = "LiF_Li2O_100_interface_match"

    # Use the persisted-search view for named-search inspection.
    persisted = project.search(search_name)
    candidates = persisted.candidates()

    # If no candidates were persisted, instruct the user to run Example 03.
    if not candidates:
        print(f"No persisted candidates found for named search: {search_name}")
        print(
            "Run examples/03_search_interfaces.py first to create the "
            "named search and persist candidates."
        )
        return

    # Display the exact Pareto-and-score selection used by build_interfaces(),
    # rather than repeating every persisted candidate and its internal
    # ranking/provenance fields. Complete rows remain in project state.
    sel = candidates.select(pareto=True).select_top(BUILD_TOP, by="score")
    if not sel:
        print("No Pareto candidates to build.")
        return
    sel.to_table(
        title="Pareto candidates selected for construction",
    ).display()

    # Buildable prototypes are persisted by the named Project search. The
    # public API handles rehydration and surfaces authoritative persistence
    # errors directly if required prototypes are unavailable.

    # Use the persisted-search view for a stable, non-throwing
    # buildability/readiness summary.
    summary = persisted.buildability_summary()
    print(summary.summary())
    if not summary.ok:
        print(summary.explain())
        return

    # --8<-- [start:tutorial-build-workflow]
    bsettings = BuildSettings(strain_partition="both", alpha=0.5, gap=1.5, vacuum=15.0)

    interfaces = project.build_interfaces(
        persisted,
        top=BUILD_TOP,
        settings=bsettings,
        name_prefix="built_interface",
    )

    # Write structures and a table of built interfaces.
    paths = interfaces.write_structures(OUTPUT_DIR, format="vasp")
    interfaces.write_table(
        OUTPUT_DIR / "05_built_interfaces.csv",
        view="construction",
    )
    interfaces.write_table(
        OUTPUT_DIR / "05_built_interface_strain.csv",
        view="strain",
    )
    # --8<-- [end:tutorial-build-workflow]

    if paths:
        print(f"Wrote {len(paths)} interface files to: {OUTPUT_DIR}")
    else:
        print("No interface files were written.")


if __name__ == "__main__":
    main()
