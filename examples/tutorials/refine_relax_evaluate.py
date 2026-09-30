"""Refine, relax, and evaluate a Cu/Ni interface with ASE EMT.

This tutorial demonstrates CALM workflow mechanics and reference bookkeeping.
EMT is not a validated model for an arbitrary target interface.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from calm import (
    BuildSettings,
    EnergyConvention,
    EnergySettings,
    Material,
    Potential,
    RegistrySettings,
    RelaxSettings,
    SearchSettings,
    StrainPartitionSettings,
    open_project,
    tutorial_structure,
)

from _support import (
    default_work_dir,
    expectation,
    prepare_directory,
    write_run_summary,
)

SEARCH_NAME = "cu-ni-100-emt"


def run(work_dir: Path, *, reset: bool = False) -> dict[str, object]:
    root = prepare_directory(work_dir, reset=reset)
    project_dir = root / "refine-relax-evaluate.calm"
    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --8<-- [start:refine-configure-materials]
    project = open_project(project_dir)
    potential = Potential(family="ase", model="EMT")
    project.configure(mlip="ase", calculator=potential.to_spec())

    project.add_material(Material.from_ase(tutorial_structure("cu"), name="Cu"))
    project.add_material(Material.from_ase(tutorial_structure("ni"), name="Ni"))
    project.optimize_material(
        "Cu",
        potential=potential,
        fmax=0.03,
        steps=200,
        relax_cell=True,
        name="Cu-EMT",
    )
    project.optimize_material(
        "Ni",
        potential=potential,
        fmax=0.03,
        steps=200,
        relax_cell=True,
        name="Ni-EMT",
    )
    # --8<-- [end:refine-configure-materials]

    project.generate_surfaces(
        ["Cu-EMT", "Ni-EMT"],
        millers=[(1, 0, 0)],
        layers=4,
        vacuum=12.0,
    )
    cu_surface = project.surface(material="Cu-EMT", miller=(1, 0, 0))
    ni_surface = project.surface(material="Ni-EMT", miller=(1, 0, 0))

    search = project.search_interfaces(
        cu_surface,
        ni_surface,
        settings=SearchSettings(
            max_principal_strain=0.08,
            max_supercell_index=6,
            max_atoms=500,
            max_candidates=200,
            mismatch_weight=0.5,
        ),
        name=SEARCH_NAME,
    )
    if search.empty:
        raise RuntimeError(search.explain())
    project.build_interfaces(
        search,
        top=1,
        settings=BuildSettings(
            strain_partition="both",
            alpha=0.5,
            gap=1.8,
            vacuum=12.0,
            translation=(0.0, 0.0),
        ),
        name_prefix="cu-ni-interface",
    )

    # --8<-- [start:refine-strain-registry]
    refinement = project.refine_interfaces(
        search,
        top=1,
        pareto=True,
        strain_settings=StrainPartitionSettings(
            target_metric="potential_energy_density_eV_per_A2",
            alphas=(0.0, 0.5, 1.0),
        ),
        registry_settings=RegistrySettings(
            steps=16,
            translation_step=0.08,
            seed=20260801,
        ),
        label_prefix="cu-ni-tutorial",
        on_error="raise",
    )
    refinement.write_outputs(
        output_dir,
        filename_prefix="refinement-",
        plots=(),
    )
    # --8<-- [end:refine-strain-registry]

    # --8<-- [start:refine-relaxation]
    relaxation = project.relax_interfaces(
        search_name=SEARCH_NAME,
        settings=RelaxSettings(fmax=0.08, steps=150, relax_cell=False),
        backend="real",
        stage="registry_refined",
        on_error="raise",
    )
    relaxation.write_table(output_dir / "relaxation-results.csv")
    # --8<-- [end:refine-relaxation]

    # --8<-- [start:refine-energies]
    convention = EnergyConvention(
        formula="work_of_adhesion_relaxed_surfaces",
        n_interfaces=2,
    )
    references = project.evaluate_reference_energies(
        convention=convention,
        search_name=SEARCH_NAME,
        settings=EnergySettings(mode="single_point"),
        surface_relaxation=RelaxSettings(
            fmax=0.08,
            steps=150,
            relax_cell=False,
        ),
        backend="real",
        on_error="raise",
    )
    references.write_table(output_dir / "reference-energies.csv")

    energies = project.evaluate_energies(
        search_name=SEARCH_NAME,
        settings=EnergySettings(mode="single_point"),
        backend="real",
        convention=convention,
        references=references,
        on_error="raise",
    )
    energies.write_table(output_dir / "raw-energies.csv", kind="raw")
    energies.write_table(
        output_dir / "work-of-adhesion.csv",
        kind="thermodynamic",
    )
    # --8<-- [end:refine-energies]

    summary: dict[str, object] = {
        "schema_version": "calm.tutorial_run.v1",
        "tutorial": "refine-relax-evaluate",
        "calculator_required": True,
        "calculator": "ase:EMT",
        "structures": ["cu", "ni"],
        "project": project_dir.name,
        "search": SEARCH_NAME,
        "reference_convention": convention.formula,
        "refinement_ok": refinement.ok,
        "relaxation_results": len(relaxation.results),
        "raw_energy_results": len(energies.energy_results),
        "thermodynamic_results": (
            len(energies.thermodynamic_results)
            if energies.thermodynamic_results is not None
            else 0
        ),
        "artifacts": sorted(
            {path.name for path in output_dir.iterdir()} | {"run-summary.json"}
        ),
    }
    write_run_summary(output_dir, summary)

    expected = expectation("refine-relax-evaluate")
    print(f"[tutorial] outcome: {expected['outcome']}")
    print("[tutorial] calculator: ase:EMT (workflow demonstration only)")
    print(f"[tutorial] convention: {convention.formula}")
    print(f"[tutorial] thermodynamic results: {summary['thermodynamic_results']}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=default_work_dir("refine-relax-evaluate"),
    )
    parser.add_argument("--reset", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run(args.work_dir, reset=args.reset)


if __name__ == "__main__":
    main()
