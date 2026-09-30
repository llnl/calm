from __future__ import annotations

from pathlib import Path
import json

import pytest

pytest.importorskip("ase")

from test_helpers import make_test_interface_prototype
from calm.public.errors import DatasetIdentityConflictError
from calm.public.project import open_project
from calm.public.inputs.settings import DatasetSettings


def test_authoritative_dataset_roundtrip(tmp_path: Path) -> None:
    project = open_project(tmp_path)
    mapping = project._workspace.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="dataset_roundtrip", miller_a=(1, 0, 0), miller_b=(1, 0, 0), n_atoms_interface=2, interface_area_A2=10.0)
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]
    interface = project._workspace.create_derived_interface(
        prototype_uid,
        label="dataset_relaxed",
        stage="relaxed",
        params={"search_name": "dataset_search"},
    )

    settings = DatasetSettings(
        schema_version="calm.interface.v1",
        duplicate_policy="error",
    )
    dataset = project.create_dataset(
        "interface_dataset",
        [interface.uid_full],
        settings=settings,
        description="authoritative interface dataset",
        tags=["roundtrip"],
    )
    assert dataset.is_authoritative
    assert dataset.schema_version == "calm.interface.v1"
    assert len(dataset.items()) == 1
    assert dataset.validate().ok

    with pytest.raises(ValueError, match="duplicate authoritative sources"):
        dataset.add([interface.uid_full])

    same = project.create_dataset(
        "interface_dataset",
        settings=settings,
    )
    assert same.uid_full == dataset.uid_full

    with pytest.raises(DatasetIdentityConflictError):
        project.create_dataset(
            "interface_dataset",
            settings=DatasetSettings(schema_version="calm.raw_energy.v1"),
        )

    exported = dataset.export(
        tmp_path / "dataset_export",
        include_structures=False,
    )
    assert exported.manifest_path.exists()

    # A stale alpha-era reporting file cannot override database-owned dataset
    # declarations or membership and is not required for reopen.
    (tmp_path / "calm-public-records.json").write_text(
        json.dumps(
            {
                "schema_version": 6,
                "datasets": [
                    {
                        "name": "interface_dataset",
                        "uid_full": "dataset:misleading",
                        "description": "not authoritative",
                    }
                ],
                "dataset_items": [],
                "energies": [],
            }
        ),
        encoding="utf-8",
    )

    reopened = open_project(tmp_path)
    loaded = reopened.dataset("interface_dataset")
    assert loaded.uid_full == dataset.uid_full
    assert loaded.description == "authoritative interface dataset"
    assert len(loaded.items()) == 1
    assert loaded.validate().ok

    item = loaded.items()[0]
    edges = reopened.edges(
        src=item.uid_full,
        dst=interface.uid_full,
        kind="dataset_item_from_source",
    )
    assert len(edges) == 1


def test_duplicate_skip_is_idempotent(tmp_path: Path) -> None:
    project = open_project(tmp_path)
    mapping = project._workspace.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="dataset_skip", miller_a=(1, 0, 0), miller_b=(1, 0, 0), interface_area_A2=5.0)
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]
    interface = project._workspace.create_derived_interface(
        prototype_uid,
        label="dataset_skip_interface",
        stage="relaxed",
    )
    dataset = project.create_dataset(
        "dataset_skip",
        [interface.uid_full, interface.uid_full],
        settings=DatasetSettings(
            schema_version="calm.interface.v1",
            duplicate_policy="skip",
        ),
    )
    assert len(dataset.items()) == 1
    assert len(dataset.add([interface.uid_full])) == 0
    assert len(dataset.items()) == 1
