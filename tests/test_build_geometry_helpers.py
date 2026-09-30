from __future__ import annotations

import numpy as np


def _make_stub_atoms(positions, cell=None):
    class Stub:
        pass

    s = Stub()
    s.positions = np.array(positions, dtype=float)
    if cell is None:
        cell = np.eye(3)
    s.cell = np.array(cell, dtype=float)
    def set_cell(c, scale_atoms=False):
        # simple replacement (scale_atoms ignored for stub)
        s.cell = np.array(c, dtype=float)
    s.set_cell = set_cell
    return s


def test_apply_deformation_gradient_and_cell_update():
    from calm.interface.building._geometry import _apply_deformation_gradient, _cell_array

    atoms = _make_stub_atoms([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    F = np.array([[2.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    _apply_deformation_gradient(atoms, F)
    assert np.allclose(atoms.positions[1], np.array([2.0, 0.0, 0.0]))
    assert np.allclose(_cell_array(atoms)[0, 0], 2.0)


def test_rotate_atoms_cartesian():
    from calm.interface.building._geometry import _rotate_atoms_cartesian, _cell_array

    atoms = _make_stub_atoms([[1.0, 0.0, 0.0]])
    R = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    _rotate_atoms_cartesian(atoms, R)
    assert np.allclose(atoms.positions[0][:2], np.array([0.0, 1.0]))
    # cell is multiplied by R.T in the implementation; identity cell -> R.T
    assert np.allclose(_cell_array(atoms)[0, 1], float(np.asarray(R).T[0, 1]))


def test_zmin_zmax_empty():
    from calm.interface.building._geometry import _zmin_zmax

    atoms = _make_stub_atoms([])
    assert _zmin_zmax(atoms) == (0.0, 0.0)
