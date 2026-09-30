"""Example 08: Persistent reference, raw-energy, and thermodynamic workflows.

The default workflow computes raw single-point total energies and derives
``interface_excess_strained_bulk`` for Example 07's authoritative relaxed
interfaces. CALM calculates and persists the required per-interface references
before thermodynamic derivation.

Set ``CALM_EXAMPLE_08_FORMULA`` to select another supported convention or to an
empty string to run the raw-energy-only path. The first-class calculated
conventions are:

- ``interface_excess_strained_bulk``
- ``work_of_separation_unrelaxed_surfaces``
- ``work_of_adhesion_relaxed_surfaces``

The work-of-adhesion workflow cleaves the exact fixed-cell relaxed interface
and relaxes both isolated surfaces independently. Inspect
``EnergyConvention.reference_capability()`` before choosing the reference mode.
Set ``CALM_EXAMPLE_08_REFERENCE_MODE=manual`` to use explicit scalar values.
"""

from __future__ import annotations

import os
from pathlib import Path

from calm import (
    EnergyConvention,
    EnergySettings,
    ReferenceEnergySettings,
    RelaxSettings,
    open_project,
)

EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"

SEARCH_NAME = "LiF_Li2O_100_interface_match"
BACKEND = os.environ.get("CALM_EXAMPLE_08_BACKEND", "real")
FORMULA = os.environ.get(
    "CALM_EXAMPLE_08_FORMULA",
    "interface_excess_strained_bulk",
).strip()
N_INTERFACES = int(os.environ.get("CALM_EXAMPLE_08_N_INTERFACES", "2"))
REFERENCE_MODE = os.environ.get(
    "CALM_EXAMPLE_08_REFERENCE_MODE",
    "authoritative",
).strip().lower()


def _optional_convention():
    if not FORMULA:
        return None
    return EnergyConvention(
        formula=FORMULA,
        n_interfaces=N_INTERFACES,
    )


def _manual_references(convention: EnergyConvention) -> ReferenceEnergySettings:
    if convention.formula == "interface_excess_strained_bulk":
        return ReferenceEnergySettings(
            bulk_a_eV_per_formula_unit=float(
                os.environ["CALM_EXAMPLE_08_BULK_A_EV_PER_FU"]
            ),
            bulk_b_eV_per_formula_unit=float(
                os.environ["CALM_EXAMPLE_08_BULK_B_EV_PER_FU"]
            ),
            n_formula_units_a=int(os.environ["CALM_EXAMPLE_08_N_FU_A"]),
            n_formula_units_b=int(os.environ["CALM_EXAMPLE_08_N_FU_B"]),
        )
    return ReferenceEnergySettings(
        surface_a_total_energy_eV=float(
            os.environ["CALM_EXAMPLE_08_SURFACE_A_TOTAL_EV"]
        ),
        surface_b_total_energy_eV=float(
            os.environ["CALM_EXAMPLE_08_SURFACE_B_TOTAL_EV"]
        ),
    )


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py through "
            "examples/07_relax_interfaces.py first."
        )
    if REFERENCE_MODE not in {"authoritative", "manual"}:
        raise ValueError(
            "CALM_EXAMPLE_08_REFERENCE_MODE must be 'authoritative' or 'manual'."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = open_project(PROJECT_DIR, summarize=True)
    # --8<-- [start:tutorial-energy-workflow]
    convention = _optional_convention()
    references = None

    if convention is not None:
        capability = convention.reference_capability()
        print(capability.summary())
        if REFERENCE_MODE == "manual":
            references = _manual_references(convention)
        else:
            capability.raise_for_calculated_references()
            surface_relaxation = (
                RelaxSettings(fmax=0.05, steps=500, relax_cell=False)
                if convention.formula == "work_of_adhesion_relaxed_surfaces"
                else None
            )
            reference_workflow = project.evaluate_reference_energies(
                convention=convention,
                search_name=SEARCH_NAME,
                settings=EnergySettings(mode="single_point"),
                surface_relaxation=surface_relaxation,
                backend=BACKEND,
                resume=True,
                partial_resume=True,
                on_error="raise",
            )
            print(reference_workflow.summary())
            reference_workflow.write_table(
                OUTPUT_DIR / "08_reference_energy_results.csv",
            )
            references = reference_workflow

    workflow = project.evaluate_energies(
        settings=EnergySettings(mode="single_point"),
        search_name=SEARCH_NAME,
        backend=BACKEND,
        convention=convention,
        references=references,
        resume=True,
        partial_resume=True,
        on_error="raise",
    )

    print(workflow.summary())
    workflow.write_table(
        OUTPUT_DIR / "08_raw_energy_results.csv",
        kind="raw",
    )
    if workflow.thermodynamic_results is not None:
        workflow.write_table(
            OUTPUT_DIR / "08_thermodynamic_results.csv",
            kind="thermodynamic",
        )
    else:
        print(
            "No derived thermodynamic quantity was requested because "
            "CALM_EXAMPLE_08_FORMULA is empty."
        )
    # --8<-- [end:tutorial-energy-workflow]


if __name__ == "__main__":
    main()
