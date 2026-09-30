
import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("sqlalchemy")

from ase import Atoms

from calm.slab.oriented.tilt import compute_slab_tilt_metadata


def _make_tilted_atoms():
    cell = np.array([[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.5, -0.3, 5.0]])
    a = Atoms("Cu", positions=[[0, 0, 0]], cell=cell, pbc=True)
    return a


def test_compute_tilt_metadata_basic():
    a = _make_tilted_atoms()
    meta = compute_slab_tilt_metadata(a, transforms=None)
    assert "tilt_xy" in meta
    assert isinstance(meta["tilt_xy"], list) and len(meta["tilt_xy"]) == 2
    assert meta["tilt_magnitude"] == pytest.approx(np.linalg.norm(a.cell.array[2, :2]))
