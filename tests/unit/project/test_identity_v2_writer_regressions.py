from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from calm.project.application.bulks import BulksService
from calm.project.application.campaigns import CampaignService
from calm.project.domain.identity_v2 import (
    campaign_identity_payload,
    is_persisted_uid_v2,
    persisted_entity_uid_v2,
    prototype_identity_payload,
)
from calm.project.domain.models import Prototype
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from calm.public.workflows.campaigns import ProjectCampaignWorkflowService
from calm.public.project import Project
from calm.public.persistence.adapter import WorkspaceAdapter


def _uow(path: Path) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork.from_sqlite_path(path)


def test_current_identity_bulk_upsert_does_not_update_the_canonical_uid(tmp_path: Path) -> None:
    path = tmp_path / "calm.sqlite"
    service = BulksService(uow_factory=lambda: _uow(path))
    first = service.add_bulk(label="first", payload={"material": "A"})
    second = service.add_bulk(label="second", payload={"material": "A"})

    assert second.uid_full == first.uid_full
    assert second.id_short == first.id_short
    assert second.label == "second"
    assert is_persisted_uid_v2(second.uid_full, entity_kind="bulk")


def test_current_identity_prototype_upsert_does_not_update_the_canonical_uid(
    tmp_path: Path,
) -> None:
    uow = _uow(tmp_path / "calm.sqlite")
    run_uid = "run:v2:" + "1" * 64
    slab_uid = "slab:v2:" + "2" * 64
    uid_full = persisted_entity_uid_v2(
        "prototype",
        prototype_identity_payload(
            run_uid_full=run_uid,
            slab_a_uid_full=slab_uid,
            slab_b_uid_full=slab_uid,
            payload={
                "schema": "calm.interface_prototype_build_payload/v2",
                "identity_algorithm": "primitive_coupled_pair_v2",
                "pair_identity": {
                    "key_version": 1,
                    "primitive_pair_key": [1, 0, 0, 1, 1, 0, 0, 1],
                    "pair_symmetry_policy": "full",
                    "correspondence_orientation": "proper",
                    "material_exchange_identified": False,
                },
            },
            match_score=0.1,
            hencky_norm=0.2,
            interface_area=3.0,
            n_atoms=4,
        ),
    )
    first = Prototype(
        uid_full=uid_full,
        id_short="p_12345678",
        run_uid_full=run_uid,
        run_id_short="r_12345678",
        slab_a_uid_full=slab_uid,
        slab_b_uid_full=slab_uid,
        match_score=0.1,
        hencky_norm=0.2,
        interface_area=3.0,
        natoms=4,
        is_pareto=False,
        pareto_rank=None,
        payload={"candidate": 1},
    )
    second = Prototype(
        uid_full=uid_full,
        id_short="p_12345678",
        run_uid_full=run_uid,
        run_id_short="r_12345678",
        slab_a_uid_full=slab_uid,
        slab_b_uid_full=slab_uid,
        match_score=0.1,
        hencky_norm=0.2,
        interface_area=3.0,
        natoms=4,
        is_pareto=True,
        pareto_rank=0,
        payload={"candidate": 1, "pareto": {"is_member": True}},
    )

    with uow as entered:
        entered.prototypes.upsert_many([first])
        stored = entered.prototypes.upsert_many([second])[0]

    assert stored.uid_full == uid_full
    assert stored.id_short == first.id_short
    assert stored.is_pareto is True
    assert stored.pareto_rank == 0


def test_repository_integrity_error_is_not_retried_as_a_lock_error(
    tmp_path: Path,
) -> None:
    uow = _uow(tmp_path / "calm.sqlite")

    with pytest.raises(
        IntegrityError,
        match="requires a canonical dataset UID",
    ):
        with uow as entered:
            entered.datasets.create_dataset(
                uid_full="dataset:legacy-random-uid",
                name="invalid",
            )



def test_current_identity_campaign_service_rejects_a_legacy_campaign_hint() -> None:
    def unexpected_uow():
        raise AssertionError("Invalid campaign identity reached persistence.")

    service = CampaignService(uow_factory=unexpected_uow)
    spec = {"purpose": "campaign identity"}
    legacy_uid = "campaign:" + ("a" * 64)

    with pytest.raises(ValueError, match="does not match the canonical"):
        service.create_or_get(
            name="campaign",
            spec=spec,
            uid_full=legacy_uid,
        )


def test_public_project_reopens_the_current_campaign_identity() -> None:
    spec = {"purpose": "campaign compatibility"}
    uid_full = persisted_entity_uid_v2(
        "campaign",
        campaign_identity_payload(name="campaign", spec=spec),
    )
    existing = SimpleNamespace(
        uid_full=uid_full,
        id_short="y_12345678",
        name="campaign",
        spec=spec,
        metadata={},
        created_at=None,
    )
    repository = SimpleNamespace(get_campaign=lambda name: existing)
    project = SimpleNamespace()
    service = ProjectCampaignWorkflowService(
        project=project,
        workspace=SimpleNamespace(),
        repository=repository,
        search_workflows=SimpleNamespace(),
        interface_builds=SimpleNamespace(),
        interface_refinements=SimpleNamespace(),
        relaxation_workflows=SimpleNamespace(),
        energy_workflows=SimpleNamespace(),
        dataset_workflows=SimpleNamespace(),
    )

    reopened = service.create_campaign(name="campaign", spec=spec)

    assert reopened.uid_full == uid_full
    assert reopened.spec == spec



def test_workspace_adapter_does_not_hide_backend_persistence_errors() -> None:
    class Backend:
        @staticmethod
        def create_campaign(*, name, spec, uid_full):
            raise ValueError(f"identity conflict for {name}")

        @staticmethod
        def create_or_get_campaign_run(
            campaign_uid_full,
            *,
            run_spec,
            backend_id=None,
            status=None,
        ):
            del run_spec, backend_id, status
            raise ValueError(f"run conflict for {campaign_uid_full}")

    adapter = WorkspaceAdapter(Backend())
    with pytest.raises(ValueError, match="identity conflict"):
        adapter.create_campaign(name="campaign", spec={}, uid_full="legacy")
    with pytest.raises(ValueError, match="run conflict"):
        adapter.create_or_get_campaign_run("campaign", run_spec={})
