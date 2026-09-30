from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.project.domain.contracts.campaign import canonical_campaign_stages
from calm.project.domain.models import Campaign
from calm.public.inputs.campaigns import CampaignCase, CampaignSettings
from calm.public.records.persistence import ProjectCampaign
from calm.public.project import Project


def test_campaign_stage_order_is_canonical() -> None:
    assert canonical_campaign_stages(("search", "build", "energy")) == (
        "search",
        "build",
        "energy",
    )
    with pytest.raises(ValueError, match="canonical order"):
        canonical_campaign_stages(("energy", "search"))
    with pytest.raises(ValueError, match="duplicates"):
        canonical_campaign_stages(("search", "search"))


def test_project_campaign_normalization_is_idempotent() -> None:
    raw = Campaign(
        uid_full="campaign:demo",
        id_short="y_demo",
        project_id="project:demo",
        name="demo",
        spec=None,
    )

    first = ProjectCampaign.from_item(raw)
    second = ProjectCampaign.from_item(first)

    assert second == first
    assert first.spec == {}
    assert first.metadata == {"project_id": "project:demo"}



def test_campaign_settings_roundtrip() -> None:
    settings = CampaignSettings(stages=("search",), on_error="record")
    restored = CampaignSettings.from_dict(settings.to_dict())
    assert restored.canonical_stages == ("search",)
    assert restored.on_error == "record"


class _Workspace:
    def __init__(self) -> None:
        self.campaigns = []
        self.runs = []
        self.edges = []
        self.last_run_spec = None

    def create_campaign(self, *, name=None, spec=None, uid_full=None):
        row = {
            "uid_full": uid_full,
            "id_short": "y_campaign",
            "name": name,
            "spec": dict(spec or {}),
        }
        self.campaigns.append(row)
        return row

    def list_campaigns(self, *, limit=None):
        return list(self.campaigns)

    def get_campaign(self, identifier):
        for row in self.campaigns:
            if identifier in {row["uid_full"], row["id_short"], row["name"]}:
                return row
        raise KeyError(identifier)

    def create_or_get_campaign_run(self, campaign_uid_full, *, run_spec, backend_id=None, status=None):
        self.last_run_spec = dict(run_spec)
        if self.runs:
            return dict(self.runs[0])
        row = {
            "uid_full": "campaign_run:one",
            "id_short": "x_one",
            "campaign_uid_full": campaign_uid_full,
            "run_spec_hash": "hash",
            "backend_id": backend_id,
            "status": status,
        }
        self.runs.append(row)
        return dict(row)

    def list_campaign_runs(self, *, campaign=None, limit=None):
        return list(self.runs)

    def get_campaign_run(self, identifier):
        for row in self.runs:
            if identifier in {row["uid_full"], row["id_short"]}:
                return dict(row)
        raise KeyError(identifier)

    def mark_campaign_run(self, campaign_run_uid_full, *, status):
        self.runs[0]["status"] = status
        return dict(self.runs[0])

    def add_provenance_edge(self, **kwargs):
        self.edges.append(dict(kwargs))
        return kwargs

    def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
        rows = [
            edge
            for edge in self.edges
            if (src is None or edge.get("src_uid_full") == src)
            and (dst is None or edge.get("dst_uid_full") == dst)
            and (kind is None or edge.get("kind") == kind)
        ]
        return rows if limit is None else rows[:limit]


class _Search:
    def __init__(self) -> None:
        self.calls = 0

    def status(self):
        self.calls += 1
        return {"status": "completed", "run_uid": "run:search"}


def test_completed_campaign_run_is_reused_without_reexecuting(tmp_path, monkeypatch) -> None:
    workspace = _Workspace()
    project = Project(workspace, path=tmp_path / "project.calm")
    search = _Search()
    monkeypatch.setattr(project._search_workflows, "search", lambda _name: search)

    campaign = project.create_campaign(
        name="demo",
        cases=[CampaignCase(name="case", search_name="existing")],
        settings=CampaignSettings(stages=("search",), on_error="record"),
    )
    first = campaign.run()
    assert first.status == "completed"
    assert search.calls == 1

    second = campaign.run()
    assert second.reused is True
    assert second.status == "completed"
    assert search.calls == 1
    assert workspace.runs[0]["status"] == "completed"
    assert workspace.last_run_spec["execution_contract"] == "synchronous_campaign_v2"
    assert any(edge["kind"] == "run_of_campaign_execution" for edge in workspace.edges)


def test_campaign_case_requires_both_surface_identifiers() -> None:
    with pytest.raises(ValueError, match="both be set"):
        CampaignCase(
            name="case",
            search_name="search",
            surface_a="s_a",
        ).validate()


def test_campaign_allows_multiple_cases_to_share_one_persisted_search(tmp_path) -> None:
    workspace = _Workspace()
    project = Project(workspace, path=tmp_path / "project.calm")
    campaign = project.create_campaign(
        name="shared-search",
        cases=[
            CampaignCase(name="a", search_name="existing", energy_backend="a"),
            CampaignCase(name="b", search_name="existing", energy_backend="b"),
        ],
        settings=CampaignSettings(stages=("energy",)),
    )
    assert len(campaign.spec["cases"]) == 2
    assert campaign.spec["identity_version"] == 3
    assert {row["search_name"] for row in campaign.spec["cases"]} == {"existing"}


def test_campaign_rejects_conflicting_definitions_for_shared_search(tmp_path) -> None:
    workspace = _Workspace()
    project = Project(workspace, path=tmp_path / "project.calm")

    with pytest.raises(ValueError, match="exact surfaces and search settings"):
        project.create_campaign(
            name="conflicting-search",
            cases=[
                CampaignCase(
                    name="a",
                    search_name="shared",
                    surface_a="surface:a",
                    surface_b="surface:b",
                ),
                CampaignCase(
                    name="b",
                    search_name="shared",
                    surface_a="surface:a",
                    surface_b="surface:c",
                ),
            ],
            settings=CampaignSettings(stages=("search",)),
        )


def test_campaign_name_rejects_surrounding_whitespace(tmp_path) -> None:
    project = Project(_Workspace(), path=tmp_path / "project.calm")
    with pytest.raises(ValueError, match="surrounding whitespace"):
        project.create_campaign(
            name=" demo ",
            cases=[CampaignCase(name="case", search_name="existing")],
            settings=CampaignSettings(stages=("search",)),
        )


def test_campaign_record_cannot_cross_project_boundaries(tmp_path) -> None:
    first = Project(_Workspace(), path=tmp_path / "first.calm")
    second = Project(_Workspace(), path=tmp_path / "second.calm")
    campaign = first.create_campaign(
        name="demo",
        cases=[CampaignCase(name="case", search_name="existing")],
        settings=CampaignSettings(stages=("search",)),
    )

    with pytest.raises(ValueError, match="belongs to another Project"):
        second.run_campaign(campaign)
