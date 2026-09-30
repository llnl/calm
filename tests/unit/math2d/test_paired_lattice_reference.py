"""Exact fixtures for the future production paired-lattice math kernel."""

from __future__ import annotations

from reference.coupled_match_reference import (
    FULL_SQUARE_GROUP,
    IDENTITY_2D,
    IDENTITY_PAIR_KEY_FULL,
    SIGMA5_CELL_C4,
    SIGMA5_CELL_C5,
    SIGMA5_PAIR_KEY_FULL,
    canonicalize_primitive_pair_2d,
    det2,
    determinantal_divisor_rank2,
    maximal_minors_rank2,
    primitiveize_pair_matrix_2d,
    repeat_source_pair,
    right_multiply_rank2,
    stack_pair,
)


def test_equal_sigma5_cell_repetition_primitiveizes_to_identity_class() -> None:
    source = stack_pair(SIGMA5_CELL_C4, SIGMA5_CELL_C4)
    factorization = primitiveize_pair_matrix_2d(source)

    assert factorization.repeat_index == 5
    assert abs(det2(factorization.source_right_factor)) == 5
    assert right_multiply_rank2(
        factorization.primitive_matrix,
        factorization.source_right_factor,
    ) == source
    assert determinantal_divisor_rank2(factorization.primitive_matrix) == 1
    assert canonicalize_primitive_pair_2d(
        factorization.primitive_matrix,
        point_group=FULL_SQUARE_GROUP,
    ) == IDENTITY_PAIR_KEY_FULL


def test_cross_sigma5_cells_are_already_primitive_and_nontrivial() -> None:
    source = stack_pair(SIGMA5_CELL_C4, SIGMA5_CELL_C5)
    factorization = primitiveize_pair_matrix_2d(source)

    assert maximal_minors_rank2(source) == (5, 4, 3, -3, 4, 5)
    assert factorization.repeat_index == 1
    assert factorization.source_right_factor == IDENTITY_2D
    assert factorization.primitive_matrix == source
    assert canonicalize_primitive_pair_2d(
        factorization.primitive_matrix,
        point_group=FULL_SQUARE_GROUP,
    ) == SIGMA5_PAIR_KEY_FULL


def test_index25_sigma5_repeat_collapses_to_index5_primitive_key() -> None:
    source = repeat_source_pair(
        SIGMA5_CELL_C4,
        SIGMA5_CELL_C5,
        (1, 0, 0, 5),
    )
    factorization = primitiveize_pair_matrix_2d(source)

    block_a = source[:4]
    block_b = source[4:]
    assert abs(det2(block_a)) == 25
    assert abs(det2(block_b)) == 25
    assert factorization.repeat_index == 5
    assert right_multiply_rank2(
        factorization.primitive_matrix,
        factorization.source_right_factor,
    ) == source
    assert canonicalize_primitive_pair_2d(
        factorization.primitive_matrix,
        point_group=FULL_SQUARE_GROUP,
    ) == SIGMA5_PAIR_KEY_FULL


def test_index30_sigma5_repeat_collapses_to_index5_primitive_key() -> None:
    source = repeat_source_pair(
        SIGMA5_CELL_C4,
        SIGMA5_CELL_C5,
        (2, 0, 0, 3),
    )
    factorization = primitiveize_pair_matrix_2d(source)

    block_a = source[:4]
    block_b = source[4:]
    assert abs(det2(block_a)) == 30
    assert abs(det2(block_b)) == 30
    assert factorization.repeat_index == 6
    assert right_multiply_rank2(
        factorization.primitive_matrix,
        factorization.source_right_factor,
    ) == source
    assert canonicalize_primitive_pair_2d(
        factorization.primitive_matrix,
        point_group=FULL_SQUARE_GROUP,
    ) == SIGMA5_PAIR_KEY_FULL
