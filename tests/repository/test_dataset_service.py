from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from calm.project.domain.contracts.dataset import (
    DatasetIdentityConflictError,
    dataset_group_uid,
    dataset_split_decision,
    dataset_split_name,
)
from calm.project.application.datasets import DatasetService
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from calm.public.inputs.settings import DatasetSettings


def _factory(path: Path):
    engines = []

    def factory():
        uow = SqlAlchemyUnitOfWork.from_sqlite_path(str(path))
        engines.append(uow.engine)
        return uow

    factory.engines = engines
    return factory


def _dispose(factory) -> None:
    for engine in factory.engines:
        engine.dispose()


def _item(source: str) -> dict:
    return {
        "schema_version": "calm.interface.v1",
        "source_kind": "interface",
        "source_uid_full": source,
        "interface_uid_full": source,
        "prototype_uid_full": "proto:source",
        "stage": "relaxed",
        "status": "completed",
        "artifact_refs": [],
    }


def test_dataset_service_identity_duplicate_and_provenance(tmp_path: Path) -> None:
    factory = _factory(tmp_path / "dataset.sqlite")
    service = DatasetService(uow_factory=factory)
    settings = DatasetSettings(schema_version="calm.interface.v1").to_dict()

    dataset = service.create_or_get(name="training", settings=settings)
    same = service.create_or_get(name="training", settings=settings)
    assert same.uid_full == dataset.uid_full

    created = service.add_items(
        dataset.uid_full,
        [_item("iface:1")],
        duplicate_policy="error",
    )
    assert len(created) == 1
    with pytest.raises(ValueError, match="duplicate authoritative sources"):
        service.add_items(
            dataset.uid_full,
            [_item("iface:1")],
            duplicate_policy="error",
        )
    assert service.add_items(
        dataset.uid_full,
        [_item("iface:1")],
        duplicate_policy="skip",
    ) == []

    with factory() as uow:
        items = uow.datasets.list_dataset_items(dataset.uid_full)
        assert len(items) == 1
        edges = uow.edges.list(src_uid_full=items[0].uid_full)
        assert {(edge.kind, edge.dst_uid_full) for edge in edges} == {
            ("included_in_dataset", dataset.uid_full),
            ("dataset_item_from_source", "iface:1"),
        }
    _dispose(factory)


def test_dataset_service_rejects_name_reuse_with_different_settings(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path / "dataset.sqlite")
    service = DatasetService(uow_factory=factory)
    service.create_or_get(
        name="training",
        settings=DatasetSettings(schema_version="calm.interface.v1").to_dict(),
    )
    with pytest.raises(DatasetIdentityConflictError):
        service.create_or_get(
            name="training",
            settings=DatasetSettings(schema_version="calm.raw_energy.v1").to_dict(),
        )
    _dispose(factory)


def test_learning_dataset_service_persists_joined_contract_and_component_edges(
    tmp_path: Path,
) -> None:
    from calm.public.inputs.settings import (
        DatasetFeature,
        DatasetSplitSettings,
        DatasetTarget,
    )

    factory = _factory(tmp_path / "learning-dataset.sqlite")
    service = DatasetService(uow_factory=factory)
    settings = DatasetSettings(
        schema_version="calm.interface_learning.v1",
        features=(DatasetFeature("steps", "relaxation.n_steps", dtype="int"),),
        targets=(DatasetTarget("energy", "raw_energy.energy_eV"),),
        group_by=("lineage.prototype",),
        split=DatasetSplitSettings(seed=11),
    ).to_dict()
    dataset = service.create_or_get(name="learning", settings=settings)
    group_by = {"lineage.prototype": "proto:1"}
    group_id = dataset_group_uid(group_by)
    item = {
        "schema_version": "calm.interface_learning.v1",
        "source_kind": "joined_interface_record",
        "source_uid_full": "followup:raw:1",
        "interface_uid_full": "interface:relaxed:1",
        "prototype_uid_full": "proto:1",
        "relaxation_followup_uid": "followup:relax:1",
        "raw_energy_followup_uid": "followup:raw:1",
        "terminal_source_kind": "raw_energy",
        "features": {"steps": 5},
        "targets": {"energy": -2.0},
        "group_by": group_by,
        "group_id": group_id,
        "split": dataset_split_name(
            group_id=group_id,
            split=settings["split"],
        ),
        "split_provenance": dataset_split_decision(
            group_id=group_id,
            split=settings["split"],
        ).to_dict(),
        "split_contract_status": "complete_v2",
        "provenance": {
            "prototype_uid_full": "proto:1",
            "relaxed_interface_uid_full": "interface:relaxed:1",
            "relaxation_run_uid_full": "run:relax:1",
            "relaxation_followup_uid": "followup:relax:1",
            "raw_energy_run_uid_full": "run:raw:1",
            "raw_energy_followup_uid": "followup:raw:1",
            "terminal_source_uid_full": "followup:raw:1",
            "relaxation": {
                "scientific_authority": "calculator_backed",
                "converged": True,
                "residual_satisfied": True,
            },
            "raw_energy": {
                "scientific_authority": "calculator_backed",
                "energy_eV": -2.0,
            },
            "thermodynamic": None,
        },
        "artifact_refs": [],
    }

    created = service.add_items(
        dataset.uid_full,
        [item],
        duplicate_policy="error",
    )
    assert len(created) == 1

    tampered = deepcopy(item)
    tampered["source_uid_full"] = "followup:raw:2"
    tampered["raw_energy_followup_uid"] = "followup:raw:2"
    tampered["provenance"]["raw_energy_followup_uid"] = "followup:raw:2"
    tampered["provenance"]["terminal_source_uid_full"] = "followup:raw:2"
    tampered["split"] = next(
        name
        for name in ("train", "validation", "test")
        if name != item["split"]
    )
    with pytest.raises(ValueError, match="deterministic group assignment"):
        service.add_items(
            dataset.uid_full,
            [tampered],
            duplicate_policy="error",
        )

    with factory() as uow:
        reopened = uow.datasets.get_dataset(dataset.uid_full)
        rows = uow.datasets.list_dataset_items(dataset.uid_full)
        assert reopened.metadata["settings"] == settings
        assert rows[0].metadata["features"] == {"steps": 5}
        edges = uow.edges.list(src_uid_full=rows[0].uid_full)
        assert {(edge.kind, edge.dst_uid_full) for edge in edges} == {
            ("included_in_dataset", dataset.uid_full),
            ("dataset_item_from_source", "followup:raw:1"),
            ("dataset_item_from_component", "proto:1"),
            ("dataset_item_from_component", "interface:relaxed:1"),
            ("dataset_item_from_component", "run:relax:1"),
            ("dataset_item_from_component", "followup:relax:1"),
            ("dataset_item_from_component", "run:raw:1"),
        }
    _dispose(factory)

def test_dataset_service_requires_a_callable_uow_factory() -> None:
    with pytest.raises(TypeError, match="UnitOfWork factory"):
        DatasetService(uow_factory=None)  # type: ignore[arg-type]


def test_dataset_service_rejects_an_entered_uow_factory(tmp_path: Path) -> None:
    factory = _factory(tmp_path / "entered-dataset.sqlite")
    uow = factory()
    service = DatasetService(uow_factory=lambda: uow)
    with uow:
        with pytest.raises(ValueError, match="fresh non-entered UnitOfWork"):
            service.create_or_get(
                name="training",
                settings=DatasetSettings(schema_version="calm.interface.v1").to_dict(),
            )
    _dispose(factory)


def test_dataset_service_rejects_unknown_duplicate_policy_before_persistence() -> None:
    def unexpected_uow():
        raise AssertionError("Invalid duplicate policy reached persistence.")

    service = DatasetService(uow_factory=unexpected_uow)
    with pytest.raises(ValueError, match="duplicate policy"):
        service.add_items(
            "dataset:unused",
            [],
            duplicate_policy="merge",
        )
