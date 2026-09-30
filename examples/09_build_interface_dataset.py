"""Example 09: Build, validate, split, and export a learning dataset.

This example joins the authoritative relaxed structures, relaxation results,
raw energies, and thermodynamic quantities produced by Examples 07 and 08.
Feature and target declarations are explicit, and split assignment is
performed deterministically by prototype group so related structures cannot
leak across train, validation, and test partitions.
"""

from __future__ import annotations

from pathlib import Path

from calm import (
    DatasetFeature,
    DatasetSettings,
    DatasetSplitSettings,
    DatasetTarget,
    open_project,
)

EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"

SEARCH_NAME = "LiF_Li2O_100_interface_match"
DATASET_NAME = "LiF_Li2O_interface_learning_dataset"
DATASET_EXPORT_DIR = OUTPUT_DIR / DATASET_NAME


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py through "
            "examples/08_evaluate_interface_energetics.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = open_project(PROJECT_DIR, summarize=True)
    # --8<-- [start:tutorial-dataset-workflow]
    search = project.search(SEARCH_NAME)
    thermodynamic_results = search.thermodynamic_results(
        status="completed",
        latest_run=True,
    )
    if not thermodynamic_results:
        raise RuntimeError(
            "No completed thermodynamic results are available. Run Example 08 "
            "with a supported energy convention first."
        )

    dataset = project.create_dataset(
        DATASET_NAME,
        thermodynamic_results,
        settings=DatasetSettings(
            schema_version="calm.interface_learning.v1",
            duplicate_policy="skip",
            failure_policy="error",
            require_complete_provenance=True,
            features=(
                DatasetFeature(
                    name="interface_area_A2",
                    source="thermodynamic.normalization_area_A2",
                    units="angstrom^2",
                    description="Normalization area of the relaxed interface.",
                ),
                DatasetFeature(
                    name="relaxation_steps",
                    source="relaxation.n_steps",
                    dtype="int",
                    description="Number of structural-relaxation steps.",
                ),
                DatasetFeature(
                    name="maximum_force_eV_per_A",
                    source="relaxation.max_force_eV_per_A",
                    units="eV/angstrom",
                    description="Final maximum atomic force.",
                ),
            ),
            targets=(
                DatasetTarget(
                    name="interface_energy_J_per_m2",
                    source="thermodynamic.value_J_per_m2",
                    units="J/m^2",
                    description="Convention-bearing interfacial energy target.",
                ),
            ),
            group_by=("lineage.prototype",),
            split=DatasetSplitSettings(
                train_fraction=0.8,
                validation_fraction=0.1,
                test_fraction=0.1,
                seed=2026,
            ),
        ),
        description=(
            "Relaxed CALM interface structures joined to relaxation, raw-energy, "
            "and thermodynamic provenance for leakage-safe model development."
        ),
        tags=["example", "learning", "interface", "thermodynamic"],
    )

    validation = dataset.validate()
    validation.raise_for_errors()
    readiness = dataset.validate_ml()
    readiness.raise_for_errors()

    exported = dataset.export(
        DATASET_EXPORT_DIR,
        manifest_format="json",
        include_structures=True,
        structure_format="extxyz",
        overwrite=True,
    )
    dataset.write_table(
        OUTPUT_DIR / "09_learning_dataset.csv",
        view="learning",
    )

    print(validation.summary())
    print(readiness.summary())
    print(exported.summary())
    # --8<-- [end:tutorial-dataset-workflow]


if __name__ == "__main__":
    main()
