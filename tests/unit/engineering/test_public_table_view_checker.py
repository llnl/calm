"""Unit tests for the public table-view architecture checker."""

from __future__ import annotations

import json
from pathlib import Path

from engineering.qualification.check_public_table_views import REPO_ROOT, validate


CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-public-table-views.json"
)


def _write_contract(tmp_path: Path, transform) -> Path:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    transform(payload)
    path = tmp_path / "current-public-table-views.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_checker_rejects_stale_to_rows_default(tmp_path: Path) -> None:
    path = _write_contract(
        tmp_path,
        lambda payload: payload["current_view_owners"]["CandidateCollection"].update(
            {"default_view": "all"}
        ),
    )

    result = validate(contract_path=path)

    assert any(
        "CandidateCollection.to_rows view default" in error
        for error in result["errors"]
    )


def test_checker_rejects_restored_candidate_example_schema(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["temporary_example_schema_constants"][
            "examples/03_search_interfaces.py"
        ] = {"CANDIDATE_SUMMARY_COLUMNS": ["candidate_id"]}

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "examples/03_search_interfaces.py must not remain" in error
        for error in result["errors"]
    )


def test_checker_rejects_drifted_projection_foundation(tmp_path: Path) -> None:
    def transform(payload):
        payload["projection_foundation"]["dynamic_schema_policy"] = "first_row"

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "projection_foundation does not match" in error
        for error in result["errors"]
    )


def test_checker_rejects_drifted_result_projection_mixin(tmp_path: Path) -> None:
    def transform(payload):
        payload["projection_foundation"]["result_projection_mixin"] = (
            "calm.public.collections.base._BaseCollection"
        )

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "projection_foundation does not match" in error
        for error in result["errors"]
    )


def test_checker_rejects_abstract_candidate_target_view_name(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["CandidateCollection"][
            "target_views"
        ] = ["all", "decision", "provenance", "strain"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "prohibited abstract names: 'decision'" in error
        for error in result["errors"]
    )


def test_checker_requires_summary_for_reader_facing_default(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["DatasetCollection"][
            "target_views"
        ] = ["all", "overview", "provenance"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "DatasetCollection target_views must retain 'summary'" in error
        for error in result["errors"]
    )


def test_checker_requires_migrated_material_views_to_match_targets(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["MaterialCollection"][
            "target_views"
        ] = ["all", "characterization", "summary"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "MaterialCollection canonical views do not match target_views" in error
        for error in result["errors"]
    )


def test_checker_rejects_migrated_example_schema_ownership(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["temporary_example_schema_constants"][
            "examples/01_optimize_materials.py"
        ] = {
            "MATERIAL_CHARACTERIZATION_COLUMNS": ["label"],
        }

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "examples/01_optimize_materials.py must not remain" in error
        for error in result["errors"]
    )


def test_checker_requires_search_result_shared_candidate_views(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["InterfaceSearchResult"][
            "recognized_views"
        ] = ["all", "full", "strain", "summary"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "InterfaceSearchResult recognized_views do not match _view_specs" in error
        for error in result["errors"]
    )


def test_checker_requires_interface_collection_views_to_match_targets(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["InterfaceCollection"][
            "target_views"
        ] = ["all", "provenance", "summary"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "InterfaceCollection target_views must be" in error
        for error in result["errors"]
    )


def test_checker_requires_result_views_to_match_public_vocabulary(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["EnergyResultCollection"][
            "target_views"
        ] = ["all", "diagnostics", "summary"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "EnergyResultCollection target_views must be" in error
        for error in result["errors"]
    )


def test_checker_requires_campaign_result_comparison_view(tmp_path: Path) -> None:
    def transform(payload):
        payload["current_view_owners"]["CampaignWorkflowResult"][
            "target_views"
        ] = ["all", "provenance", "summary"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "CampaignWorkflowResult target_views must be" in error
        for error in result["errors"]
    )


def test_checker_requires_dataset_learning_view(tmp_path: Path) -> None:
    def transform(payload):
        payload["current_view_owners"]["DatasetItemCollection"][
            "target_views"
        ] = ["all", "provenance", "summary"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "DatasetItemCollection target_views must be" in error
        for error in result["errors"]
    )


def test_checker_requires_zero_remaining_defects(tmp_path: Path) -> None:
    def transform(payload):
        payload["known_defects"] = ["restored_defect"]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "known_defects must be empty" in error for error in result["errors"]
    )


def test_checker_preserves_retired_preset_inventory(tmp_path: Path) -> None:
    def transform(payload):
        payload["retired_table_presets"].remove("prototypes")

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "retired_table_presets must preserve" in error
        for error in result["errors"]
    )


def test_checker_requires_general_persistence_view_ownership(
    tmp_path: Path,
) -> None:
    def transform(payload):
        payload["current_view_owners"]["SearchCollection"]["target_views"] = [
            "all",
            "summary",
        ]

    path = _write_contract(tmp_path, transform)
    result = validate(contract_path=path)

    assert any(
        "SearchCollection canonical views do not match target_views" in error
        for error in result["errors"]
    )
