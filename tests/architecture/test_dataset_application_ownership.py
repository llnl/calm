from __future__ import annotations

import inspect

from calm.project.application.datasets import DatasetService
from calm.project.infrastructure.db.repos import SqlAlchemyDatasetRepository
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from calm.project.runtime.workspace import Workspace
from calm.public.persistence.adapter import WorkspaceAdapter


def test_workspace_dataset_writes_delegate_to_application_service() -> None:
    create_source = inspect.getsource(Workspace.create_or_get_dataset)
    items_source = inspect.getsource(Workspace.add_dataset_items)

    assert "self._dataset_service.create_or_get(" in create_source
    assert "self._dataset_service.add_items(" in items_source
    combined = create_source + items_source
    assert "uow.datasets" not in combined
    assert "edges.add" not in combined
    assert "except Exception" not in combined


def test_dataset_service_owns_identity_validation_and_lineage() -> None:
    source = inspect.getsource(DatasetService)
    assert "dataset_identity_payload" in source
    assert "dataset_item_identity_payload" in source
    assert "uow.edges.add(" in source
    assert "included_in_dataset" in source
    assert "dataset_item_from_source" in source
    assert "dataset_item_uses_artifact" in source
    assert "fresh non-entered UnitOfWork" in source
    assert "lambda" not in source


def test_dataset_repository_is_row_only_and_typed() -> None:
    source = inspect.getsource(SqlAlchemyDatasetRepository)
    assert "_dataset_from_row" in source
    assert "_dataset_item_from_row" in source
    assert "edges" not in source
    assert "Dataset(" in source
    assert "DatasetItem(" in source
    assert "list[dict]" not in source


def test_dataset_repository_is_required_by_current_uow() -> None:
    source = inspect.getsource(SqlAlchemyUnitOfWork.__enter__)
    assert "self.datasets = SqlAlchemyDatasetRepository" in source
    start = source.index("self.datasets = SqlAlchemyDatasetRepository")
    dataset_block = source[start:]
    assert "except Exception" not in dataset_block


def test_public_dataset_mutations_use_exact_workspace_methods() -> None:
    create_source = inspect.getsource(WorkspaceAdapter.create_or_get_dataset)
    items_source = inspect.getsource(WorkspaceAdapter.add_dataset_items)

    assert "self._ws.create_or_get_dataset(" in create_source
    assert "self._ws.add_dataset_items(" in items_source
    combined = create_source + items_source
    assert "getattr(" not in combined
    assert "except TypeError" not in combined
