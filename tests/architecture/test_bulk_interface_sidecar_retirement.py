"""Guard Stage C2 retirement of material and interface sidecar entities."""

from __future__ import annotations

import inspect
from pathlib import Path

from calm.public.project import Project
from calm.public.workflows.saving import PublicProjectSaver
from calm.public.persistence import repository as public_repository
from calm.public.persistence.repository import PublicRepository
from calm.public.persistence.adapter import WorkspaceAdapter


ROOT = Path(__file__).resolve().parents[2]


def test_automatic_reporting_sidecar_is_fully_retired() -> None:
    assert not (ROOT / "calm" / "public" / "sidecar.py").exists()
    assert not hasattr(Project, "_record_path")
    assert not hasattr(Project, "_flush_public_records")


def test_entity_projection_modules_remain_deleted() -> None:
    assert not (ROOT / "calm" / "public" / "records.py").exists()
    assert not (ROOT / "calm" / "public" / "sidecar_store.py").exists()


def test_entity_persistence_signatures_have_no_sidecar_tag_channel() -> None:
    assert "tags" not in inspect.signature(Project.add_material).parameters
    assert "tags" not in inspect.signature(
        PublicProjectSaver.record_interface_model
    ).parameters
    assert "tags" not in inspect.signature(
        WorkspaceAdapter.persist_derived_interface
    ).parameters


def test_repository_has_one_authoritative_composition_dependency() -> None:
    parameters = inspect.signature(PublicRepository).parameters
    assert tuple(parameters) == ("workspace_adapter",)

    source = (ROOT / "calm" / "public" / "persistence" / "repository.py").read_text(
        encoding="utf-8"
    )
    assert "SidecarStore" not in source
    assert "_merge_interface_rows" not in source
    assert 'table("bulks")' not in source
    assert 'table("interfaces")' not in source
    assert "build_uid" not in public_repository._INTERFACE_ID_FIELDS


def test_material_persistence_has_no_projection_write_or_flush() -> None:
    source = (ROOT / "calm" / "public" / "workflows" / "materials.py").read_text(
        encoding="utf-8"
    )
    assert "record_bulk" not in source
    assert "flush(" not in source
