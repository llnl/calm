from __future__ import annotations

import pytest

ase = pytest.importorskip("ase")
pytest.importorskip("spglib")

from ase import Atoms  # noqa: E402
from ase.build import bulk as ase_bulk  # noqa: E402

from calm.bulk.bulk import Bulk  # noqa: E402
from calm.slab.oriented.terminations import (  # noqa: E402
    _cluster_atoms_by_z,
    enumerate_all_terminations,
    identify_unique_terminations,
)


def _binary_simple_cubic() -> Bulk:
    atoms = Atoms(
        symbols=["Li", "F"],
        scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        cell=[4.0, 4.0, 4.0],
        pbc=True,
    )
    return Bulk(atoms)


def test_binary_stacking_has_two_decorated_termination_classes():
    candidates = identify_unique_terminations(
        _binary_simple_cubic(),
        (0, 0, 1),
        layers=4,
        tolerance=1e-4,
    )

    assert len(candidates) == 2
    assert {item["termination_identity_version"] for item in candidates} == {2}
    assert len({item["termination_identity"]["digest"] for item in candidates}) == 2
    assert all(item["termination_pair_identity"] for item in candidates)


def test_fcc_111_records_abc_period_without_inventing_three_classes():
    aluminium = Bulk(ase_bulk("Al", "fcc", a=4.05, cubic=True))

    candidates = identify_unique_terminations(
        aluminium,
        (1, 1, 1),
        layers=4,
        tolerance=1e-4,
    )

    assert len(candidates) == 1
    assert candidates[0]["decorated_stacking_period_layers"] == 3
    assert candidates[0]["stacking_translation_order"] == 3


def test_all_canonical_cuts_preserve_atom_count_and_ordered_surface_labels():
    enumerated = enumerate_all_terminations(
        _binary_simple_cubic(),
        (0, 0, 1),
        layers=4,
        vacuum=8.0,
        tolerance=1e-4,
    )

    assert len(enumerated) == 2
    assert len({len(item.slab) for item in enumerated}) == 1
    for item in enumerated:
        layers = _cluster_atoms_by_z(item.slab, tolerance=1e-4)
        assert layers[-1].composition == item.metadata["top_composition"]
        assert layers[0].composition == item.metadata["bottom_composition"]
        assert item.metadata["termination_identity_version"] == 2


def test_reversed_surface_normal_remains_versioned_and_deterministic():
    material = _binary_simple_cubic()

    positive = identify_unique_terminations(
        material,
        (0, 0, 1),
        layers=3,
        tolerance=1e-4,
    )
    negative = identify_unique_terminations(
        material,
        (0, 0, -1),
        layers=3,
        tolerance=1e-4,
    )

    assert len(positive) == len(negative) == 2
    assert all(item["termination_identity_version"] == 2 for item in negative)
