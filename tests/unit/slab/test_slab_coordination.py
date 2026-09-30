from __future__ import annotations

import numpy as np
import pytest
from ase import Atoms
from ase.build import fcc211

from calm.slab.oriented._coordination import build_slab_coordination


def test_slab_coordination_is_symmetric_and_nonempty() -> None:
    atoms = fcc211("Al", (3, 3, 3), a=4.05, vacuum=10.0)
    result = build_slab_coordination(atoms)

    assert result.matrix.shape == (len(atoms), len(atoms))
    np.testing.assert_array_equal(result.matrix, result.matrix.T)
    assert not np.any(np.diag(result.matrix))
    assert result.maximum == int(result.matrix.sum(axis=1).max())
    assert result.maximum > 0


def test_slab_coordination_rejects_structure_without_nonzero_pair_distance() -> None:
    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=[5.0, 5.0, 5.0], pbc=True)

    with pytest.raises(RuntimeError, match="nearest-neighbor distance"):
        build_slab_coordination(atoms)
