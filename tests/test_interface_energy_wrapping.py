"""Regression tests for interface construction canonicalization.

We rely on two-interface (slab + vacuum) models for registry search and derived
interface export. A critical invariance for usability is that the constructed
interface should *not* be split across the periodic boundary in z due to a
numerical negative-zero drift and a subsequent full 3D ASE wrap.

This test guards the followups-facing interface builder used by
`build_interface_from_prototype_with_strain`.
"""

from __future__ import annotations

import numpy as np


def test_followups_build_simple_interface_does_not_wrap_in_z() -> None:
    """_build_simple_interface must avoid wrapping atoms across z.

    We construct a minimal two-slab system with a tiny negative z drift.

    - If the implementation uses `Atoms.wrap()` in z, the slightly negative
      atom will wrap to ~Lz, creating an artificial split slab.
    - The correct behavior is to clamp z into [0, Lz) while wrapping only x/y.
    """

    from ase import Atoms

    # Import the private helper explicitly: we want to guard this internal.
    from calm.project.application.followups.interface_energy import _build_simple_interface

    # Two tiny "slabs" represented by a couple of atoms each.
    # Include a small negative z to simulate numerical drift.
    slab_a = Atoms(
        symbols=["H", "H"],
        positions=[
            [0.0, 0.0, -1e-8],
            [0.0, 0.0, 0.5 - 1e-8],
        ],
        cell=np.diag([2.0, 2.0, 2.0]),
        pbc=[True, True, True],
    )

    slab_b = Atoms(
        symbols=["He"],
        positions=[[0.0, 0.0, -2e-8]],
        cell=np.diag([2.0, 2.0, 2.0]),
        pbc=[True, True, True],
    )

    z_pad = 1.0
    iface = _build_simple_interface(slab_a, slab_b, z_padding=z_pad)

    Lz = float(iface.cell[2, 2])
    z = iface.positions[:, 2]

    # Canonical placement: no negative z, and no atom should be wrapped to the
    # very top boundary due to a tiny negative drift.
    assert z.min() >= -1e-12

    # In this constructed system the top of the upper slab should be far from
    # the boundary by ~z_pad (1 Å). If a drifted atom were wrapped, we'd see a
    # coordinate extremely close to Lz.
    assert not np.any(z > (Lz - 1e-3))

