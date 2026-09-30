from __future__ import annotations

from itertools import product

import numpy as np
import pytest

from calm.interface.matching._pair_identity import (
    canonicalize_primitive_pair_2d,
    restrict_surface_group_for_pair_identity,
)
from calm.interface.matching._types import PairIdentityPolicy2D
from reference.coupled_match_reference import (
    FULL_SQUARE_GROUP,
    IDENTITY_PAIR_KEY_FULL,
    PROPER_SQUARE_GROUP,
    SIGMA5_CELL_C4,
    SIGMA5_CELL_C5,
    SIGMA5_PAIR_KEY_FULL,
    canonicalize_primitive_pair_2d as reference_pair_key,
    matrix4x2,
)

IDENTITY = np.eye(2, dtype=int)
SHEAR = np.array([[1, 1], [0, 1]], dtype=int)
REFLECTION = np.array([[1, 0], [0, -1]], dtype=int)


def _array(matrix: tuple[int, int, int, int]) -> np.ndarray:
    return np.asarray(matrix, dtype=int).reshape(2, 2)


def _group(
    matrices: tuple[tuple[int, int, int, int], ...],
) -> tuple[np.ndarray, ...]:
    return tuple(_array(matrix) for matrix in matrices)


def _stack(block_a: np.ndarray, block_b: np.ndarray) -> np.ndarray:
    return np.vstack([block_a, block_b])


def _policy(
    *,
    symmetry: str = "full",
    exchange: bool = False,
) -> PairIdentityPolicy2D:
    return PairIdentityPolicy2D(
        pair_symmetry=symmetry,
        correspondence_orientation="proper",
        identify_material_exchange=exchange,
    )


def _canonicalize(
    matrix: np.ndarray,
    *,
    symmetry: str = "full",
    exchange: bool = False,
    group_a: tuple[np.ndarray, ...] | None = None,
    group_b: tuple[np.ndarray, ...] | None = None,
):
    group = _group(FULL_SQUARE_GROUP)
    return canonicalize_primitive_pair_2d(
        matrix,
        point_group_A=group if group_a is None else group_a,
        point_group_B=group if group_b is None else group_b,
        policy=_policy(symmetry=symmetry, exchange=exchange),
    )


def test_restrict_surface_group_separates_proper_and_full_operations() -> None:
    full_input = tuple(reversed(_group(FULL_SQUARE_GROUP))) + (IDENTITY.copy(),)

    full = restrict_surface_group_for_pair_identity(full_input, "full")
    proper = restrict_surface_group_for_pair_identity(full_input, "proper")

    assert len(full) == 8
    assert len(proper) == 4
    assert all(round(np.linalg.det(operation)) == 1 for operation in proper)
    assert [tuple(operation.ravel()) for operation in full] == sorted(
        tuple(operation.ravel()) for operation in full
    )


def test_common_right_change_preserves_pair_key() -> None:
    primitive = _stack(IDENTITY, SHEAR)
    common_right = np.array([[2, 1], [1, 1]], dtype=int)

    original = _canonicalize(primitive)
    transformed = _canonicalize(primitive @ common_right)

    assert transformed.key == original.key


def test_independent_right_change_generally_changes_pair_key() -> None:
    primitive = _stack(IDENTITY, IDENTITY)
    independently_changed = _stack(IDENTITY, SHEAR)
    identity_group = (IDENTITY,)

    original = _canonicalize(
        primitive,
        group_a=identity_group,
        group_b=identity_group,
    )
    changed = _canonicalize(
        independently_changed,
        group_a=identity_group,
        group_b=identity_group,
    )

    assert changed.key != original.key


def test_independent_admitted_left_operations_preserve_pair_key() -> None:
    primitive = _stack(IDENTITY, SHEAR)
    group = _group(FULL_SQUARE_GROUP)
    operation_a = group[2]
    operation_b = group[5]
    transformed = _stack(operation_a @ IDENTITY, operation_b @ SHEAR)

    assert _canonicalize(transformed).key == _canonicalize(primitive).key


def test_full_symmetry_identifies_reflection_but_proper_does_not() -> None:
    primitive = _stack(_array(SIGMA5_CELL_C4), _array(SIGMA5_CELL_C5))
    reflected = _stack(REFLECTION @ primitive[:2], primitive[2:])

    assert _canonicalize(reflected, symmetry="full").key == _canonicalize(
        primitive,
        symmetry="full",
    ).key
    assert _canonicalize(reflected, symmetry="proper").key != _canonicalize(
        primitive,
        symmetry="proper",
    ).key


def test_material_exchange_is_merged_only_when_enabled() -> None:
    primitive = _stack(IDENTITY, SHEAR)
    swapped = _stack(SHEAR, IDENTITY)
    identity_group = (IDENTITY,)

    ordered_a = _canonicalize(
        primitive,
        exchange=False,
        group_a=identity_group,
        group_b=identity_group,
    )
    ordered_b = _canonicalize(
        swapped,
        exchange=False,
        group_a=identity_group,
        group_b=identity_group,
    )
    exchanged_a = _canonicalize(
        primitive,
        exchange=True,
        group_a=identity_group,
        group_b=identity_group,
    )
    exchanged_b = _canonicalize(
        swapped,
        exchange=True,
        group_a=identity_group,
        group_b=identity_group,
    )

    assert ordered_a.key != ordered_b.key
    assert not ordered_a.material_exchange_applied
    assert exchanged_a.key == exchanged_b.key
    assert not exchanged_a.material_exchange_applied
    assert exchanged_b.material_exchange_applied

    transformed = _stack(
        exchanged_b.point_operation_B @ swapped[2:],
        exchanged_b.point_operation_A @ swapped[:2],
    )
    assert np.array_equal(
        transformed @ exchanged_b.common_right_transform,
        exchanged_b.canonical_matrix,
    )


def test_sigma5_pair_is_distinct_from_identity_under_full_d4() -> None:
    identity = _canonicalize(_stack(IDENTITY, IDENTITY), symmetry="full")
    sigma5 = _canonicalize(
        _stack(_array(SIGMA5_CELL_C4), _array(SIGMA5_CELL_C5)),
        symmetry="full",
    )

    assert identity.key == IDENTITY_PAIR_KEY_FULL
    assert sigma5.key == SIGMA5_PAIR_KEY_FULL
    assert sigma5.key != identity.key


def test_canonicalization_returns_exact_reconstruction_witnesses() -> None:
    primitive = _stack(_array(SIGMA5_CELL_C4), _array(SIGMA5_CELL_C5))
    result = _canonicalize(primitive, symmetry="proper")

    transformed = _stack(
        result.point_operation_A @ primitive[:2],
        result.point_operation_B @ primitive[2:],
    )
    reconstructed = transformed @ result.common_right_transform

    assert np.array_equal(reconstructed, result.canonical_matrix)
    assert tuple(int(value) for value in reconstructed.ravel()) == result.key
    assert abs(round(np.linalg.det(result.common_right_transform))) == 1


def test_result_is_idempotent_and_group_order_independent() -> None:
    primitive = _stack(_array(SIGMA5_CELL_C4), _array(SIGMA5_CELL_C5))
    group = _group(FULL_SQUARE_GROUP)

    original = canonicalize_primitive_pair_2d(
        primitive,
        point_group_A=group,
        point_group_B=group,
        policy=_policy(symmetry="full"),
    )
    reordered = canonicalize_primitive_pair_2d(
        primitive,
        point_group_A=tuple(reversed(group)),
        point_group_B=tuple(reversed(group)),
        policy=_policy(symmetry="full"),
    )
    repeated = canonicalize_primitive_pair_2d(
        original.canonical_matrix,
        point_group_A=group,
        point_group_B=group,
        policy=_policy(symmetry="full"),
    )

    assert reordered.key == original.key
    assert repeated.key == original.key


@pytest.mark.parametrize("symmetry", ["proper", "full"])
def test_production_keys_match_slow_reference_on_small_unimodular_pairs(
    symmetry: str,
) -> None:
    reference_group = (
        PROPER_SQUARE_GROUP if symmetry == "proper" else FULL_SQUARE_GROUP
    )
    production_group = _group(FULL_SQUARE_GROUP)
    lower_blocks = (
        IDENTITY,
        SHEAR,
        np.array([[1, -1], [1, 0]], dtype=int),
        np.array([[0, -1], [1, 2]], dtype=int),
    )

    for left_operation, lower in product(production_group[:4], lower_blocks):
        primitive = _stack(left_operation, lower)
        production = _canonicalize(primitive, symmetry=symmetry)
        reference = reference_pair_key(
            matrix4x2(primitive.tolist()),
            point_group=reference_group,
        )
        assert production.key == reference


def test_nonprimitive_pair_is_rejected() -> None:
    repeated = _stack(2 * IDENTITY, 2 * IDENTITY)

    with pytest.raises(ValueError, match="must be saturated"):
        _canonicalize(repeated)


def test_invalid_policy_and_group_inputs_are_rejected() -> None:
    with pytest.raises(ValueError, match="pair_symmetry"):
        PairIdentityPolicy2D(
            pair_symmetry="invalid",
            correspondence_orientation="proper",
            identify_material_exchange=False,
        )
    with pytest.raises(ValueError, match="correspondence_orientation"):
        PairIdentityPolicy2D(
            pair_symmetry="full",
            correspondence_orientation="invalid",
            identify_material_exchange=False,
        )
    with pytest.raises(ValueError, match="nonempty"):
        restrict_surface_group_for_pair_identity((), "full")
    with pytest.raises(ValueError, match="unimodular"):
        restrict_surface_group_for_pair_identity(
            (np.array([[2, 0], [0, 1]], dtype=int),),
            "full",
        )


def test_search_scoped_context_matches_public_and_isolates_witness_arrays() -> None:
    from calm.interface.matching._pair_identity import (
        _canonicalize_primitive_pair_tuple_2d,
        _prepare_pair_identity_context_2d,
    )

    primitive = _stack(_array(SIGMA5_CELL_C4), _array(SIGMA5_CELL_C5))
    group = _group(FULL_SQUARE_GROUP)
    policy = _policy(symmetry="full")
    context = _prepare_pair_identity_context_2d(
        point_group_A=group,
        point_group_B=tuple(reversed(group)),
        policy=policy,
    )
    source = tuple(int(value) for value in primitive.ravel())

    first = _canonicalize_primitive_pair_tuple_2d(source, context=context)
    second = _canonicalize_primitive_pair_tuple_2d(source, context=context)
    public = canonicalize_primitive_pair_2d(
        primitive,
        point_group_A=group,
        point_group_B=group,
        policy=policy,
    )

    assert first.key == second.key == public.key
    assert np.array_equal(first.canonical_matrix, public.canonical_matrix)
    assert np.array_equal(
        first.common_right_transform,
        public.common_right_transform,
    )

    original_second_a = second.point_operation_A.copy()
    original_second_b = second.point_operation_B.copy()
    first.point_operation_A[0, 0] += 17
    first.point_operation_B[0, 0] -= 13
    assert np.array_equal(second.point_operation_A, original_second_a)
    assert np.array_equal(second.point_operation_B, original_second_b)
