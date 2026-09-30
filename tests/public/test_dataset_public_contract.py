from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from calm.project.domain.identity_v2 import (
    dataset_identity_payload,
    dataset_item_identity_payload,
    persisted_entity_uid_v2,
)
from calm.public.errors import DatasetIdentityConflictError
from calm.public.records.datasets import (
    DatasetValidationError,
    export_persisted_dataset,
    normalize_authoritative_dataset_source,
)
from calm.public.project import open_project
from calm.public.records.persistence import (
    ProjectDataset,
    ProjectDatasetItem,
    ProjectEnergyResult,
    RecordAuthority,
)
from calm.public.inputs.settings import DatasetSettings


def test_dataset_settings_are_strict_and_identity_bearing() -> None:
    settings = DatasetSettings(
        schema_version="calm.raw_energy.v1",
        duplicate_policy="skip",
        failure_policy="exclude",
    )
    assert settings.to_dict() == {
        "schema_version": "calm.raw_energy.v1",
        "duplicate_policy": "skip",
        "failure_policy": "exclude",
        "require_complete_provenance": True,
    }
    uid1 = persisted_entity_uid_v2(
        "dataset",
        dataset_identity_payload(name="training", settings=settings.to_dict()),
    )
    uid2 = persisted_entity_uid_v2(
        "dataset",
        dataset_identity_payload(name="training", settings=settings.to_dict()),
    )
    assert uid1 == uid2
    assert uid1.startswith("dataset:v2:")
    assert uid1 != persisted_entity_uid_v2(
        "dataset",
        dataset_identity_payload(
            name="training",
            settings=DatasetSettings(schema_version="calm.interface.v1").to_dict(),
        ),
    )
    item_payload = dataset_item_identity_payload(
        dataset_uid_full=uid1,
        source_uid_full="followup:1",
    )
    assert persisted_entity_uid_v2("dataset_item", item_payload) == (
        persisted_entity_uid_v2("dataset_item", item_payload)
    )

    with pytest.raises(ValueError, match="duplicate_policy"):
        DatasetSettings(duplicate_policy="replace").validate()
    with pytest.raises(ValueError, match="failure_policy"):
        DatasetSettings(failure_policy="ignore").validate()
    with pytest.raises(ValueError, match="Unsupported dataset schema"):
        DatasetSettings(schema_version="unknown.v1").validate()


def test_project_dataset_creation_is_service_backed_and_reopenable(
    tmp_path: Path,
) -> None:
    project = open_project(tmp_path, summarize=False)
    settings = DatasetSettings(schema_version="calm.raw_energy.v1")

    dataset = project.create_dataset(
        "  training  ",
        settings=settings,
        description="service-backed dataset",
        tags="campaign",
    )

    assert dataset.name == "training"
    assert dataset.description == "service-backed dataset"
    assert dataset.settings == settings.to_dict()
    assert dataset.metadata["tags"] == ["campaign"]
    assert dataset._project is project

    same = project.create_dataset("training", settings=settings)
    assert same.uid_full == dataset.uid_full

    reopened = open_project(tmp_path, summarize=False).dataset("training")
    assert reopened.uid_full == dataset.uid_full
    assert reopened.description == "service-backed dataset"

    with pytest.raises(DatasetIdentityConflictError):
        project.create_dataset(
            "training",
            settings=DatasetSettings(schema_version="calm.interface.v1"),
        )


def _energy(*, status: str = "done", failure=None) -> ProjectEnergyResult:
    return ProjectEnergyResult(
        uid_full="followup:energy",
        id_short="f_energy",
        status=status,
        run_uid_full="run:energy",
        run_id_short="r_energy",
        prototype_uid_full="proto:1",
        target_uid_full="iface:1",
        target_kind="interface",
        quantity="total_energy",
        energy_eV=-1.25,
        backend="deterministic",
        backend_identity={"backend": "deterministic"},
        settings={"mode": "single_point"},
        artifact_refs=("artifact:1",),
        failure=failure,
        authority=RecordAuthority.AUTHORITATIVE,
    )


def test_raw_energy_source_normalization_and_failure_policy() -> None:
    settings = DatasetSettings(schema_version="calm.raw_energy.v1")
    row = normalize_authoritative_dataset_source(
        SimpleNamespace(),
        _energy(),
        settings=settings,
    )
    assert row == {
        "schema_version": "calm.raw_energy.v1",
        "source_kind": "raw_energy",
        "source_uid_full": "followup:energy",
        "source_id_short": "f_energy",
        "run_uid_full": "run:energy",
        "run_id_short": "r_energy",
        "interface_uid_full": "iface:1",
        "prototype_uid_full": "proto:1",
        "quantity": "total_energy",
        "energy_eV": -1.25,
        "units": "eV",
        "backend": "deterministic",
        "backend_identity": {"backend": "deterministic"},
        "settings": {"mode": "single_point"},
        "status": "done",
        "failure": None,
        "artifact_refs": ["artifact:1"],
    }

    failed = _energy(status="failed", failure={"message": "boom"})
    with pytest.raises(ValueError, match="is failed"):
        normalize_authoritative_dataset_source(
            SimpleNamespace(),
            failed,
            settings=settings,
        )
    assert (
        normalize_authoritative_dataset_source(
            SimpleNamespace(),
            failed,
            settings=DatasetSettings(
                schema_version="calm.raw_energy.v1",
                failure_policy="exclude",
            ),
        )
        is None
    )
    included = normalize_authoritative_dataset_source(
        SimpleNamespace(),
        failed,
        settings=DatasetSettings(
            schema_version="calm.raw_energy.v1",
            failure_policy="include",
        ),
    )
    assert included is not None and included["status"] == "failed"


class _Repo:
    def resolve_identifier(self, identifier: str) -> str:
        return identifier

    def list_edges(self, **kwargs):
        return [SimpleNamespace()]


class _DatasetProject:
    def __init__(self):
        self._repo = _Repo()
        self._structure_queries = SimpleNamespace(
            get_interface_atoms=self._structure_export_disabled
        )

    @staticmethod
    def _structure_export_disabled(identifier: str):
        del identifier
        raise AssertionError("structure export was disabled")

    def export_dataset(self, _identifier, destination, **kwargs):
        dataset = self.dataset_record
        return export_persisted_dataset(self, dataset, destination, **kwargs)


def _dataset() -> ProjectDataset:
    project = _DatasetProject()
    settings = DatasetSettings(schema_version="calm.raw_energy.v1")
    item = ProjectDatasetItem(
        uid_full="dataset_item:1",
        id_short="t_1",
        dataset_uid_full="dataset:1",
        index=0,
        metadata={
            "schema_version": "calm.raw_energy.v1",
            "source_kind": "raw_energy",
            "source_uid_full": "followup:energy",
            "run_uid_full": "run:energy",
            "interface_uid_full": "iface:1",
            "prototype_uid_full": "proto:1",
            "quantity": "total_energy",
            "energy_eV": -1.25,
            "units": "eV",
            "backend_identity": {"backend": "deterministic"},
            "status": "done",
        },
        authority=RecordAuthority.AUTHORITATIVE,
    )
    project.dataset_items = lambda _identifier: [item]
    dataset = ProjectDataset(
        uid_full="dataset:1",
        id_short="d_1",
        name="training",
        metadata={
            "schema_version": "calm.raw_energy.v1",
            "settings": settings.to_dict(),
        },
        authority=RecordAuthority.AUTHORITATIVE,
        _project=project,
    )
    project.dataset_record = dataset
    return dataset


def test_dataset_export_is_atomic_and_supports_json_and_jsonl(tmp_path: Path) -> None:
    dataset = _dataset()
    result = export_persisted_dataset(
        dataset._project,
        dataset,
        tmp_path / "json_export",
        include_structures=False,
    )
    assert result.manifest_path.name == "manifest.json"
    assert result.manifest_path.exists()
    assert (result.destination / "checksums.sha256").exists()

    result2 = dataset.export(
        tmp_path / "jsonl_export",
        manifest_format="jsonl",
        include_structures=False,
    )
    assert result2.manifest_path.name == "manifest.jsonl"
    lines = result2.manifest_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    sentinel = tmp_path / "existing"
    sentinel.mkdir()
    (sentinel / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        dataset.export(sentinel, include_structures=False)
    assert (sentinel / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_dataset_export_records_unavailable_optional_structures(tmp_path: Path) -> None:
    dataset = _dataset()

    def missing_atoms(identifier: str):
        raise KeyError(f"No atoms available for {identifier}")

    dataset._project._structure_queries.get_interface_atoms = missing_atoms
    result = dataset.export(
        tmp_path / "missing_structure_export",
        include_structures=True,
    )

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["structure_export"] == {
        "requested": True,
        "format": "extxyz",
        "n_exported": 0,
        "n_unavailable": 1,
    }
    assert payload["items"][0]["structure_status"] == "unavailable"
    assert "No atoms available" in payload["items"][0]["structure_error"]
    assert "structure_file" not in payload["items"][0]
    assert result.destination.exists()


def test_dataset_export_does_not_suppress_structure_loader_failures(
    tmp_path: Path,
) -> None:
    dataset = _dataset()

    def broken_loader(_identifier: str):
        raise RuntimeError("structure backend failed")

    dataset._project._structure_queries.get_interface_atoms = broken_loader
    destination = tmp_path / "failed_structure_export"
    with pytest.raises(RuntimeError, match="structure backend failed"):
        dataset.export(destination, include_structures=True)
    assert not destination.exists()


def test_dataset_export_rejects_invalid_dataset(tmp_path: Path) -> None:
    dataset = _dataset()
    bad = ProjectDatasetItem(
        uid_full="dataset_item:bad",
        id_short="t_bad",
        dataset_uid_full="dataset:1",
        index=0,
        metadata={"schema_version": "calm.raw_energy.v1"},
        authority=RecordAuthority.AUTHORITATIVE,
    )
    dataset._project.dataset_items = lambda _identifier: [bad]
    with pytest.raises(DatasetValidationError):
        dataset.export(tmp_path / "bad", include_structures=False)
    assert not (tmp_path / "bad").exists()
