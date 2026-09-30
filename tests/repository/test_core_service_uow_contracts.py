from __future__ import annotations

from pathlib import Path

import pytest

from calm.calculators.spec import CalculatorSpec
from calm.project.application.bulks import BulksService
from calm.project.application.calculators import CalculatorsService
from calm.project.application.followups.service import FollowupsService
from calm.project.application.slabs import SlabsService
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.runtime.workspace import Workspace


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: BulksService(uow_factory=None),
        lambda: CalculatorsService(uow_factory=None),
        lambda: SlabsService(uow_factory=None),
        lambda: FollowupsService(uow_factory=None),
    ],
)
def test_core_services_reject_missing_factories(constructor) -> None:
    with pytest.raises(TypeError, match="callable UnitOfWork factory"):
        constructor()


def test_calculator_service_preserves_the_complete_canonical_spec(
    sqlite_uow_factory,
) -> None:
    spec = CalculatorSpec(
        family="test",
        model="exact",
        version="3",
        source="unit-test",
        device="cpu",
        dtype="float64",
        options={"cutoff": 5.0},
    )
    stored = CalculatorsService(uow_factory=sqlite_uow_factory).register(spec)

    assert stored.spec == spec.to_dict()

    with sqlite_uow_factory() as uow:
        reopened = uow.calculators.get_by_uid_full(stored.uid_full)

    assert reopened is not None
    assert reopened.spec == spec.to_dict()


def test_optimized_bulk_and_calculator_share_one_transaction(
    sqlite_uow_factory,
) -> None:
    service = BulksService(uow_factory=sqlite_uow_factory)
    bulk = service.add_bulk(
        label="optimized",
        payload={"material": "LiF"},
        optimized_with="test:model",
    )

    with sqlite_uow_factory() as uow:
        calculators = uow.calculators.list(limit=None)
        stored = uow.bulks.get_by_uid_full(bulk.uid_full)

    assert stored is not None
    assert len(calculators) == 1
    assert stored.optimized_with_calculator_uid_full == calculators[0].uid_full
    assert stored.calculator == "test:model"


def test_bulk_failure_rolls_back_calculator_registration(
    sqlite_uow_factory,
) -> None:
    service = BulksService(uow_factory=sqlite_uow_factory)

    with pytest.raises(Exception):
        service.add_bulk(
            structure=object(),
            optimized_with="test:rollback",
        )

    with sqlite_uow_factory() as uow:
        assert uow.calculators.list(limit=None) == []
        assert uow.bulks.list(limit=None) == []


def test_current_sql_uow_exposes_all_required_repositories(
    sqlite_uow_factory,
) -> None:
    with sqlite_uow_factory() as uow:
        for name in (
            "bulks",
            "calculators",
            "slabs",
            "runs",
            "artifacts",
            "prototypes",
            "followups",
            "edges",
            "derived_interfaces",
            "campaigns",
            "datasets",
            "project_configuration",
            "ids",
        ):
            assert getattr(uow, name) is not None


def test_workspace_requires_an_explicit_uow_factory(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="callable UnitOfWork factory"):
        Workspace(
            out_dir=tmp_path / "out",
            artifact_store=FSArtifactStore(tmp_path / "out"),
            uow_factory=None,
        )


def test_workspace_requires_an_artifact_store(
    tmp_path: Path,
    sqlite_uow_factory,
) -> None:
    with pytest.raises(TypeError, match="requires an artifact store"):
        Workspace(
            out_dir=tmp_path / "out",
            artifact_store=None,
            uow_factory=sqlite_uow_factory,
        )


def test_workspace_does_not_retain_a_unit_of_work(
    tmp_path: Path,
    sqlite_uow_factory,
) -> None:
    workspace = Workspace(
        out_dir=tmp_path / "out",
        artifact_store=FSArtifactStore(tmp_path / "out"),
        uow_factory=sqlite_uow_factory,
    )
    assert not hasattr(workspace, "_uow")
    with workspace._fresh_uow() as first:
        first_connection = first.connection
    with workspace._fresh_uow() as second:
        second_connection = second.connection
    assert first_connection is not second_connection
