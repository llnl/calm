import numpy as np
from ase import Atoms

from calm.interface.config import EnergyConfig
from calm.interface.energy.reference import get_strained_bulk, get_ortho_map


def make_simple_conv_cell():
    # simple cubic conventional cell 1x1x1
    positions = [(0.0, 0.0, 0.0)]
    cell = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    conv = Atoms("H", positions=positions, cell=cell, pbc=True)
    return conv


def _fallback_energy_config():
    return EnergyConfig(
        strict_reference_frame=False,
        warn_on_reference_frame_fallback=False,
    )


class DummySlab:
    def __init__(self, conv_cell, hkl=(0, 0, 1)):
        self.bulk = type("B", (), {})()
        self.bulk.conv = conv_cell
        # conv_cell.cell is in ASE row-major convention; code expects conv_cell as transposed columns
        self.bulk.conv_cell = np.asarray(conv_cell.cell).T
        self.bulk.prim_cell = np.asarray(conv_cell.cell).T
        self.hkl = hkl


def test_get_strained_bulk_identity():
    conv = make_simple_conv_cell()
    slab = DummySlab(conv)
    super_slab = conv.copy()
    F = np.eye(3)

    strained = get_strained_bulk(
        slab,
        super_slab,
        F,
        config=_fallback_energy_config(),
    )
    # strained cell should equal conv cell (modulo ASE transposition semantics)
    Q = get_ortho_map(slab, super_slab, strict=False, warn=False)
    F_conv = Q @ F @ Q.T
    expected = F_conv @ np.asarray(conv.cell).T
    assert np.allclose(np.asarray(strained.cell).T, expected)


def test_get_strained_bulk_stretch():
    conv = make_simple_conv_cell()
    slab = DummySlab(conv)
    super_slab = conv.copy()
    F = np.diag([1.02, 0.98, 1.0])

    strained = get_strained_bulk(
        slab,
        super_slab,
        F,
        config=_fallback_energy_config(),
    )
    Q = get_ortho_map(slab, super_slab, strict=False, warn=False)
    F_conv = Q @ F @ Q.T
    expected = F_conv @ np.asarray(conv.cell).T
    assert np.allclose(np.asarray(strained.cell).T, expected)
