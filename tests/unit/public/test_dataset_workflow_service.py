from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.workflows.datasets import ProjectDatasetWorkflowService
from calm.public.records.persistence import ProjectDataset
from calm.public.inputs.settings import DatasetSettings


class _Workspace:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.added: list[dict] = []

    def create_or_get_dataset(self, **kwargs):
        self.created.append(dict(kwargs))
        return SimpleNamespace(
            uid_full="dataset:one",
            id_short="d_one",
            name=kwargs["name"],
            description=kwargs.get("description"),
            metadata={
                "schema_version": kwargs["settings"]["schema_version"],
                "settings": dict(kwargs["settings"]),
                "tags": list(kwargs.get("tags") or []),
            },
            created_at=None,
        )

    def add_dataset_items(self, dataset, items, *, duplicate_policy):
        self.added.append(
            {
                "dataset": dataset,
                "items": list(items),
                "duplicate_policy": duplicate_policy,
            }
        )
        return [
            SimpleNamespace(
                uid_full=f"dataset_item:{index}",
                id_short=f"t_{index}",
                dataset_uid_full=dataset,
                index=index,
                metadata=dict(item),
                artifact_refs=tuple(item.get("artifact_refs") or ()),
                created_at=None,
            )
            for index, item in enumerate(items)
        ]


class _Repository:
    def __init__(self, workspace: _Workspace) -> None:
        self._workspace = workspace

    def get_dataset(self, identifier):
        assert identifier in {"dataset:one", "d_one", "training"}
        if self._workspace.created:
            created = self._workspace.created[-1]
            settings = dict(created["settings"])
            description = created.get("description")
            tags = list(created.get("tags") or [])
        else:
            settings = DatasetSettings(
                schema_version="calm.raw_energy.v1",
                duplicate_policy="skip",
            ).to_dict()
            description = None
            tags = []
        return SimpleNamespace(
            uid_full="dataset:one",
            id_short="d_one",
            name="training",
            description=description,
            metadata={
                "schema_version": settings["schema_version"],
                "settings": settings,
                "tags": tags,
            },
            created_at=None,
        )


def _service(project=None):
    workspace = _Workspace()
    repository = _Repository(workspace)
    service = ProjectDatasetWorkflowService(
        project=project or SimpleNamespace(),
        workspace=workspace,
        repository=repository,
    )
    return service, workspace, repository


def test_create_dataset_normalizes_before_persistence(monkeypatch) -> None:
    project = SimpleNamespace(marker="project")
    service, workspace, _repository = _service(project)
    calls = []

    def normalize(owner, item, *, settings):
        assert owner is project
        calls.append((item, settings.schema_version))
        return {
            "source_uid_full": f"followup:{item}",
            "source_kind": "raw_energy",
            "schema_version": settings.schema_version,
        }

    monkeypatch.setattr(
        "calm.public.records.datasets.normalize_authoritative_dataset_source",
        normalize,
    )
    settings = DatasetSettings(schema_version="calm.raw_energy.v1")

    dataset = service.create_dataset(
        "  training  ",
        ["one", "two"],
        settings=settings,
        description="authoritative dataset",
        tags="campaign",
    )

    assert isinstance(dataset, ProjectDataset)
    assert dataset.uid_full == "dataset:one"
    assert dataset._project is project
    assert calls == [
        ("one", "calm.raw_energy.v1"),
        ("two", "calm.raw_energy.v1"),
    ]
    assert workspace.created == [
        {
            "name": "training",
            "settings": settings.to_dict(),
            "description": "authoritative dataset",
            "tags": ["campaign"],
        }
    ]
    assert workspace.added[0]["dataset"] == "dataset:one"
    assert workspace.added[0]["duplicate_policy"] == "error"


def test_create_dataset_duplicate_preflight_precedes_record_creation(
    monkeypatch,
) -> None:
    service, workspace, _repository = _service()

    monkeypatch.setattr(
        "calm.public.records.datasets.normalize_authoritative_dataset_source",
        lambda *_args, **_kwargs: {"source_uid_full": "followup:duplicate"},
    )

    with pytest.raises(ValueError, match="duplicate authoritative sources"):
        service.create_dataset(
            "training",
            ["one", "two"],
            settings=DatasetSettings(schema_version="calm.raw_energy.v1"),
        )

    assert workspace.created == []
    assert workspace.added == []


def test_add_dataset_items_uses_persisted_settings(monkeypatch) -> None:
    service, workspace, _repository = _service()
    observed = []

    def normalize(_owner, item, *, settings):
        observed.append(settings.duplicate_policy)
        return {
            "source_uid_full": f"followup:{item}",
            "source_kind": "raw_energy",
            "schema_version": settings.schema_version,
        }

    monkeypatch.setattr(
        "calm.public.records.datasets.normalize_authoritative_dataset_source",
        normalize,
    )

    created = service.add_dataset_items("training", "three")

    assert observed == ["skip"]
    assert len(created) == 1
    assert workspace.added == [
        {
            "dataset": "dataset:one",
            "items": [
                {
                    "source_uid_full": "followup:three",
                    "source_kind": "raw_energy",
                    "schema_version": "calm.raw_energy.v1",
                }
            ],
            "duplicate_policy": "skip",
        }
    ]


def test_dataset_workflow_rejects_invalid_public_controls() -> None:
    service, _workspace, _repository = _service()

    with pytest.raises(ValueError, match="name must be non-empty"):
        service.create_dataset("   ")
    with pytest.raises(TypeError, match="DatasetSettings"):
        service.create_dataset("training", settings={})
    with pytest.raises(TypeError, match="tags"):
        service.create_dataset("training", tags=1)
    with pytest.raises(ValueError, match="selectors must be non-empty"):
        service.add_dataset_items(" ", [])
