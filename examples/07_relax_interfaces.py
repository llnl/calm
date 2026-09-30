"""Example 07: Typed persistent structural relaxation.

This example reopens the shared project, selects the authoritative
``registry_refined`` interfaces created by Example 06, and executes one
synchronous persisted relaxation run.

The default ``real`` backend performs calculator-backed ASE relaxation using
the calculator provenance persisted by the earlier material workflow. Set
``CALM_EXAMPLE_07_BACKEND=deterministic`` only for dependency-light persistence
and resume testing; that synthetic backend does not optimize geometry.

Raw final total energies are reported by the relaxation stage. Derived
interface-energy or adhesion conventions remain outside this example and are
introduced only by the later energetics workflow.
"""

from __future__ import annotations

import os
from pathlib import Path

from calm import RelaxSettings, open_project

EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"

SEARCH_NAME = "LiF_Li2O_100_interface_match"
BACKEND = os.environ.get("CALM_EXAMPLE_07_BACKEND", "real")
FMAX = float(os.environ.get("CALM_EXAMPLE_07_FMAX", "0.05"))
STEPS = int(os.environ.get("CALM_EXAMPLE_07_STEPS", "500"))
RELAX_CELL = os.environ.get("CALM_EXAMPLE_07_RELAX_CELL", "0") == "1"


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py through "
            "examples/06_refine_interfaces.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = open_project(PROJECT_DIR, summarize=True)
    # --8<-- [start:tutorial-relaxation-workflow]
    workflow = project.relax_interfaces(
        search_name=SEARCH_NAME,
        settings=RelaxSettings(
            fmax=FMAX,
            steps=STEPS,
            relax_cell=RELAX_CELL,
        ),
        backend=BACKEND,
        resume=True,
        partial_resume=True,
        on_error="raise",
        stage="registry_refined",
    )

    print(workflow.summary())
    workflow.write_table(
        OUTPUT_DIR / "07_relaxation_results.csv",
    )
    workflow.relaxed_interfaces.write_table(
        OUTPUT_DIR / "07_relaxed_interfaces.csv",
    )
    workflow.relaxed_interfaces.write_table(
        OUTPUT_DIR / "07_relaxed_interface_strain.csv",
        view="strain",
    )
    # --8<-- [end:tutorial-relaxation-workflow]


if __name__ == "__main__":
    main()
