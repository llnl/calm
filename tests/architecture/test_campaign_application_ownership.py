from __future__ import annotations

import inspect

from calm.project.application.campaigns import CampaignService
from calm.project.infrastructure.db.repos import SqlAlchemyCampaignRepository
from calm.project.runtime.workspace import Workspace


def test_workspace_campaign_writes_delegate_to_application_service() -> None:
    create_source = inspect.getsource(Workspace.create_campaign)
    run_source = inspect.getsource(Workspace.create_or_get_campaign_run)
    status_source = inspect.getsource(Workspace.mark_campaign_run)

    assert "self._campaigns.create_or_get(" in create_source
    assert "self._campaigns.create_or_get_run(" in run_source
    assert "self._campaigns.mark_run(" in status_source
    combined = create_source + run_source + status_source
    assert "uow.campaigns" not in combined
    assert "edges.add" not in combined
    assert "except Exception" not in combined


def test_campaign_lineage_is_application_owned_and_mandatory() -> None:
    service_source = inspect.getsource(CampaignService.create_or_get_run)
    repository_source = inspect.getsource(
        SqlAlchemyCampaignRepository.create_or_get_campaign_run
    )

    assert "uow.edges.add(" in service_source
    assert "run_of_campaign" in service_source
    assert "except Exception" not in service_source
    assert "edges" not in repository_source
    assert "run_of_campaign" not in repository_source


def test_campaign_repository_has_one_typed_row_shape() -> None:
    source = inspect.getsource(SqlAlchemyCampaignRepository)
    assert "_campaign_from_row" in source
    assert "_campaign_run_from_row" in source
    assert 'return {"uid_full"' not in source
    assert "return CampaignRun(" in source
