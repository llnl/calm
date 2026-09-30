from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pytest

from calm.interface.matching.grouping import (
    CONTACT_MOTIF_GROUPING_KEY_VERSION,
    METRIC_GROUPING_KEY_VERSION,
    NUMERICAL_GROUPING_POLICY,
    NUMERICAL_GROUPING_POLICY_VERSION,
    contact_motif_grouping_key_2d,
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
class _Supercell:
    N_tot: np.ndarray
    G_red: np.ndarray


@dataclass(frozen=True)
class _Prototype:
    prototype_uid: str
    match_score: float
    d_cell: float
    slab_a: _Slab
    slab_b: _Slab
    supercell_a: _Supercell
    supercell_b: _Supercell


def _slab(
    positions: np.ndarray,
    numbers: np.ndarray,
    *,
    cell: np.ndarray | None = None,
) -> _Slab:
    return _Slab(_Atoms(positions=positions, numbers=numbers, cell=cell))


def test_metric_grouping_key_records_units_version_and_collision_policy() -> None:
    step = 1e-4
    base = metric_grouping_key_2d(
        np.eye(2),
        quantization_step_angstrom2=step,
    )
    same_bin = metric_grouping_key_2d(
        np.diag([1.0 + 0.4 * step, 1.0]),
        quantization_step_angstrom2=step,
    )
    next_bin = metric_grouping_key_2d(
        np.diag([1.0 + 0.6 * step, 1.0]),
        quantization_step_angstrom2=step,
    )
    same_bin_far_side = metric_grouping_key_2d(
        np.diag([1.0 - 0.49 * step, 1.0]),
        quantization_step_angstrom2=step,
    )
    boundary_left = metric_grouping_key_2d(
        np.diag([1.0 + 0.49 * step, 1.0]),
        quantization_step_angstrom2=step,
    )
    boundary_right = metric_grouping_key_2d(
        np.diag([1.0 + 0.51 * step, 1.0]),
        quantization_step_angstrom2=step,
    )

    assert same_bin == base == same_bin_far_side
    assert next_bin != base
    assert boundary_left != boundary_right
    assert base.signature_version == METRIC_GROUPING_KEY_VERSION
    assert base.gram_unit == "angstrom^2"
    assert base.rounding == "nearest_half_to_even"
    assert base.normalization == "none_absolute_binning"
    assert base.input_representation == "canonical_reduced_spd_gram"
    assert base.cartesian_orthogonal_quotient == "via_gram"
    assert base.symmetry_validation.startswith("max_asymmetry_le_64eps")
    assert base.relation == "tolerance_defined_numerical_grouping"
    assert base.collision_possible is True
    assert base.to_dict()["quantized_gram"] == [10000, 0, 10000]


def test_metric_grouping_uses_reduced_metric_and_is_not_scale_invariant() -> None:
    reduced_basis = np.array([[2.0, 0.3], [0.0, 1.2]])
    angle = np.deg2rad(37.0)
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    )
    gram = reduced_basis.T @ reduced_basis
    rotated_gram = (rotation @ reduced_basis).T @ (rotation @ reduced_basis)

    key = metric_grouping_key_2d(gram)
    assert metric_grouping_key_2d(rotated_gram) == key
    assert metric_grouping_key_2d(4.0 * gram) != key

    # Unimodular basis invariance belongs to the preceding canonical Gauss
    # reduction.  Once that stage supplies the same G_red, the numerical key is
    # independent of the integer embedding carried beside it.
    cell_a = _Supercell(N_tot=np.eye(2, dtype=int), G_red=gram)
    cell_b = _Supercell(
        N_tot=np.array([[1, 1], [0, 1]], dtype=int),
        G_red=gram.copy(),
    )
    assert metric_grouping_key_2d(cell_a.G_red) == metric_grouping_key_2d(
        cell_b.G_red
    )


def test_contact_motif_key_declares_quotients_units_and_version() -> None:
    atoms = _slab(
        np.array(
            [
                [0.0, 0.0, 0.0],
                [0.5, 0.5, 0.0],
                [0.25, 0.25, 1.0],
            ]
        ),
        np.array([8, 14, 6]),
    )
    matrix = np.array([[2, 1], [0, 2]], dtype=int)
    unimodular = np.array([[1, 1], [0, 1]], dtype=int)

    key = contact_motif_grouping_key_2d(
        atoms,
        matrix,
        side="bottom",
    )
    reordered = _slab(
        atoms.atoms.positions[[1, 0, 2]],
        atoms.atoms.numbers[[1, 0, 2]],
    )
    translated = _slab(
        atoms.atoms.positions + np.array([1.0, -2.0, 0.0]),
        atoms.atoms.numbers,
    )

    assert contact_motif_grouping_key_2d(
        reordered,
        matrix,
        side="bottom",
    ) == key
    assert contact_motif_grouping_key_2d(
        translated,
        matrix,
        side="bottom",
    ) == key
    assert contact_motif_grouping_key_2d(
        atoms,
        matrix @ unimodular,
        side="bottom",
    ) == key
    assert key.signature_version == CONTACT_MOTIF_GROUPING_KEY_VERSION
    assert key.z_window_angstrom == 0.25
    assert key.fractional_quantization_step == 1e-8
    assert key.height_quantization_step_angstrom == 1e-3
    assert key.periodic_translation_quotient == (
        "primitive_translations_within_declared_supercell"
    )
    assert key.surface_symmetry_quotient == "none"
    assert key.species_policy == "atomic_number_exact"
    assert key.layer_selection_boundary == "inclusive"
    assert key.normalization == "fractional_xy_and_relative_height"
    assert key.digest_algorithm == "sha256_little_endian_int64_v1"
    assert key.collision_possible is True


def test_contact_selection_boundary_and_species_are_explicit() -> None:
    matrix = np.eye(2, dtype=int)
    boundary = _slab(
        np.array([[0.0, 0.0, 0.0], [0.4, 0.4, 0.25]]),
        np.array([8, 14]),
    )
    included = contact_motif_grouping_key_2d(
        boundary,
        matrix,
        side="bottom",
        z_window_angstrom=0.25,
    )
    excluded = contact_motif_grouping_key_2d(
        boundary,
        matrix,
        side="bottom",
        z_window_angstrom=np.nextafter(0.25, 0.0),
    )
    changed_species = _slab(
        boundary.atoms.positions,
        np.array([8, 8]),
    )

    assert included != excluded
    assert contact_motif_grouping_key_2d(
        changed_species,
        matrix,
        side="bottom",
        z_window_angstrom=0.25,
    ) != included


def test_contact_quantization_collision_is_visible_in_key_contract() -> None:
    matrix = np.eye(2, dtype=int)
    base = _slab(
        np.array([[0.0, 0.0, 0.0], [0.25, 0.25, 0.0]]),
        np.array([8, 14]),
    )
    distinct_same_bin = _slab(
        np.array([[0.0, 0.0, 0.0], [0.25 + 4e-9, 0.25, 0.0]]),
        np.array([8, 14]),
    )
    distinct_next_bin = _slab(
        np.array([[0.0, 0.0, 0.0], [0.25 + 6e-9, 0.25, 0.0]]),
        np.array([8, 14]),
    )

    key = contact_motif_grouping_key_2d(base, matrix, side="bottom")
    assert contact_motif_grouping_key_2d(
        distinct_same_bin,
        matrix,
        side="bottom",
    ) == key
    assert contact_motif_grouping_key_2d(
        distinct_next_bin,
        matrix,
        side="bottom",
    ) != key
    assert key.collision_possible is True


def test_versioned_grouping_is_order_invariant_and_separate_from_identity() -> None:
    slab_a = _slab(
        np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]]),
        np.array([8, 14]),
    )
    slab_b = _slab(
        np.array([[0.0, 0.0, 0.0], [0.5, 0.5, 0.0]]),
        np.array([3, 9]),
    )
    cell = _Supercell(N_tot=np.eye(2, dtype=int), G_red=np.eye(2))
    later = _Prototype("later", 2.0, 0.2, slab_a, slab_b, cell, cell)
    earlier = _Prototype("earlier", 1.0, 0.1, slab_a, slab_b, cell, cell)

    forward = group_prototypes_by_numerical_metric_then_contact_motif(
        [later, earlier]
    )
    reverse = group_prototypes_by_numerical_metric_then_contact_motif(
        [earlier, later]
    )
    assert list(forward) == list(reverse)
    group = next(iter(forward.values()))
    reverse_group = next(iter(reverse.values()))
    assert next(iter(group.variants.values())) == [earlier, later]
    assert next(iter(reverse_group.variants.values())) == [earlier, later]
    assert group.grouping_policy == NUMERICAL_GROUPING_POLICY
    assert group.grouping_policy_version == NUMERICAL_GROUPING_POLICY_VERSION
    assert group.exact_identity is False
    assert group.collision_limitations

    result_like = SimpleNamespace(prototypes=[later, earlier])
    explicit = PrototypeSearchResult.group_numerical_variants(result_like)
    assert explicit == forward


def test_grouping_controls_reject_ambiguous_or_invalid_values() -> None:
    with pytest.raises(TypeError, match="Boolean"):
        metric_grouping_key_2d(np.eye(2), quantization_step_angstrom2=True)
    with pytest.raises(ValueError, match="positive"):
        metric_grouping_key_2d(np.eye(2), quantization_step_angstrom2=0.0)
    with pytest.raises(ValueError, match="symmetric"):
        metric_grouping_key_2d(np.array([[1.0, 0.2], [0.0, 1.0]]))

    slab = _slab(np.array([[0.0, 0.0, 0.0]]), np.array([8]))
    with pytest.raises(TypeError, match="Boolean"):
        contact_motif_grouping_key_2d(
            slab,
            np.eye(2, dtype=int),
            side="bottom",
            z_window_angstrom=False,
        )
    with pytest.raises(TypeError, match="integer"):
        contact_motif_grouping_key_2d(
            slab,
            np.eye(2, dtype=int),
            side="bottom",
            xy_decimals=True,
        )
