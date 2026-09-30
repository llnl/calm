from __future__ import annotations

import inspect
from pathlib import Path

from calm.project.application.workspace_validation import WorkspaceValidator
from calm.project.runtime.workspace import Workspace


def test_workspace_accepts_only_the_uow_factory_boundary() -> None:
    parameters = inspect.signature(Workspace).parameters
    assert "uow" not in parameters
    assert parameters["uow_factory"].default is inspect.Parameter.empty


def test_workspace_runtime_does_not_retain_a_uow() -> None:
    source = Path("calm/project/runtime/workspace.py").read_text(encoding="utf-8")
    assert "self._uow =" not in source
    assert "self._ws._uow" not in source
    assert "_facade" not in source


def test_workspace_validator_is_factory_only() -> None:
    parameters = inspect.signature(WorkspaceValidator).parameters
    assert set(parameters) == {"uow_factory"}
    source = Path("calm/project/application/workspace_validation.py").read_text(
        encoding="utf-8"
    )
    assert "self._uow =" not in source
    assert "fresh_uow(" in source


def test_bootstrap_does_not_construct_a_discarded_shared_uow() -> None:
    source = Path("calm/project/bootstrap.py").read_text(encoding="utf-8")
    assert "uow = uow_factory()" not in source
    assert "uow=uow" not in source
    assert "uow_factory=uow_factory" in source


def test_public_adapter_does_not_probe_retired_workspace_uow_state() -> None:
    source = Path("calm/public/persistence/adapter.py").read_text(encoding="utf-8")
    assert 'getattr(self._ws, "_uow"' not in source
    assert "self._ws._uow" not in source
