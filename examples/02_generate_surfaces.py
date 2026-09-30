"""Example 02: Generate primitive surface slabs, query, and export.

This example reopens the project created by Example 01, generates primitive
surface slabs for multiple Miller orientations from persisted optimized
materials, lists the generated slabs, and exports selected slabs as POSCAR
files. The example demonstrates label-based retrieval and explicit,
termination-aware surface selection through the public Project facade.
"""

from __future__ import annotations

from pathlib import Path

from calm import open_project

EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"


def main():
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --8<-- [start:tutorial-surface-workflow]
    project = open_project(PROJECT_DIR, summarize=True)

    project.materials().where(kind="optimized").to_table(title="Optimized materials", max_width=200, max_col_width=30).display()

    # Retrieve the optimized material by its user-facing label.
    lif_opt = project.material("LiF_opt")
    print("Retrieved LiF_opt:")
    print(lif_opt.summary())

    # Generate and export slabs using project-level helpers
    millers = [(1, 0, 0), (1, 1, 0), (1, 1, 1)]
    project.generate_surfaces(["LiF_opt", "Li2O_opt"], millers=millers, layers=4, vacuum=15.0)

    surfaces = project.surfaces()
    surfaces.to_table(
        view="characterization",
        title="Persisted surface characterization",
    ).display()
    surfaces.write_table(
        OUTPUT_DIR / "02_surface_catalog.csv",
        view="characterization",
    )

    # Demonstrate exact, termination-aware selection. These selections are the
    # persisted surfaces used by Examples 03-06.
    lif_100 = project.surface(
        material="LiF_opt",
        miller=(1, 0, 0),
        termination="LiF",
        termination_shift=0,
    )
    li2o_100_o_facing = project.surface(
        material="Li2O_opt",
        miller=(1, 0, 0),
        termination_bottom="O",
        termination_shift=1,
    )
    print("Selected LiF surface:", lif_100.summary())
    print(lif_100.characterize().summary())
    print("Selected Li2O surface:", li2o_100_o_facing.summary())
    print(li2o_100_o_facing.characterize().summary())

    # Export by material criteria
    written = project.export_surfaces(materials=["LiF_opt", "Li2O_opt"], millers=millers, directory=OUTPUT_DIR, format="vasp")
    print(f"Exported {len(written)} surface POSCAR files to: {OUTPUT_DIR}")
    # --8<-- [end:tutorial-surface-workflow]


if __name__ == "__main__":
    main()
