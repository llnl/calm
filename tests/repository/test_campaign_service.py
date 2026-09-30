from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.project.domain.contracts.campaign import CampaignIdentityConflictError
from calm.project.application.campaigns import CampaignService


def test_campaign_service_marks_run_status_and_timestamps(
    schema_uow_factory,
) -> None:
    service = CampaignService(uow_factory=schema_uow_factory)
    campaign = service.create_or_get(
        name="campaign-service",
        spec={"cases": [], "settings": {}},
    )
    run = service.create_or_get_run(
        campaign.uid_full,
        run_spec={"execution_contract": "synchronous_campaign_v1"},
        backend_id="synchronous",
        status="pending",
    )
    running = service.mark_run(run.uid_full, status="running")
    assert running.status == "running"
    assert running.started_at is not None
    assert running.finished_at is None

    completed = service.mark_run(run.uid_full, status="completed")
    assert completed.status == "completed"
    assert completed.started_at is not None
    assert completed.finished_at is not None


def test_campaign_service_rejects_name_reuse_with_different_spec(
    schema_uow_factory,
) -> None:
    service = CampaignService(uow_factory=schema_uow_factory)
    service.create_or_get(name="campaign-service", spec={"a": 1})
    with pytest.raises(CampaignIdentityConflictError):
        service.create_or_get(name="campaign-service", spec={"a": 2})


def test_campaign_service_rejects_unknown_run_status(schema_uow_factory) -> None:
    service = CampaignService(uow_factory=schema_uow_factory)
    campaign = service.create_or_get(name="campaign-service", spec={})
    run = service.create_or_get_run(campaign.uid_full, run_spec={})
    with pytest.raises(ValueError, match="Unsupported campaign-run status"):
        service.mark_run(run.uid_full, status="finished")


def test_campaign_service_propagates_lineage_persistence_failure() -> None:
    campaign = SimpleNamespace(uid_full="campaign:test", name="c", spec={})
    run = SimpleNamespace(
        uid_full="campaign_run:test",
        campaign_uid_full=campaign.uid_full,
        status="pending",
    )

    class _Repo:
        def get_campaign(self, uid):
            return campaign if uid == campaign.uid_full else None

        def create_or_get_campaign_run(self, **kwargs):
            return run

    class _Edges:
        def add(self, **kwargs):
            raise RuntimeError("edge write failed")

    class _Uow:
        campaigns = _Repo()
        edges = _Edges()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    service = CampaignService(uow_factory=_Uow)
    with pytest.raises(RuntimeError, match="edge write failed"):
        service.create_or_get_run(campaign.uid_full, run_spec={})
