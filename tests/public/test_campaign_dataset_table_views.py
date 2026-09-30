from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from calm.public.collections.campaigns import CampaignCollection
from calm.public.collections.datasets import DatasetCollection
from calm.public.collections.persistence import (
    CampaignRunCollection,
    DatasetItemCollection,
)
from calm.public.inputs.campaigns import (
    CampaignCase,
    CampaignCaseResult,
    CampaignWorkflowResult,
)
from calm.public.records.dataset_views import dataset_learning_columns
from calm.public.records.persistence import (
    ProjectCampaign,
    ProjectCampaignRun,
    ProjectDataset,
    ProjectDatasetItem,
    RecordAuthority,
)


class _DatasetProject:
    def __init__(self, items):
        self._items = DatasetItemCollection(items)

    def dataset_items(self, _identifier):
        return self._items


class _DatasetRepo:
    def __init__(self, items):
        self._items = list(items)

    def list_dataset_items(self, _identifier):
        return list(self._items)


def _dataset_item() -> ProjectDatasetItem:
    return ProjectDatasetItem(
        uid_full="dataset_item:one",
        id_short="t_one",
        dataset_uid_full="dataset:one",
        index=0,
        metadata={
            "source_uid_full": "followup:one",
            "source_id_short": "f_one",
            "source_kind": "thermodynamic",
            "terminal_source_kind": "thermodynamic",
            "run_uid_full": "run:one",
            "interface_uid_full": "interface:one",
            "interface_id_short": "i_one",
            "interface_label": "interface-one",
            "prototype_uid_full": "prototype:one",
            "group_id": "prototype:one",
            "split": "train",
            "status": "completed",
            "features": {"area_A2": 12.5},
            "targets": {"energy_J_per_m2": 4.0},
        },
        artifact_refs=("artifact:one",),
        created_at="2026-01-01T00:00:00",
        authority=RecordAuthority.AUTHORITATIVE,
    )


def _dataset() -> ProjectDataset:
    item = _dataset_item()
    project = _DatasetProject([item])
    return ProjectDataset(
        uid_full="dataset:one",
        id_short="d_one",
        name="learning",
        description="demo dataset",
        metadata={
            "schema_version": "calm.interface_learning.v1",
            "content_fingerprint": "dataset_content:one",
        },
        created_at="2026-01-01T00:00:00",
        authority=RecordAuthority.AUTHORITATIVE,
        _project=project,
    )


def test_campaign_and_run_collections_use_explicit_named_views(tmp_path: Path) -> None:
    campaign = ProjectCampaign(
        uid_full="campaign:one",
        id_short="y_one",
        name="demo",
        spec={
            "identity_version": 3,
            "cases": [{"name": "a"}, {"name": "b"}],
            "settings": {"stages": ["search", "build", "dataset"]},
        },
        created_at="2026-01-01T00:00:00",
        authority=RecordAuthority.AUTHORITATIVE,
    )
    collection = CampaignCollection(campaigns=[campaign])

    assert collection.available_views() == ("summary", "provenance", "all")
    assert collection.to_rows() == [
        {
            "campaign_id": "y_one",
            "name": "demo",
            "n_cases": 2,
            "stages": ["search", "build", "dataset"],
            "created_at": "2026-01-01T00:00:00",
        }
    ]
    provenance = collection.to_rows(view="provenance")[0]
    assert provenance["identity_version"] == 3
    assert provenance["authority"] == "authoritative"
    assert "spec" in collection.to_rows(view="all")[0]

    empty = tmp_path / "campaigns.csv"
    CampaignCollection(campaigns=[]).write_table(empty)
    assert empty.read_text(encoding="utf-8").splitlines() == [
        "campaign_id,name,n_cases,stages,created_at"
    ]

    run = ProjectCampaignRun(
        uid_full="campaign_run:one",
        id_short="x_one",
        campaign_uid_full=campaign.uid_full,
        run_spec_hash="hash",
        backend_id="local",
        status="completed",
        started_at="2026-01-01T00:00:00",
        finished_at="2026-01-01T01:00:00",
        authority=RecordAuthority.AUTHORITATIVE,
    )
    runs = CampaignRunCollection([run])
    assert runs.available_views() == ("summary", "provenance", "all")
    assert list(runs.to_rows()[0]) == [
        "run_id",
        "campaign_id",
        "status",
        "backend_id",
        "started_at",
        "finished_at",
    ]
    assert runs.to_rows(view="provenance")[0]["run_spec_hash"] == "hash"


def test_campaign_workflow_result_uses_shared_result_projection(tmp_path: Path) -> None:
    dataset = _dataset()
    result = CampaignWorkflowResult(
        campaign=SimpleNamespace(
            uid_full="campaign:one",
            id_short="y_one",
            name="demo",
        ),
        run=SimpleNamespace(uid_full="campaign_run:one", id_short="x_one"),
        cases=(
            CampaignCaseResult(
                case=CampaignCase(
                    name="case",
                    search_name="search",
                    dimensions={"backend": "demo"},
                ),
                status="completed",
                stages={"energy": {"raw_eV_mean": -3.0}},
                dataset=dataset,
                export_path=tmp_path / "bundle",
            ),
        ),
        status="completed",
    )

    assert result.available_views() == (
        "summary",
        "comparison",
        "provenance",
        "all",
    )
    assert list(result.to_rows()[0]) == [
        "campaign_name",
        "case_name",
        "search_name",
        "status",
        "dataset_name",
        "export_path",
        "failure_type",
        "failure_message",
    ]
    assert result.to_rows(view="provenance")[0]["dataset_uid_full"] == (
        "dataset:one"
    )
    comparison = result.to_rows(view="comparison")[0]
    assert comparison["dimension_backend"] == "demo"
    assert comparison["energy_raw_eV_mean"] == -3.0
    assert result.to_rows(view="all")[0]["case"]["search_name"] == "search"

    output = tmp_path / "campaign.csv"
    result.write_table(output)
    with output.open(newline="", encoding="utf-8") as stream:
        header = next(csv.reader(stream))
    assert header == list(result.to_rows()[0])
    assert list(result.to_dataframe().columns) == header

    comparison_result = result.comparison()
    assert comparison_result.to_rows()[0]["energy_raw_eV_mean"] == -3.0
    assert list(comparison_result.to_dataframe().columns) == list(
        comparison_result.to_rows()[0]
    )

    empty_result = CampaignWorkflowResult(
        campaign=SimpleNamespace(
            uid_full="campaign:empty",
            id_short="y_empty",
            name="empty",
        ),
        run=SimpleNamespace(uid_full="campaign_run:empty", id_short="x_empty"),
        cases=(),
        status="completed",
    )
    empty_comparison = tmp_path / "empty-comparison.csv"
    empty_result.write_table(empty_comparison, view="comparison")
    assert empty_comparison.read_text(encoding="utf-8").splitlines() == [
        "campaign_name,case_name,search_name,status,dataset_name,export_path,"
        "failure_type,failure_message"
    ]

    with pytest.raises(ValueError, match="Unknown table view"):
        result.to_rows(view="not_a_real_view")


def test_dataset_and_item_views_share_ordered_projection_schemas(
    tmp_path: Path,
) -> None:
    item = _dataset_item()
    dataset = _dataset()
    collection = DatasetCollection(
        datasets=[dataset],
        repo=_DatasetRepo([item]),
        project=dataset._project,
    )

    assert collection.available_views() == ("summary", "provenance", "all")
    assert collection.to_rows() == [
        {
            "dataset_id": "d_one",
            "name": "learning",
            "schema_version": "calm.interface_learning.v1",
            "n_items": 1,
            "created_at": "2026-01-01T00:00:00",
        }
    ]
    provenance = collection.to_rows(view="provenance")[0]
    assert provenance["content_fingerprint"] == "dataset_content:one"
    assert provenance["authority"] == "authoritative"

    items = DatasetItemCollection([item])
    assert items.available_views() == (
        "summary",
        "learning",
        "provenance",
        "all",
    )
    assert list(items.to_rows()[0]) == [
        "dataset_index",
        "source_id_short",
        "source_kind",
        "interface_id_short",
        "interface_label",
        "group_id",
        "split",
        "status",
    ]
    learning = items.to_rows(view="learning")[0]
    assert learning["feature_area_A2"] == 12.5
    assert learning["target_energy_J_per_m2"] == 4.0
    assert items.to_rows(view="provenance")[0]["artifact_refs"] == [
        "artifact:one"
    ]

    assert dataset.available_views() == items.available_views()
    assert dataset.to_rows() == items.to_rows(view="learning")
    assert dataset.to_rows(view="summary") == items.to_rows(view="summary")

    output = tmp_path / "learning.csv"
    dataset.write_table(output)
    with output.open(newline="", encoding="utf-8") as stream:
        header = next(csv.reader(stream))
    assert header == list(dataset.to_rows()[0])
    assert list(dataset.to_dataframe().columns) == header

    manifest = tmp_path / "manifest.csv"
    collection.write_manifest(manifest, view="provenance")
    with manifest.open(newline="", encoding="utf-8") as stream:
        manifest_header = next(csv.reader(stream))
    assert manifest_header == list(items.to_rows(view="provenance")[0])

    empty = tmp_path / "empty-items.csv"
    DatasetItemCollection([]).write_table(empty)
    assert empty.read_text(encoding="utf-8").splitlines() == [
        "dataset_index,source_id_short,source_kind,interface_id_short,"
        "interface_label,group_id,split,status"
    ]

    learning_columns = dataset_learning_columns(
        {
            "features": [{"name": "area_A2"}],
            "targets": [{"name": "energy_J_per_m2"}],
        }
    )
    empty_learning = tmp_path / "empty-learning.csv"
    DatasetItemCollection(
        [],
        learning_columns=learning_columns,
    ).write_table(empty_learning, view="learning")
    assert empty_learning.read_text(encoding="utf-8").splitlines() == [
        "dataset_index,source_id,source_kind,interface_id,interface_label,"
        "search_name,group_id,split,feature_area_A2,target_energy_J_per_m2"
    ]
