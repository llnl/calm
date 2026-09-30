from __future__ import annotations

from pathlib import Path

import pytest

from calm.public.inputs.materials import Material
from calm.public.project import Project
from calm.public.collections.structures import MaterialCollection
from calm.public.records.surfaces import Surface


class _MaterialWorkspace:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.rows: dict[str, dict] = {}

    def add_bulk(self, **kwargs):
        self.calls.append(dict(kwargs))
        label = kwargs["label"]
        row = {
            "uid_full": f"bulk:{label}",
            "id_short": f"b_{label}",
            "label": label,
            "kind": kwargs["kind"],
            "payload": dict(kwargs.get("payload") or {}),
            "calculator": kwargs.get("optimized_with"),
        }
        self.rows[row["uid_full"]] = row
        return row

    def list_bulks(self, *, limit=None):
        rows = list(self.rows.values())
        return rows if limit is None else rows[:limit]

    def get_bulk(self, identifier):
        for row in self.rows.values():
            if identifier in {row["uid_full"], row["id_short"], row["label"]}:
                return row
        raise KeyError(identifier)


def test_materials_import_uses_exact_authoritative_contract_once(tmp_path: Path) -> None:
    workspace = _MaterialWorkspace()
    project = Project(workspace, path=tmp_path)

    result = project.add_material(
        {"label": "LiF", "payload": {"source": "LiF.poscar"}},
    )

    assert result.uid_full == "bulk:LiF"
    assert result.id_short == "b_LiF"
    assert result.metadata["source"] == "LiF.poscar"
    assert workspace.calls == [
        {
            "structure": None,
            "label": "LiF",
            "payload": {"source": "LiF.poscar"},
            "kind": "reference",
            "optimized_with": None,
        }
    ]
    assert not hasattr(project, "_public_records")


def test_project_add_material_rejects_retired_sidecar_tags(tmp_path: Path) -> None:
    project = Project(_MaterialWorkspace(), path=tmp_path)

    with pytest.raises(TypeError, match="unexpected keyword argument 'tags'"):
        project.add_material({"label": "LiF"}, tags=["input"])


def test_project_add_material_uses_the_single_material_owner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = Project(_MaterialWorkspace(), path=tmp_path)
    calls: list[object] = []

    def fake_persist_material(obj, **kwargs):
        calls.append((obj, kwargs))
        return "saved"

    monkeypatch.setattr(project._saver, "persist_material", fake_persist_material)
    material = Material(name="LiF", label="LiF", atoms=None)

    assert project.add_material(material, name="via_add") == "saved"
    assert [entry[1]["name"] for entry in calls] == ["via_add"]


def test_material_persistence_errors_propagate_without_retry(tmp_path: Path) -> None:
    class FailingWorkspace:
        def __init__(self) -> None:
            self.calls = 0

        def add_bulk(self, **kwargs):
            self.calls += 1
            raise TypeError("backend persistence defect")

    workspace = FailingWorkspace()
    project = Project(workspace, path=tmp_path)

    with pytest.raises(TypeError, match="backend persistence defect"):
        project.add_material({"label": "LiF"})

    assert workspace.calls == 1
    assert not hasattr(project, "_public_records")


def test_material_persistence_requires_authoritative_identity(tmp_path: Path) -> None:
    class ProjectionOnlyWorkspace:
        def add_bulk(self, **kwargs):
            return {"label": kwargs["label"], "payload": {}}

    project = Project(ProjectionOnlyWorkspace(), path=tmp_path)

    with pytest.raises(RuntimeError, match="must return uid_full and id_short"):
        project.add_material({"label": "LiF"})
    assert not hasattr(project, "_public_records")


def test_repeated_material_ingest_does_not_create_reporting_state(
    tmp_path: Path,
) -> None:
    workspace = _MaterialWorkspace()
    project = Project(workspace, path=tmp_path)

    first = project.add_material({"label": "LiF", "payload": {"revision": 1}})
    second = project.add_material({"label": "LiF", "payload": {"revision": 2}})

    assert first.uid_full == second.uid_full == "bulk:LiF"
    assert workspace.rows["bulk:LiF"]["payload"]["revision"] == 2
    assert not hasattr(project, "_public_records")


def test_optimized_material_mapping_preserves_calculator_provenance(
    tmp_path: Path,
) -> None:
    workspace = _MaterialWorkspace()
    project = Project(workspace, path=tmp_path)

    project.add_material(
        {
            "label": "LiF_opt",
            "kind": "optimized",
            "optimized_with": "mace:small",
        }
    )

    assert workspace.calls[0]["kind"] == "optimized"
    assert workspace.calls[0]["optimized_with"] == "mace:small"


def test_material_query_uses_authoritative_bulk_identity(tmp_path: Path) -> None:
    workspace = _MaterialWorkspace()
    project = Project(workspace, path=tmp_path)
    project.add_material(
        {"label": "LiF", "payload": {"source": "authoritative"}}
    )

    material = project.material("LiF")

    assert material.uid_full == "bulk:LiF"
    assert material.id_short == "b_LiF"
    assert material.metadata["source"] == "authoritative"
    assert not hasattr(project, "_public_records")



def test_material_query_ignores_retired_sidecar_file(tmp_path: Path) -> None:
    path = tmp_path / "project.calm"
    path.mkdir()
    workspace = _MaterialWorkspace()
    project = Project(workspace, path=path)
    project.add_material({"label": "LiF"})
    assert not (path / "calm-public-records.json").exists()

    legacy = path / "calm-public-records.json"
    legacy.write_text(
        '{"schema_version": 6, "bulks": [{"label": "wrong"}]}',
        encoding="utf-8",
    )
    reopened = Project(workspace, path=path)
    material = reopened.material("LiF")

    assert material.uid_full == "bulk:LiF"
    assert material.id_short == "b_LiF"
    assert not hasattr(reopened, "_public_records")

def test_project_add_material_rejects_unsupported_objects(tmp_path: Path) -> None:
    project = Project(_MaterialWorkspace(), path=tmp_path)

    with pytest.raises(TypeError, match="material input must be"):
        project.add_material(object())


def test_retired_material_compatibility_surfaces_remain_absent() -> None:
    assert not hasattr(MaterialCollection, "import_material")
    assert not hasattr(MaterialCollection, "filter")
    assert not hasattr(Material, "lattice_parameters")
    assert not hasattr(Material, "surface")
    assert not hasattr(Material, "surfaces")
    assert not hasattr(Surface, "to_slab_spec")
