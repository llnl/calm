"""Ownership guards for authoritative public interface persistence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.errors import ProjectPersistenceError
from calm.public.project import Project
from calm.public.workflows.saving import PublicProjectSaver
from calm.public.records.interfaces import InterfaceModel
from calm.public.inputs.settings import BuildSettings


class _QueryOnly:
    def list_prototypes(self, *args, **kwargs):
        return []


class _FailingWorkspace:
    query = _QueryOnly()

    def create_derived_interface(self, prototype, **kwargs):
        del prototype, kwargs
        raise RuntimeError("authoritative write failed")


class _MissingIdentityWorkspace:
    query = _QueryOnly()

    def create_derived_interface(self, prototype, **kwargs):
        del prototype, kwargs
        return SimpleNamespace(uid_full=None, id_short=None)


def _model() -> InterfaceModel:
    return InterfaceModel(
        SimpleNamespace(atoms=[], prototype_uid="proto:authoritative"),
        candidate={"project_prototype_uid": "proto:authoritative"},
        build_settings=BuildSettings(),
    )


def test_authoritative_failure_does_not_create_interface_projection(tmp_path) -> None:
    project = Project(_FailingWorkspace(), path=tmp_path / "project.calm")

    with pytest.raises(RuntimeError, match="authoritative write failed"):
        project._saver.record_interface_model(_model(), name="iface")
    assert not hasattr(project, "_public_records")


def test_authoritative_result_requires_both_durable_identifiers(tmp_path) -> None:
    project = Project(_MissingIdentityWorkspace(), path=tmp_path / "project.calm")

    with pytest.raises(
        ProjectPersistenceError,
        match="must return uid_full and id_short",
    ):
        project._saver.record_interface_model(_model(), name="iface")
    assert not hasattr(project, "_public_records")



def test_interface_persistence_rejects_retired_sidecar_tags(tmp_path) -> None:
    project = Project(_FailingWorkspace(), path=tmp_path / "project.calm")

    with pytest.raises(TypeError, match="unexpected keyword argument 'tags'"):
        project._saver.record_interface_model(
            _model(),
            name="iface",
            tags=["smoke"],
        )

def test_generic_project_persistence_dispatch_is_retired(tmp_path) -> None:
    project = Project(_FailingWorkspace(), path=tmp_path / "project.calm")

    assert not hasattr(project, "_persist")
    assert not hasattr(project._saver, "persist")


def test_public_project_saver_requires_project_owned_adapter() -> None:
    with pytest.raises(TypeError, match="Project-owned WorkspaceAdapter"):
        PublicProjectSaver(workspace=object(), repo=None)
