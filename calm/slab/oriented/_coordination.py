"""Coordination graph used by slab layer peeling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ase import Atoms
from ase.neighborlist import neighbor_list


@dataclass(frozen=True, slots=True)
class SlabCoordination:
    """Coordination matrix and maximum row coordination for one slab."""

    matrix: np.ndarray
    maximum: int


def build_slab_coordination(
    atoms: Atoms,
    *,
    rad_scalar: float = 1.05,
    distance_floor: float = 1.0e-3,
) -> SlabCoordination:
    """Build the metal-safe periodic coordination graph used by ``Slab.fix_layers``.

    The cutoff is the nearest nonzero minimum-image distance multiplied by
    ``rad_scalar``.  Periodic-image multiplicity is retained because the layer
    peeling algorithm compares row coordination against the slab-wide maximum.
    """

    n_atoms = len(atoms)
    if n_atoms == 0:
        return SlabCoordination(
            matrix=np.zeros((0, 0), dtype=np.uint16),
            maximum=0,
        )

    distances = np.asarray(atoms.get_all_distances(mic=True), dtype=float)
    valid = distances[distances > float(distance_floor)]
    if valid.size == 0:
        raise RuntimeError(
            "Could not determine a nearest-neighbor distance for slab "
            "coordination construction."
        )

    cutoff = float(valid.min() * float(rad_scalar))
    i, j, _offset = neighbor_list("ijS", atoms, cutoff)

    coordination = np.zeros((n_atoms, n_atoms), dtype=np.uint16)
    np.add.at(coordination, (i, j), 1)
    if not np.array_equal(coordination, coordination.T):
        coordination = coordination + coordination.T
    np.fill_diagonal(coordination, 0)

    if not np.any(coordination):
        raise RuntimeError(
            "Coordination graph is empty (no bonds detected); increase rad_scalar "
            "or inspect the slab geometry."
        )

    row_coordination = coordination.sum(axis=1)
    return SlabCoordination(
        matrix=coordination,
        maximum=int(row_coordination.max()),
    )
