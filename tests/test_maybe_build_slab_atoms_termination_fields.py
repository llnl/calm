from ase import Atoms
import numpy as np

from calm.bulk.bulk import Bulk
from calm.project.application.slabs import _build_slab_atoms_if_available
from calm.slab.oriented.terminations import identify_unique_terminations
from calm.structure.payloads import atoms_to_dict


def make_simple_li_f_bulk():
    # Simple cubic 2-atom cell Li at origin, F at body center
    cell = np.diag([4.0, 4.0, 4.0])
    scaled_positions = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]
    atoms = Atoms(
        symbols=["Li", "F"],
        scaled_positions=scaled_positions,
        cell=cell,
        pbc=True,
    )
    return atoms


def test_build_slab_atoms_if_available_records_top_and_bottom_for_default():
    atoms = make_simple_li_f_bulk()
    payload = {"atoms": atoms_to_dict(atoms), "params": {"layers": 4}}

    res = _build_slab_atoms_if_available(
        bulk_payload=payload,
        miller=(1, 0, 0),
        vacuum=12.0,
        termination_shift=0,
    )
    assert isinstance(res, dict)
    assert "termination" in res
    assert "termination_top" in res
    assert "termination_bottom" in res
    assert isinstance(res["termination_top"], str)
    assert isinstance(res["termination_bottom"], str)
    assert res["characterization"]["schema"] == "calm.surface_characterization.v1"
    assert res["characterization"]["area_A2"] > 0.0
    assert res["characterization"]["slab_thickness_A"] is not None


def test_build_slab_atoms_if_available_records_top_and_bottom_for_shift():
    atoms = make_simple_li_f_bulk()
    payload = {"atoms": atoms_to_dict(atoms), "params": {"layers": 4}}

    candidates = identify_unique_terminations(
        Bulk(atoms),
        (1, 0, 0),
        layers=4,
        tolerance=0.3,
    )
    assert len(candidates) == 2
    selected = candidates[1]

    res = _build_slab_atoms_if_available(
        bulk_payload=payload,
        miller=(1, 0, 0),
        vacuum=12.0,
        termination_shift=int(selected["shift"]),
        termination_metadata=selected,
    )
    assert isinstance(res, dict)
    assert "termination" in res
    assert "termination_top" in res
    assert "termination_bottom" in res
    # For shifted termination both may be equal to the computed label
    assert isinstance(res["termination_top"], str)
    assert isinstance(res["termination_bottom"], str)
    assert res["characterization"]["schema"] == "calm.surface_characterization.v1"
    assert res["characterization"]["area_A2"] > 0.0
    assert res["characterization"]["slab_thickness_A"] is not None
