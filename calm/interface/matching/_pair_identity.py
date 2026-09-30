"""Exact primitive coupled-pair identity for the coupled-v2 matcher.

The final equivalence relation is

``M' = diag(P_A, P_B) M U``,

where the admitted parent-surface operations act independently on the two
blocks and one common right unimodular basis change acts on both blocks.
Optional material exchange is a separate, explicit policy.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import numpy as np

from calm.math2d._exact_rank2 import (
    Matrix2Tuple,
    Matrix4x2Tuple,
    det2_tuple,
    exact_matrix2_tuple,
    exact_matrix4x2_tuple,
    left_multiply2_tuple,
    tuple_to_int_array,
)
from calm.math2d.paired_lattice import (
    _canonicalize_common_right_rank2_tuple,
    _determinantal_divisor_tuple,
)

from calm.interface.config import PairSymmetryPolicy
from calm.interface.matching._types import PairCanonicalization2D, PairIdentityPolicy2D


def _matrix_key(matrix: np.ndarray) -> Matrix2Tuple:
    return exact_matrix2_tuple(matrix, name="matrix")


def _validate_group(
    operations: Sequence[np.ndarray],
    *,
    name: str,
) -> tuple[np.ndarray, ...]:
    if not operations:
        raise ValueError(f"{name} must be nonempty")

    unique: dict[Matrix2Tuple, np.ndarray] = {}
    for index, operation in enumerate(operations):
        key = exact_matrix2_tuple(operation, name=f"{name}[{index}]")
        if det2_tuple(key) not in {-1, 1}:
            raise ValueError(f"{name}[{index}] must be unimodular")
        unique[key] = tuple_to_int_array(
            key,
            shape=(2, 2),
            name=f"{name}[{index}]",
        )
    return tuple(unique[key] for key in sorted(unique))


def restrict_surface_group_for_pair_identity(
    operations: Sequence[np.ndarray],
    policy: PairSymmetryPolicy,
) -> tuple[np.ndarray, ...]:
    """Return deterministic admitted operations for one pair-identity policy."""
    if policy not in {"proper", "full"}:
        raise ValueError("policy must be 'proper' or 'full'")

    group = _validate_group(operations, name="operations")
    if policy == "full":
        return tuple(np.asarray(operation, dtype=np.int_) for operation in group)

    proper = tuple(
        np.asarray(operation, dtype=np.int_)
        for operation in group
        if det2_tuple(_matrix_key(operation)) == 1
    )
    if not proper:
        raise ValueError("proper pair identity requires a determinant +1 operation")
    return proper


@dataclass(frozen=True)
class _PairIdentityContext2D:
    """Validated search-scoped state for primitive-pair canonicalization."""

    group_a_items: tuple[tuple[Matrix2Tuple, np.ndarray], ...]
    group_b_items: tuple[tuple[Matrix2Tuple, np.ndarray], ...]
    exchange_modes: tuple[bool, ...]


def _prepare_pair_identity_context_2d(
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
    policy: PairIdentityPolicy2D,
) -> _PairIdentityContext2D:
    """Validate pair-identity policy and point groups once per search."""

    if not isinstance(policy, PairIdentityPolicy2D):
        raise TypeError("policy must be a PairIdentityPolicy2D")
    group_a = restrict_surface_group_for_pair_identity(
        point_group_A,
        policy.pair_symmetry,
    )
    group_b = restrict_surface_group_for_pair_identity(
        point_group_B,
        policy.pair_symmetry,
    )
    return _PairIdentityContext2D(
        group_a_items=tuple(
            (_matrix_key(operation), operation) for operation in group_a
        ),
        group_b_items=tuple(
            (_matrix_key(operation), operation) for operation in group_b
        ),
        exchange_modes=(False, True) if policy.identify_material_exchange else (False,),
    )


def _candidate_canonicalization(
    block_a: Matrix2Tuple,
    block_b: Matrix2Tuple,
    operation_a: Matrix2Tuple,
    operation_b: Matrix2Tuple,
) -> tuple[Matrix4x2Tuple, Matrix2Tuple, tuple[int, int]]:
    transformed = cast(
        Matrix4x2Tuple,
        left_multiply2_tuple(operation_a, block_a)
        + left_multiply2_tuple(operation_b, block_b),
    )
    canonicalization = _canonicalize_common_right_rank2_tuple(transformed)
    return (
        canonicalization.key,
        canonicalization.right_transform,
        canonicalization.pivot_rows,
    )


def _canonicalize_primitive_pair_tuple_2d(
    source: Matrix4x2Tuple,
    *,
    context: _PairIdentityContext2D,
) -> PairCanonicalization2D:
    """Canonicalize one validated tuple using search-scoped group state."""

    if _determinantal_divisor_tuple(source) != 1:
        raise ValueError("primitive_matrix must be saturated")

    block_a = cast(Matrix2Tuple, source[:4])
    block_b = cast(Matrix2Tuple, source[4:])

    best_rank: tuple[object, ...] | None = None
    best_key: Matrix4x2Tuple | None = None
    best_operation_a: np.ndarray | None = None
    best_operation_b: np.ndarray | None = None
    best_right: Matrix2Tuple | None = None
    best_pivot: tuple[int, int] | None = None
    best_exchanged = False

    for exchanged in context.exchange_modes:
        first_block, second_block = (
            (block_b, block_a) if exchanged else (block_a, block_b)
        )
        for operation_a_key, operation_a in context.group_a_items:
            for operation_b_key, operation_b in context.group_b_items:
                if exchanged:
                    key, right, pivot = _candidate_canonicalization(
                        first_block,
                        second_block,
                        operation_b_key,
                        operation_a_key,
                    )
                else:
                    key, right, pivot = _candidate_canonicalization(
                        first_block,
                        second_block,
                        operation_a_key,
                        operation_b_key,
                    )

                rank = (
                    key,
                    exchanged,
                    operation_a_key,
                    operation_b_key,
                    right,
                    pivot,
                )
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best_key = key
                    best_operation_a = operation_a
                    best_operation_b = operation_b
                    best_right = right
                    best_pivot = pivot
                    best_exchanged = exchanged

    if (
        best_key is None
        or best_operation_a is None
        or best_operation_b is None
        or best_right is None
        or best_pivot is None
    ):
        raise RuntimeError("pair canonicalization produced no candidates")

    return PairCanonicalization2D(
        key=best_key,
        canonical_matrix=tuple_to_int_array(
            best_key,
            shape=(4, 2),
            name="canonicalize_primitive_pair_2d(canonical_matrix)",
        ),
        point_operation_A=np.array(best_operation_a, dtype=np.int_, copy=True),
        point_operation_B=np.array(best_operation_b, dtype=np.int_, copy=True),
        common_right_transform=tuple_to_int_array(
            best_right,
            shape=(2, 2),
            name="canonicalize_primitive_pair_2d(common_right_transform)",
        ),
        pivot_rows=best_pivot,
        material_exchange_applied=best_exchanged,
    )


def canonicalize_primitive_pair_2d(
    primitive_matrix: np.ndarray,
    *,
    point_group_A: Sequence[np.ndarray],
    point_group_B: Sequence[np.ndarray],
    policy: PairIdentityPolicy2D,
) -> PairCanonicalization2D:
    """Canonicalize one primitive coupled pair under the declared equivalence."""

    source_array = np.asarray(primitive_matrix)
    if source_array.shape != (4, 2):
        raise ValueError("primitive_matrix must have shape (4, 2)")
    source = exact_matrix4x2_tuple(source_array, name="primitive_matrix")
    context = _prepare_pair_identity_context_2d(
        point_group_A=point_group_A,
        point_group_B=point_group_B,
        policy=policy,
    )
    return _canonicalize_primitive_pair_tuple_2d(source, context=context)


__all__ = [
    "PairSymmetryPolicy",
    "canonicalize_primitive_pair_2d",
    "restrict_surface_group_for_pair_identity",
]
