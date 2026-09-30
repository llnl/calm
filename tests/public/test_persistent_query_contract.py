from __future__ import annotations

from types import SimpleNamespace

import pytest

from energy_result_fixtures import raw_energy_payload

from calm.project.domain.models import (
    ArtifactRef,
    Campaign,
    CampaignRun,
    Dataset,
    DatasetItem,
    Edge,
    FollowupResult,
    InterfaceSearch,
    Run,
)
from calm.public.records.persistence import (
    ProjectArtifact,
    ProjectCampaign,
    ProjectCampaignRun,
    ProjectDataset,
    ProjectDatasetItem,
    ProjectEdge,
    ProjectEnergyResult,
    ProjectFollowupResult,
    ProjectRun,
    ProjectSearch,
    RecordAuthority,
)
from calm.public.project import Project
from calm.public.persistence.adapter import WorkspaceAdapter


class _PersistentWorkspace:
    def __init__(self) -> None:
        self._runs = [
            Run(
                uid_full="run:search",
                id_short="r_search",
                run_type="prototype_search",
                spec={"search_identity": "search:screen"},
                status="done",
            ),
            Run(
                uid_full="run:energy",
                id_short="r_energy",
                run_type="energy_stage",
                spec={"backend": "deterministic"},
                status="done",
            ),
        ]
        self._searches = [
            InterfaceSearch(
                name="screen",
                search_identity="search:screen",
                run_uid_full="run:search",
                run_id_short="r_search",
                status="done",
                spec={"search_identity": "search:screen"},
            )
        ]
        self._followups = [
            FollowupResult(
                uid_full="followup:energy",
                id_short="f_energy",
                run_uid_full="run:energy",
                run_id_short="r_energy",
                prototype_uid_full="proto:1",
                prototype_id_short="p_1",
                target_kind="interface",
                target_uid_full="interface:1",
                target_id_short="i_1",
                kind="energy_stage",
                best_energy=-2.5,
                payload=raw_energy_payload(-2.5),
            )
        ]
        self._artifacts = [
            ArtifactRef(
                uid_full="artifact:1",
                id_short="a_1",
                run_uid_full="run:energy",
                kind="json",
                uri="data/result.json",
            )
        ]
        self._datasets = [
            Dataset(
                uid_full="dataset:1",
                id_short="d_1",
                name="training",
                description="phase 1 query fixture",
            )
        ]
        self._dataset_items = [
            DatasetItem(
                uid_full="dataset_item:1",
                id_short="t_1",
                dataset_uid_full="dataset:1",
                index=0,
                metadata={"candidate_id": "C0000"},
            )
        ]
        self._campaigns = [
            Campaign(
                uid_full="campaign:1",
                id_short="y_1",
                name="screening",
            )
        ]
        self._campaign_runs = [
            CampaignRun(
                uid_full="campaign_run:1",
                id_short="x_1",
                campaign_uid_full="campaign:1",
                status="done",
            )
        ]
        self._edges = [
            Edge(
                uid_full="edge:run-proto",
                src_uid_full="run:search",
                dst_uid_full="proto:1",
                kind="run_to_prototype",
            ),
            Edge(
                uid_full="edge:proto-interface",
                src_uid_full="proto:1",
                dst_uid_full="interface:1",
                kind="prototype_to_interface",
            ),
            Edge(
                uid_full="edge:interface-followup",
                src_uid_full="interface:1",
                dst_uid_full="followup:energy",
                kind="interface_to_followup",
            ),
        ]

    def secret_internal_method(self) -> str:
        return "not public"

    def list_runs(self, *, run_type=None, status=None, limit=None):
        rows = [
            row
            for row in self._runs
            if (run_type is None or row.run_type == run_type)
            and (status is None or row.status == status)
        ]
        return rows if limit is None else rows[:limit]

    def get_run(self, identifier):
        for row in self._runs:
            if identifier in {row.uid_full, row.id_short}:
                return row
        raise KeyError(identifier)

    def list_interface_searches(self, *, limit=None):
        rows = list(self._searches)
        return rows if limit is None else rows[:limit]

    def get_interface_search(self, identifier):
        for row in self._searches:
            if identifier in {
                row.name,
                row.search_identity,
                row.run_uid_full,
                row.run_id_short,
            }:
                return row
        raise KeyError(identifier)

    def list_prototypes(self, *, run=None, limit=None):
        del run, limit
        return [SimpleNamespace(uid_full="proto:1", id_short="p_1")]

    def resolve_identifier(self, identifier):
        aliases = {
            "r_search": "run:search",
            "r_energy": "run:energy",
            "p_1": "proto:1",
            "i_1": "interface:1",
            "f_energy": "followup:energy",
            "a_1": "artifact:1",
        }
        return aliases.get(identifier, identifier)

    def list_followup_results(
        self,
        *,
        run=None,
        prototype=None,
        kind=None,
        limit=None,
    ):
        rows = [
            row
            for row in self._followups
            if (run is None or run in {row.run_uid_full, row.run_id_short})
            and (
                prototype is None
                or prototype in {row.prototype_uid_full, row.prototype_id_short}
            )
            and (kind is None or row.kind == kind)
        ]
        return rows if limit is None else rows[:limit]

    def get_followup_result(self, identifier):
        for row in self._followups:
            if identifier in {row.uid_full, row.id_short}:
                return row
        raise KeyError(identifier)

    def list_artifacts(self, run):
        run_obj = self.get_run(run)
        return [row for row in self._artifacts if row.run_uid_full == run_obj.uid_full]

    def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
        rows = [
            row
            for row in self._edges
            if (src is None or row.src_uid_full == src)
            and (dst is None or row.dst_uid_full == dst)
            and (kind is None or row.kind == kind)
        ]
        return rows if limit is None else rows[:limit]

    def list_datasets(self, *, limit=None):
        rows = list(self._datasets)
        return rows if limit is None else rows[:limit]

    def get_dataset(self, identifier):
        for row in self._datasets:
            if identifier in {row.uid_full, row.id_short, row.name}:
                return row
        raise KeyError(identifier)

    def list_dataset_items(self, dataset):
        selected = self.get_dataset(dataset)
        return [
            row
            for row in self._dataset_items
            if row.dataset_uid_full == selected.uid_full
        ]

    def list_campaigns(self, *, limit=None):
        rows = list(self._campaigns)
        return rows if limit is None else rows[:limit]

    def get_campaign(self, identifier):
        for row in self._campaigns:
            if identifier in {row.uid_full, row.id_short, row.name}:
                return row
        raise KeyError(identifier)

    def list_campaign_runs(self, *, campaign=None, limit=None):
        rows = [
            row
            for row in self._campaign_runs
            if campaign is None
            or campaign in {row.campaign_uid_full, "y_1", "screening"}
        ]
        return rows if limit is None else rows[:limit]

    def get_campaign_run(self, identifier):
        for row in self._campaign_runs:
            if identifier in {row.uid_full, row.id_short}:
                return row
        raise KeyError(identifier)

    def get_campaign_for_dataset(self, dataset):
        self.get_dataset(dataset)
        return self._campaigns[0]

    def get_campaign_run_for_dataset(self, dataset):
        self.get_dataset(dataset)
        return self._campaign_runs[0]

    def get_prototype(self, identifier):
        if identifier == "proto:1":
            return SimpleNamespace(uid_full="proto:1", id_short="p_1")
        raise KeyError(identifier)

    def get_derived_interface(self, identifier):
        if identifier == "interface:1":
            return SimpleNamespace(
                uid_full="interface:1",
                id_short="i_1",
                prototype_uid_full="proto:1",
                label="built",
                spec={},
            )
        raise KeyError(identifier)


class _QueryOnlyWorkspace:
    class _Query:
        @staticmethod
        def list_followup_results(*, run=None, kind=None, status=None, limit=None):
            del run, kind, status, limit
            return [
                {
                    "uid_full": "followup:one",
                    "prototype_uid_full": "proto:1",
                    "status": "done",
                },
                {
                    "uid_full": "followup:two",
                    "prototype_uid_full": "proto:2",
                    "status": "failed",
                },
            ]

    query = _Query()


def test_project_boundary_does_not_delegate_arbitrary_workspace_methods(tmp_path):
    project = Project(_PersistentWorkspace(), path=tmp_path / "project.calm")

    assert not hasattr(project, "secret_internal_method")
    with pytest.raises(AttributeError):
        project.secret_internal_method()


def test_persistent_queries_return_typed_authoritative_records(tmp_path):
    project = Project(_PersistentWorkspace(), path=tmp_path / "project.calm")

    search = project.searches().get("screen")
    run = project.run("r_energy")
    followup = project.followups(kind="energy_stage").get("f_energy")
    exact_followup = project.followup("f_energy")
    artifact = project.run_artifacts("r_energy").get("a_1")
    edge = project.edges(kind="run_to_prototype")[0]

    assert isinstance(search, ProjectSearch)
    assert search.authority is RecordAuthority.AUTHORITATIVE
    assert search.uid_full == "run:search"
    assert project.search("screen").uid_full == "run:search"

    assert isinstance(run, ProjectRun)
    assert isinstance(followup, ProjectFollowupResult)
    assert exact_followup == followup
    assert isinstance(artifact, ProjectArtifact)
    assert isinstance(edge, ProjectEdge)
    assert all(
        item.is_authoritative
        for item in (run, followup, artifact, edge)
    )


def test_typed_dataset_campaign_and_energy_queries_preserve_authority(tmp_path):
    project_path = tmp_path / "project.calm"
    project_path.mkdir()
    (project_path / "calm-public-records.json").write_text(
        '{"schema_version": 6, "datasets": [{"name": "wrong"}], "energies": []}',
        encoding="utf-8",
    )
    project = Project(_PersistentWorkspace(), path=project_path)

    dataset = project.dataset("training")
    item_record = project.datasets().where(name="training").items()[0]
    campaign = project.campaign("screening")
    campaign_run = project.campaign_run("x_1")
    related_campaign = project.campaign_for_dataset("training")
    related_campaign_run = project.campaign_run_for_dataset("training")
    collection_run = project.campaigns().where(name="screening").runs()[0]
    energy = project.energy_results()[0]

    assert isinstance(dataset, ProjectDataset)
    assert dataset.description == "phase 1 query fixture"
    assert isinstance(item_record, ProjectDatasetItem)
    assert item_record.metadata["candidate_id"] == "C0000"
    assert isinstance(campaign, ProjectCampaign)
    assert isinstance(campaign_run, ProjectCampaignRun)
    assert related_campaign == campaign
    assert related_campaign_run == campaign_run
    assert collection_run == campaign_run
    assert isinstance(energy, ProjectEnergyResult)
    assert energy.energy == -2.5
    assert all(
        record.is_authoritative
        for record in (dataset, item_record, campaign, campaign_run, energy)
    )


def test_lineage_traverses_persisted_edges_with_direction_and_depth(tmp_path):
    project = Project(_PersistentWorkspace(), path=tmp_path / "project.calm")

    complete = project.lineage("proto:1")
    assert complete.root_uid_full == "proto:1"
    assert {node.uid_full for node in complete.nodes} == {
        "run:search",
        "proto:1",
        "interface:1",
        "followup:energy",
    }
    assert {edge.kind for edge in complete.edges} == {
        "run_to_prototype",
        "prototype_to_interface",
        "interface_to_followup",
    }

    upstream = project.lineage("interface:1", direction="upstream", depth=1)
    assert {node.uid_full for node in upstream.nodes} == {
        "proto:1",
        "interface:1",
    }

    filtered = project.lineage(
        "proto:1",
        direction="downstream",
        kinds={"prototype_to_interface"},
    )
    assert [edge.kind for edge in filtered.edges] == ["prototype_to_interface"]

    with pytest.raises(ValueError, match="direction"):
        project.lineage("proto:1", direction="sideways")
    with pytest.raises(TypeError, match="collection"):
        project.lineage("proto:1", kinds="prototype_to_interface")


def test_workspace_adapter_rejects_retired_query_facade_fallback() -> None:
    adapter = WorkspaceAdapter(_QueryOnlyWorkspace())

    with pytest.raises(AttributeError):
        adapter.list_followup_results(
            prototype="proto:2",
            status="failed",
        )


def test_followup_projection_does_not_read_target_identity_from_payload() -> None:
    record = ProjectFollowupResult.from_item(
        FollowupResult(
            uid_full="followup:payload-only-target",
            id_short="f_payload_only_target",
            run_uid_full="run:1",
            run_id_short="r_1",
            prototype_uid_full="proto:1",
            prototype_id_short="p_1",
            kind="registry_search",
            payload={
                "target_uid_full": "iface:historical",
                "target_kind": "interface",
            },
        )
    )

    assert record.target_uid_full is None
    assert record.target_kind is None
