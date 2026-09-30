"""Example 10: run and compare a first-class synchronous CALM campaign.

This example reuses the authoritative search and relaxed interfaces produced by
Examples 03-08. It demonstrates typed case-grid generation, per-case dataset
policy overrides, reproducible resume, dataset export, and reopen-safe
comparison, then captures a project reproducibility manifest without introducing
a queue or background worker.
"""

from __future__ import annotations

import os
from pathlib import Path

from calm import CampaignCase, CampaignSettings, DatasetSettings, open_project


EXAMPLES_DIR = Path(__file__).resolve().parent
PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"
OUTPUT_DIR = EXAMPLES_DIR / "outputs"
SEARCH_NAME = "LiF_Li2O_100_interface_match"
ENERGY_BACKEND = os.environ.get("CALM_EXAMPLE_10_ENERGY_BACKEND", "real")


def main() -> None:
    if not PROJECT_DIR.is_dir():
        raise FileNotFoundError(
            f"Shared example project not found at {PROJECT_DIR}. "
            "Run examples/01_optimize_materials.py through "
            "examples/09_build_interface_dataset.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    project = open_project(PROJECT_DIR)

    # --8<-- [start:tutorial-campaign-workflow]
    base_case = CampaignCase(
        name="LiF_Li2O_100",
        search_name=SEARCH_NAME,
    )
    cases = CampaignCase.grid(
        base_case,
        axes={
            "dataset_policy": (
                CampaignCase.variant(
                    "strict",
                    dataset_settings=DatasetSettings(
                        schema_version="calm.raw_energy.v1",
                        duplicate_policy="error",
                        failure_policy="error",
                        require_complete_provenance=True,
                    ),
                ),
                CampaignCase.variant(
                    "resume_safe",
                    dataset_settings=DatasetSettings(
                        schema_version="calm.raw_energy.v1",
                        duplicate_policy="skip",
                        failure_policy="error",
                        require_complete_provenance=True,
                    ),
                ),
            )
        },
    )

    campaign = project.create_campaign(
        name="LiF_Li2O_energy_campaign",
        cases=cases,
        settings=CampaignSettings(
            stages=("energy", "dataset"),
            energy_backend=ENERGY_BACKEND,
            dataset_name_template="{campaign}_{case}",
            on_error="raise",
        ),
    )

    result = campaign.run(
        resume=True,
        export_root=OUTPUT_DIR / "10_campaign_exports",
    )

    results_output = OUTPUT_DIR / "10_campaign_results.csv"
    result.write_table(results_output)

    comparison = result.comparison().rank_by("energy_raw_eV_mean")
    comparison_output = OUTPUT_DIR / "10_campaign_comparison.csv"
    comparison.write_table(comparison_output)

    manifest = project.write_reproducibility_manifest(overwrite=True)
    verification = project.verify_reproducibility_manifest()
    verification.raise_for_errors()

    print(result.summary())
    print(comparison.summary())
    print(manifest.summary())
    print(verification.summary())
    print(f"Wrote: {results_output}")
    print(f"Wrote: {comparison_output}")
    print(f"Wrote: {PROJECT_DIR / 'calm-reproducibility-manifest.json'}")
    # --8<-- [end:tutorial-campaign-workflow]


if __name__ == "__main__":
    main()
