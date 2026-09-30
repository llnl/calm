from __future__ import annotations

import pytest

pytest.importorskip("ase")

import types
from pathlib import Path

from calm.public.project import Project
from calm.public.inputs.materials import Material
from calm.slab.oriented.tilt import compute_slab_tilt_metadata
from calm.structure.payloads import atoms_to_dict
from slab_record_fixtures import current_slab_payload, current_slab_uid


def _current_surface(
    *,
    id_short: str,
    miller: tuple[int, int, int],
    material: str,
    atoms=None,
):
    bulk_uid_full = f"bulk:test:{material}"
    atoms_payload = None
    if atoms is not None:
        atoms.info["calm:tilt"] = compute_slab_tilt_metadata(
            atoms,
            transforms=None,
        )
        atoms_payload = atoms_to_dict(atoms)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid_full,
        miller=miller,
        atoms=atoms_payload,
    )
    return types.SimpleNamespace(
        uid_full=current_slab_uid(
            bulk_uid_full=bulk_uid_full,
            miller=miller,
            payload=payload,
        ),
        id_short=id_short,
        bulk_uid_full=bulk_uid_full,
        bulk_id_short=f"b_{id_short}",
        miller=miller,
        material=material,
        atoms=atoms,
        payload=payload,
    )


def test_generate_surfaces_uses_workspace_builder(tmp_path):
    # Fake workspace with build_slabs implementation that records args
    called = {}

    def build_slabs(bulk, *, millers, payload=None, params=None, enumerate_terminations=False):
        called['bulk'] = bulk
        called['millers'] = millers
        called['payload_keys'] = sorted(payload.keys()) if isinstance(payload, dict) else None
        return [
            _current_surface(
                id_short='s_test',
                miller=millers[0],
                material='LiF',
                atoms=lif.to_ase().copy(),
            )
        ]

    fake_ws = types.SimpleNamespace()
    fake_ws.build_slabs = build_slabs
    fake_ws.get_bulk = lambda identifier: types.SimpleNamespace(
        uid_full="bulk:test:LiF",
        id_short="b_test",
        payload={"atoms": {}},
    )

    proj = Project(workspace=fake_ws, path=tmp_path)

    # Create a public Material with ASE atoms via from_file to ensure to_ase works
    structures_dir = Path(__file__).resolve().parents[2] / 'examples' / 'Structures'
    lif = Material.from_file(structures_dir / 'LiF.poscar', name='LiF')
    lif.id_short = 'b_test'

    slabs = proj.generate_surfaces(lif, millers=[(1, 0, 0)], layers=4, vacuum=12.0)
    assert isinstance(slabs, list)
    assert called.get('bulk') == 'b_test'
    assert called.get('millers') == [(1, 0, 0)]
    # The persisted parent bulk is the sole atomistic construction source.
    assert called.get('payload_keys') is None


def test_export_surfaces_writes_files(tmp_path):
    # Make a fake slab with ASE atoms
    from ase import Atoms

    slab = _current_surface(
        id_short='s_test',
        miller=(1, 0, 0),
        material='LiF',
        atoms=Atoms(
            symbols=['Li', 'F'],
            positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        ),
    )

    # Fake workspace with query.get_slab for resolution
    bulk = types.SimpleNamespace(
        uid_full=slab.bulk_uid_full,
        id_short=slab.bulk_id_short,
        label=slab.material,
        calculator=None,
    )

    class FakeQuery:
        def get_bulk(self, uid_or_short: str):
            if uid_or_short in {bulk.uid_full, bulk.id_short}:
                return bulk
            raise KeyError

        def get_slab(self, uid_or_short: str):
            if uid_or_short in {slab.uid_full, slab.id_short}:
                return slab
            raise KeyError

        def list_slabs(self, limit=None):
            return [slab]

    fake_ws = FakeQuery()

    proj = Project(workspace=fake_ws, path=tmp_path)

    out = tmp_path / 'surfaces'
    written = proj.export_surfaces('s_test', directory=out, format='vasp')
    assert isinstance(written, list)
    assert len(written) == 1
    assert written[0].exists()


def test_export_surfaces_by_criteria(tmp_path):
    # Build fake slab rows returned by workspace query.list_slabs
    from ase import Atoms

    slab1 = _current_surface(
        id_short='s_lif_100',
        miller=(1, 0, 0),
        material='LiF_opt',
        atoms=Atoms(
            symbols=['Li', 'F'],
            positions=[[0, 0, 0], [0.5, 0.5, 0.5]],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        ),
    )

    slab2 = _current_surface(
        id_short='s_li2o_100',
        miller=(1, 0, 0),
        material='Li2O_opt',
        atoms=Atoms(
            symbols=['Li', 'Li', 'O', 'O'],
            positions=[
                [0, 0, 0],
                [0.5, 0.5, 0.5],
                [0.25, 0.25, 0.25],
                [0.75, 0.75, 0.75],
            ],
            cell=[4.0, 4.0, 4.0],
            pbc=True,
        ),
    )

    bulk1 = types.SimpleNamespace(
        uid_full=slab1.bulk_uid_full,
        id_short=slab1.bulk_id_short,
        label=slab1.material,
        calculator=None,
    )
    bulk2 = types.SimpleNamespace(
        uid_full=slab2.bulk_uid_full,
        id_short=slab2.bulk_id_short,
        label=slab2.material,
        calculator=None,
    )

    class FakeQuery2:
        def list_slabs(self, limit=None):
            return [slab1, slab2]

        def get_bulk(self, uid_or_short: str):
            if uid_or_short in {bulk1.uid_full, bulk1.id_short}:
                return bulk1
            if uid_or_short in {bulk2.uid_full, bulk2.id_short}:
                return bulk2
            raise KeyError

        def get_slab(self, uid_or_short: str):
            if uid_or_short in {slab1.uid_full, slab1.id_short}:
                return slab1
            if uid_or_short in {slab2.uid_full, slab2.id_short}:
                return slab2
            raise KeyError

    fake_ws = FakeQuery2()

    proj = Project(workspace=fake_ws, path=tmp_path)

    out = tmp_path / 'surfaces'
    written = proj.export_surfaces(materials=['LiF_opt','Li2O_opt'], millers=[(1,0,0)], directory=out, format='vasp')
    assert isinstance(written, list)
    assert len(written) == 2
    for p in written:
        assert p.exists()


def test_export_surfaces_requires_one_exact_selection_mode(tmp_path):
    project = Project(workspace=types.SimpleNamespace(), path=tmp_path)

    with pytest.raises(ValueError, match="requires identifiers or selection criteria"):
        project.export_surfaces(directory=tmp_path / "none")

    with pytest.raises(TypeError, match="identifiers or material/Miller criteria"):
        project.export_surfaces(
            "s_test",
            directory=tmp_path / "mixed",
            materials=["LiF"],
        )
