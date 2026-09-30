"""Repository contract for consolidated public table-view ownership."""

from __future__ import annotations

from engineering.qualification.check_public_table_views import validate


def test_public_table_view_inventory_is_exact_and_current() -> None:
    result = validate()

    assert result == {
        "errors": [],
        "foundation_methods": [
            "to_dataframe",
            "to_rows",
            "to_table",
            "write_table",
        ],
        "result_foundation_methods": [
            "to_dataframe",
            "to_rows",
            "to_table",
            "write_table",
        ],
        "known_defects": 0,
        "retired_table_presets": [
            "artifacts",
            "bulks",
            "calculators",
            "edges",
            "followups",
            "interfaces",
            "prototypes",
            "runs",
            "slabs",
        ],
        "owners": [
            "ArtifactCollection",
            "CampaignCollection",
            "CampaignRunCollection",
            "CampaignWorkflowResult",
            "CandidateCollection",
            "DatasetCollection",
            "DatasetItemCollection",
            "EdgeCollection",
            "EnergyResultCollection",
            "EnergyWorkflowResult",
            "FollowupCollection",
            "InterfaceCollection",
            "InterfaceSearchResult",
            "MaterialCollection",
            "ProjectDataset",
            "ReferenceEnergyResultCollection",
            "ReferenceEnergyWorkflowResult",
            "RegistrySearchRun",
            "RelaxationResultCollection",
            "RelaxationWorkflowResult",
            "RunCollection",
            "SearchCollection",
            "StrainPartitionScan",
            "SurfaceCollection",
            "ThermodynamicResultCollection",
        ],
        "schema": "calm.public_table_views.v8",
        "temporary_example_schemas": 0,
    }
