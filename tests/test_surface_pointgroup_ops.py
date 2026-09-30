"""Smoke/stress tests for surface point-group extraction.

These tests ensure that the spglib adapter returns well-formed, unimodular
integer operations for common low-index slabs.
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.mark.parametrize("hkl", [(1, 1, 1), (1, 1, 0), (1, 0, 0)])
def test_get_surface_pointgroup_ops_2d_basic(hkl):
    spglib = pytest.importorskip("spglib")
    assert spglib is not None  # silence linter

    from ase.build import bulk as ase_bulk

    from calm.bulk.bulk import Bulk
    from calm.slab.slab import Slab
    from calm.slab.slab import SlabSpec
    from calm.symmetry.spglib_adapter import get_surface_pointgroup_ops

    bulk_atoms = ase_bulk("Al", a=4.05, cubic=True)
    bulk = Bulk(bulk_atoms)
    slab = Slab(bulk, SlabSpec(miller=hkl, n_layers=3, vacuum=8.0, pbc=(True, True, True)))

    ops2 = get_surface_pointgroup_ops(slab.atoms)
    assert isinstance(ops2, list)
    assert len(ops2) >= 1

    I2 = np.eye(2, dtype=int)
    assert any(np.array_equal(op, I2) for op in ops2)

    for op in ops2:
        op = np.asarray(op)
        assert op.shape == (2, 2)
        assert issubclass(op.dtype.type, np.integer)
        det = int(round(float(np.linalg.det(op))))
        assert abs(det) == 1

    from calm.symmetry.surface_group import (
        surface_metric_from_cell_rows,
        validate_surface_symmetry_group_2d,
    )

    metric = surface_metric_from_cell_rows(slab.atoms.cell.array)
    validated = validate_surface_symmetry_group_2d(
        ops2,
        metric=metric,
        metric_tolerance=1e-8,
    )
    assert len(validated) == len(ops2)


@pytest.mark.parametrize(
    ("symbol", "crystalstructure", "lattice_parameter"),
    [
        ("Al", "fcc", 4.05),
        ("Si", "diamond", 5.43),
    ],
)
def test_centered_and_nonsymmorphic_bulk_fixtures_form_surface_groups(
    symbol,
    crystalstructure,
    lattice_parameter,
):
    pytest.importorskip("spglib")
    from ase.build import bulk as ase_bulk

    from calm.symmetry.surface_group import (
        surface_metric_from_cell_rows,
        validate_surface_symmetry_group_2d,
    )
    from calm.symmetry.spglib_adapter import get_surface_pointgroup_ops

    atoms = ase_bulk(
        symbol,
        crystalstructure,
        a=lattice_parameter,
        cubic=True,
    )
    operations = get_surface_pointgroup_ops(atoms)
    metric = surface_metric_from_cell_rows(atoms.cell.array)

    validated = validate_surface_symmetry_group_2d(
        operations,
        metric=metric,
        metric_tolerance=1e-8,
    )
    assert len(validated) == len(operations)


def test_skew_low_symmetry_fixture_returns_a_valid_group():
    pytest.importorskip("spglib")
    from ase import Atoms

    from calm.symmetry.surface_group import (
        surface_metric_from_cell_rows,
        validate_surface_symmetry_group_2d,
    )
    from calm.symmetry.spglib_adapter import get_surface_pointgroup_ops

    atoms = Atoms(
        symbols=["Na", "Cl", "F"],
        scaled_positions=[
            (0.07, 0.13, 0.19),
            (0.31, 0.47, 0.59),
            (0.73, 0.83, 0.37),
        ],
        cell=[
            (3.1, 0.0, 0.0),
            (0.8, 2.7, 0.0),
            (0.0, 0.0, 6.2),
        ],
        pbc=True,
    )
    operations = get_surface_pointgroup_ops(atoms)
    metric = surface_metric_from_cell_rows(atoms.cell.array)

    validated = validate_surface_symmetry_group_2d(
        operations,
        metric=metric,
        metric_tolerance=1e-8,
    )
    assert len(validated) >= 1
    assert any(np.array_equal(operation, np.eye(2, dtype=int)) for operation in validated)
