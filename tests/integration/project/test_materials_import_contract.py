"""Authoritative public material-ingest contract tests."""
from __future__ import annotations

from pathlib import Path

from calm.public.inputs.materials import Material as PublicMaterial
from calm.public.project import Project


class FakeWorkspace:
    def __init__(self) -> None:
        self.added: list[dict] = []

    def add_bulk(
        self,
        *,
        structure=None,
        label=None,
        payload=None,
        kind="reference",
        optimized_with=None,
    ):
        persisted = {
            "uid_full": f"bulk:{label or 'x'}",
            "id_short": f"b_{label or 'x'}_1",
            "label": label,
            "payload": dict(payload or {}),
            "kind": kind,
        }
        self.added.append(persisted)
        return persisted


def test_import_returns_public_material_with_ids(tmp_path: Path) -> None:
    workspace = FakeWorkspace()
    project = Project(workspace, path=tmp_path)

    result = project.add_material(
        {"label": "TestMat", "payload": {"note": "import test"}},
        name="TestMat",
    )

    assert isinstance(result, PublicMaterial)
    assert result.uid_full == "bulk:TestMat"
    assert result.id_short == "b_TestMat_1"
    assert workspace.added[0]["label"] == "TestMat"


def test_import_preserves_file_provenance(tmp_path: Path) -> None:
    workspace = FakeWorkspace()
    project = Project(workspace, path=tmp_path)

    result = project.add_material(
        {
            "label": "ProvMat",
            "payload": {
                "source": "file.poscar",
                "source_sha256": "deadbeef",
            },
        },
        name="ProvMat",
    )

    assert result.metadata["source"] == "file.poscar"
    assert workspace.added[0]["payload"]["source"] == "file.poscar"


def test_import_is_idempotent_or_upserts(tmp_path: Path) -> None:
    workspace = FakeWorkspace()
    project = Project(workspace, path=tmp_path)
    input_obj = {"label": "SameMat", "payload": {"note": "x"}}

    first = project.add_material(input_obj, name="SameMat")
    second = project.add_material(input_obj, name="SameMat")

    assert first.uid_full == second.uid_full
    assert first.id_short == second.id_short
    assert not hasattr(project, "_public_records")
