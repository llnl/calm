from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from calm.public.records.generated_surface import GeneratedSurface
from calm.public.inputs.materials import Material
from calm.public.project import Project
from calm.public.persistence.repository import PublicRepository
from slab_record_fixtures import current_atoms, current_slab_payload, current_slab_uid


class _SurfaceWorkspace:
    def __init__(self, slabs, *, atomistic_parent: bool = True):
        self.slabs = list(slabs)
        self.calls: list[tuple[str, dict]] = []
        self.bulk = SimpleNamespace(
            uid_full="bulk:v2:test",
            id_short="b_lif",
            payload={"atoms": {}} if atomistic_parent else {},
        )

    def get_bulk(self, identifier: str):
        if identifier in {self.bulk.uid_full, self.bulk.id_short}:
            return self.bulk
        raise KeyError(identifier)

    def build_slabs(self, bulk: str, **kwargs):
        self.calls.append((bulk, dict(kwargs)))
        return list(self.slabs)


def _material() -> Material:
    return Material(
        name="LiF",
        label="LiF",
        atoms=object(),
        id_short="b_lif",
    )


def _surface_record():
    bulk_uid = "bulk:v2:test"
    miller = (1, 0, 0)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        atoms=current_atoms(),
        params={"layers": 4, "vacuum": 12.0},
        layers=4,
        vacuum_A=12.0,
    )
    return SimpleNamespace(
        uid_full=current_slab_uid(
            bulk_uid_full=bulk_uid,
            miller=miller,
            payload=payload,
        ),
        id_short="s_lif_100",
        bulk_uid_full=bulk_uid,
        bulk_id_short="b_lif",
        material="LiF",
        miller=miller,
        payload=payload,
    )


def test_project_surface_generation_calls_exact_workspace_contract_once(
    tmp_path: Path,
) -> None:
    workspace = _SurfaceWorkspace([_surface_record()])
    project = Project(workspace, path=tmp_path)
    slabs = project.generate_surfaces(
        _material(),
        millers=[(1, 0, 0)],
        layers=4,
        vacuum=12.0,
    )

    assert all(isinstance(surface, GeneratedSurface) for surface in slabs)
    assert [surface.id_short for surface in slabs] == ["s_lif_100"]
    assert workspace.calls == [
        (
            "b_lif",
            {
                "millers": [(1, 0, 0)],
                "params": {"layers": 4, "vacuum": 12.0},
                "enumerate_terminations": True,
            },
        )
    ]


def test_surface_generation_rejects_non_atomistic_parent_before_build(
    tmp_path: Path,
) -> None:
    workspace = _SurfaceWorkspace(
        [SimpleNamespace(id_short="s_empty")],
        atomistic_parent=False,
    )
    project = Project(workspace, path=tmp_path)

    with pytest.raises(ValueError, match="no current atoms payload"):
        project.generate_surfaces(
            _material(),
            millers=[(1, 0, 0)],
        )

    assert workspace.calls == []


def test_public_repository_requires_composition_root_adapter() -> None:
    with pytest.raises(TypeError, match="requires a WorkspaceAdapter"):
        PublicRepository(object())


def test_retired_public_conveniences_remain_absent() -> None:
    assert not hasattr(Project, "import_material")
    assert not hasattr(Project, "get_by_hash")
    assert not hasattr(GeneratedSurface, "stable_uid")
    assert not hasattr(GeneratedSurface, "validate_exportable")


def test_generated_surface_reuses_materialized_slab_geometry() -> None:
    ase = pytest.importorskip("ase")
    import numpy as np

    atoms = ase.Atoms(
        "Al2",
        scaled_positions=[[0.0, 0.0, 0.25], [0.5, 0.5, 0.75]],
        cell=[[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 12.0]],
        pbc=True,
    )
    from calm.structure.payloads import atoms_to_dict

    bulk_uid = "bulk:v2:test"
    miller = (1, 0, 0)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        atoms=atoms_to_dict(atoms),
        params={"layers": 2, "vacuum": 10.0},
        layers=2,
        vacuum_A=10.0,
    )
    uid_full = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=miller,
        payload=payload,
    )
    record = SimpleNamespace(
        uid_full=uid_full,
        id_short="s_test",
        bulk_uid_full=bulk_uid,
        bulk_id_short="b_test",
        miller=miller,
        vacuum=10.0,
        params={"layers": 2, "vacuum": 10.0},
        payload=payload,
        atoms=atoms,
    )

    surface = GeneratedSurface.from_workspace(record)
    materialized = surface.to_surface().to_slab()

    assert materialized.uid == uid_full
    assert materialized.project_slab_id_short == "s_test"
    assert materialized.hkl == (1, 0, 0)
    assert np.array_equal(materialized.atoms.positions, atoms.positions)
    assert np.array_equal(materialized.atoms.cell.array, atoms.cell.array)
