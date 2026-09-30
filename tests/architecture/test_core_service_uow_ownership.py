from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from calm.project.application.bulks import BulksService
from calm.project.application.calculators import CalculatorsService
from calm.project.application.followups.query import FollowupQueryService
from calm.project.application.followups.service import FollowupsService
from calm.project.application.slabs import SlabsService
from calm.project.runtime.workspace import Workspace


@pytest.mark.parametrize(
    "service",
    [BulksService, CalculatorsService, SlabsService, FollowupQueryService],
)
def test_factory_only_core_services_require_one_uow_factory(service) -> None:
    parameters = inspect.signature(service).parameters
    assert set(parameters) == {"uow_factory"}
    assert parameters["uow_factory"].default is inspect.Parameter.empty


def test_followups_service_requires_uow_factory_and_accepts_artifact_owner() -> None:
    parameters = inspect.signature(FollowupsService).parameters
    assert set(parameters) == {"uow_factory", "artifacts"}
    assert parameters["uow_factory"].default is inspect.Parameter.empty
    assert parameters["artifacts"].default is None


def test_workspace_requires_the_composition_root_uow_factory() -> None:
    parameter = inspect.signature(Workspace).parameters["uow_factory"]
    assert parameter.default is inspect.Parameter.empty


def test_retired_uow_resolver_and_infrastructure_reexport_are_absent() -> None:
    from calm.project.ports import ids

    assert not hasattr(ids, "UowIdResolver")
    assert importlib.util.find_spec("calm.project.infrastructure.unit_of_work") is None


def test_bootstrap_imports_the_concrete_uow_owner_directly() -> None:
    source = Path("calm/project/bootstrap.py").read_text(encoding="utf-8")
    assert "from .infrastructure.db.uow import SqlAlchemyUnitOfWork" in source
    assert "infrastructure.unit_of_work" not in source


def test_sql_uow_does_not_suppress_required_repository_construction() -> None:
    source = Path("calm/project/infrastructure/db/uow.py").read_text(
        encoding="utf-8"
    )
    assert "self.project_configuration = ProjectConfigurationRepository(conn)" in source
    assert "self.campaigns = SqlAlchemyCampaignRepository(conn, ids=ids)" in source
    assert "self.project_configuration = None" not in source
    assert "self.campaigns = None" not in source


def test_core_services_do_not_store_a_concrete_uow_or_external_id_resolver() -> None:
    for path in (
        "calm/project/application/bulks.py",
        "calm/project/application/calculators.py",
        "calm/project/application/slabs.py",
        "calm/project/application/followups/service.py",
        "calm/project/application/followups/query.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "self._uow =" not in source
        assert "UowIdResolver" not in source
        assert "IdResolver" not in source
