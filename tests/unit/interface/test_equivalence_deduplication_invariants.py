from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from calm.interface.matching.grouping import (
    _supercell_contact_motif_signature_2d,
    group_prototypes_by_numerical_metric_then_contact_motif,
    metric_grouping_key_2d,
)
from calm.interface.results import PrototypeSearchResult


class _Cell:
    def __init__(self, value: np.ndarray) -> None:
        self.array = np.asarray(value, dtype=float)


class _Atoms:
    def __init__(
        self,
        *,
        positions: np.ndarray,
        numbers: np.ndarray,
        cell: np.ndarray | None = None,
    ) -> None:
        self.positions = np.asarray(positions, dtype=float)
        self.numbers = np.asarray(numbers, dtype=int)
        self.cell = _Cell(np.eye(3) if cell is None else cell)


class _Slab:
    def __init__(self, atoms: _Atoms) -> None:
        self.atoms = atoms


@dataclass(frozen=True)
class _PublicSupercell:
    N_tot: np.ndarray
    G_red: np.ndarray


@dataclass(frozen=True)
class _PublicPrototype:
    prototype_uid: str
    match_score: float
    d_cell: float
    slab_a: _Slab
    slab_b: _Slab
    supercell_a: _PublicSupercell
    supercell_b: _PublicSupercell


def _identity_group() -> list[np.ndarray]:
    return [np.eye(2, dtype=int)]


def test_contact_motif_signature_respects_declared_equivalence() -> None:
    atoms = _Atoms(
        positions=np.array(
            [
                [0.0, 0.0, 0.0],
                [0.5, 0.5, 0.0],
                [0.25, 0.25, 1.0],
            ]
        ),
        numbers=np.array([8, 14, 6]),
    )
    slab = _Slab(atoms)
    matrix = np.array([[2, 1], [0, 2]], dtype=int)
    unimodular = np.array([[1, 1], [0, 1]], dtype=int)
    signature = _supercell_contact_motif_signature_2d(slab, matrix, side="bottom")

    reordered = _Slab(
        _Atoms(
            positions=atoms.positions[[1, 0, 2]],
            numbers=atoms.numbers[[1, 0, 2]],
        )
    )
    assert _supercell_contact_motif_signature_2d(
        reordered,
        matrix,
        side="bottom",
    ) == signature

    translated = _Slab(
        _Atoms(
            positions=atoms.positions + np.array([1.0, -2.0, 0.0]),
            numbers=atoms.numbers,
        )
    )
    assert _supercell_contact_motif_signature_2d(
        translated,
        matrix,
        side="bottom",
    ) == signature
    assert _supercell_contact_motif_signature_2d(
        slab,
        matrix @ unimodular,
        side="bottom",
    ) == signature

    changed_species = _Slab(
        _Atoms(
            positions=atoms.positions,
            numbers=np.array([8, 8, 6]),
        )
    )
    assert _supercell_contact_motif_signature_2d(
        changed_species,
        matrix,
        side="bottom",
    ) != signature


def test_public_metric_variant_grouping_is_available_and_deterministic() -> None:
    slab_a = _Slab(
        _Atoms(
            positions=np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]]),
            numbers=np.array([8, 14]),
        )
    )
    slab_b = _Slab(
        _Atoms(
            positions=np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]]),
            numbers=np.array([3, 9]),
        )
    )
    cell = _PublicSupercell(N_tot=np.eye(2, dtype=int), G_red=np.eye(2))
    later = _PublicPrototype("later", 2.0, 0.2, slab_a, slab_b, cell, cell)
    earlier = _PublicPrototype("earlier", 1.0, 0.1, slab_a, slab_b, cell, cell)

    grouped = group_prototypes_by_numerical_metric_then_contact_motif(
        [later, earlier]
    )
    assert len(grouped) == 1
    group = next(iter(grouped.values()))
    assert len(group.variants) == 1
    assert next(iter(group.variants.values())) == [earlier, later]

    result_like = SimpleNamespace(prototypes=[later, earlier])
    via_method = PrototypeSearchResult.group_numerical_variants(result_like)
    assert list(via_method) == list(grouped)


def test_metric_grouping_rejects_non_spd_or_nonfinite_inputs() -> None:
    assert metric_grouping_key_2d(
        np.eye(2), quantization_step_angstrom2=1e-4
    ).quantized_gram == (10000, 0, 10000)
    with pytest.raises(ValueError, match="positive definite"):
        metric_grouping_key_2d(np.diag([1.0, -1.0]))
    with pytest.raises(ValueError, match="finite"):
        metric_grouping_key_2d(
            np.array([[np.nan, 0.0], [0.0, 1.0]])
        )
    with pytest.raises(ValueError, match=r"scale \* G"):
        metric_grouping_key_2d(np.eye(2) * 1e308)

    tilted = _Slab(
        _Atoms(
            positions=np.array([[0.0, 0.0, 0.0]]),
            numbers=np.array([8]),
            cell=np.array(
                [[1.0, 0.0, 0.1], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            ),
        )
    )
    with pytest.raises(ValueError, match="global Cartesian xy plane"):
        _supercell_contact_motif_signature_2d(
            tilted,
            np.eye(2, dtype=int),
            side="bottom",
        )
