from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from calm.public.errors import ProjectPersistenceError
from calm.public.project import Project


class _ConfigurationRepository:
    def __init__(self) -> None:
        self.row: dict | None = None

    def get(self):
        return None if self.row is None else dict(self.row)

    def upsert(
        self,
        *,
        default_mlip=None,
        default_calculator_uid_full=None,
        workflow_defaults=None,
    ):
        self.row = {
            "default_mlip": default_mlip,
            "default_calculator_uid_full": default_calculator_uid_full,
            "workflow_defaults": (
                None if workflow_defaults is None else dict(workflow_defaults)
            ),
        }
        return dict(self.row)


class _UnitOfWork:
    def __init__(self, repository: _ConfigurationRepository) -> None:
        self.project_configuration = repository

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Workspace:
    def __init__(self, repository: _ConfigurationRepository | None = None) -> None:
        self.configuration_repository = repository or _ConfigurationRepository()
        self._uow_factory = lambda: _UnitOfWork(self.configuration_repository)
        self._calculators: dict[str, object] = {}

    def register_calculator(self, spec):
        from calm.project.domain.identity_v2 import (
            calculator_identity_payload,
            persisted_entity_uid_v2,
        )

        uid = persisted_entity_uid_v2(
            "calculator",
            calculator_identity_payload(spec=spec.to_dict()),
        )
        record = SimpleNamespace(
            uid_full=uid,
            id_short="c_default",
            family=spec.family,
            model=spec.model,
        )
        self._calculators[uid] = record
        return record

    def get_calculator(self, identifier):
        return self._calculators.get(identifier)


def test_configure_persists_only_authoritative_database_state(tmp_path: Path):
    workspace = _Workspace()
    project = Project(workspace, path=tmp_path)

    configured = project.configure(
        mlip="local_mlip",
        calculator={"family": "test", "model": "v1"},
        defaults={"foo": "bar"},
    )

    assert configured["default_mlip"] == "local_mlip"
    assert configured["default_calculator_uid_full"].startswith("calc:")
    assert configured["workflow_defaults"] == {"foo": "bar"}
    assert project._configuration == configured
    assert not hasattr(project, "_public_records")


def test_reopened_project_loads_authoritative_configuration(tmp_path: Path):
    repository = _ConfigurationRepository()
    workspace = _Workspace(repository)
    project = Project(workspace, path=tmp_path)
    project.configure(mlip="x_mlip", defaults={"a": 1})

    reopened = Project(_Workspace(repository), path=tmp_path)

    assert reopened._configuration == {
        "default_mlip": "x_mlip",
        "default_calculator_uid_full": None,
        "workflow_defaults": {"a": 1},
    }
    assert not hasattr(reopened, "_public_records")


def test_configure_merges_workflow_defaults(tmp_path: Path):
    project = Project(_Workspace(), path=tmp_path)
    project.configure(defaults={"a": 1})

    updated = project.configure(defaults={"b": 2})

    assert updated["workflow_defaults"] == {"a": 1, "b": 2}


def test_configure_rejects_mlip_and_calculator_replacement(tmp_path: Path):
    project = Project(_Workspace(), path=tmp_path)
    project.configure(
        mlip="first",
        calculator={"family": "test", "model": "v1"},
    )

    with pytest.raises(RuntimeError, match="already uses MLIP"):
        project.configure(mlip="second")

    with pytest.raises(RuntimeError, match="different calculator identity"):
        project.configure(calculator={"family": "test", "model": "v2"})


def test_configure_requires_authoritative_project_storage(tmp_path: Path):
    project = Project(SimpleNamespace(), path=tmp_path)

    with pytest.raises(ProjectPersistenceError, match="project database"):
        project.configure(mlip="test")
