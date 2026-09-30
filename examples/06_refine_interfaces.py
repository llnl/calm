"""Example 06: Geodesic strain partitioning + registry search.

This example demonstrates a durable follow-up workflow using the Project
followup APIs. It performs:

- A geodesic strain-partition scan over authoritative built interfaces created
  by Example 05 and selected from a named search.
- Registry Monte Carlo searches seeded from the best-alpha derived interfaces.
- Persistence of distinct strain-partitioned and registry-refined interfaces.
- Export of CSV summaries and the potential-energy-density curve used by the
  explicit strain-selection objective.

Notes
-----
- This example requires prototype records with calculator provenance (a
  bulk optimized with a registered calculator). If calculator provenance is
  missing the followups will fail with a clear message.
- This example does not relax interfaces or compute final thermodynamic
  quantities; those stages are demonstrated by Examples 07 and 08.
"""

from __future__ import annotations

import os
from pathlib import Path

from calm import RegistrySettings, StrainPartitionSettings, open_project

EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"

# We only produce the potential-energy-density plot for strain scans.
# The interfacial-energy (gamma) vs strain plot is no longer generated.

SEARCH_NAME = "LiF_Li2O_100_interface_match"
MAX_PROTOTYPES = int(os.environ.get("CALM_EXAMPLE_06_MAX_PROTOTYPES", "2"))
REGISTRY_STEPS = int(os.environ.get("CALM_EXAMPLE_06_REGISTRY_STEPS", "32"))


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    project = open_project(PROJECT_DIR, summarize=True)

    # --8<-- [start:tutorial-refinement-workflow]
    # Refinement uses the named persisted search created from explicit surface
    # UIDs and termination selections in Example 03.

    # Use the high-level refine_interfaces helper to run followups and derive interfaces.
    # Only include potential_energy_density in the example outputs.
    PLOTS = ("potential_energy_density_eV_per_A2",)

    search = project.search(SEARCH_NAME)
    refinement = project.refine_interfaces(
        search,
        top=MAX_PROTOTYPES,
        pareto=True,
        strain_settings=StrainPartitionSettings(
            target_metric="potential_energy_density_eV_per_A2",
            alphas=(0.0, 0.25, 0.5, 0.75, 1.0),
        ),
        registry_settings=RegistrySettings(
            steps=REGISTRY_STEPS,
            translation_step=0.08,
            seed=20260719,
        ),
        label_prefix="example_06",
    )

    print(refinement.summary())
    refinement.write_outputs(
        OUTPUT_DIR,
        filename_prefix="06_",
        plots=PLOTS,
    )
    # --8<-- [end:tutorial-refinement-workflow]


if __name__ == "__main__":
    main()
