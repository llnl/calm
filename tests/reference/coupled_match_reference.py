"""Exact slow reference for coupled two-dimensional lattice matching.

This module deliberately uses only the Python standard library.  It is not a
production implementation.  Its purpose is to freeze small exact oracles before
CALM's coupled-match migration changes the optimized matching pipeline.

Matrices are stored as row-major tuples:

* ``Matrix2`` has four entries and represents a 2 x 2 matrix;
* ``Matrix4x2`` has eight entries and represents a 4 x 2 stacked pair matrix.

The reference equivalence is

    M' = diag(P_A, P_B) M U,

where ``P_A`` and ``P_B`` are independently selected square-lattice point-group
operations and ``U`` is one common right unimodular basis change.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import gcd, isqrt
from numbers import Integral
from typing import Iterable, Literal, Sequence

Matrix2 = tuple[int, int, int, int]
Matrix4x2 = tuple[int, int, int, int, int, int, int, int]
PairSymmetry = Literal["full", "proper"]

IDENTITY_2D: Matrix2 = (1, 0, 0, 1)
ROTATION_90_2D: Matrix2 = (0, -1, 1, 0)

# Two determinant-five square coincidence cells of opposite handedness.
SIGMA5_CELL_C4: Matrix2 = (2, -1, 1, 2)
SIGMA5_CELL_C5: Matrix2 = (2, 1, -1, 2)

IDENTITY_PAIR_KEY_FULL: Matrix4x2 = (-1, 0, 0, -1, 1, 0, 0, 1)
SIGMA5_PAIR_KEY_FULL: Matrix4x2 = (-4, -3, -3, -1, 5, 3, 0, 1)
SIGMA5_PAIR_KEYS_PROPER: tuple[Matrix4x2, Matrix4x2] = (
    (-4, -3, 3, 1, 0, 1, -5, -3),
    (-4, -1, -3, -2, 5, 2, 0, 1),
)

FULL_D4_DISCOVERY_BY_INDEX: tuple[tuple[int, Matrix4x2], ...] = (
    (1, IDENTITY_PAIR_KEY_FULL),
    (5, SIGMA5_PAIR_KEY_FULL),
    (13, (-12, -7, -5, -4, 13, 8, 0, 1)),
    (17, (-15, -11, -8, -7, 17, 13, 0, 1)),
    (25, (-24, -17, -7, -6, 25, 18, 0, 1)),
    (29, (-21, -13, -20, -11, 29, 17, 0, 1)),
)


def _exact_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an exact integer.")
    return int(value)


def matrix2(value: Sequence[object] | Sequence[Sequence[object]]) -> Matrix2:
    """Return one exact row-major 2 x 2 matrix tuple."""
    if len(value) == 2 and all(hasattr(row, "__len__") for row in value):
        rows = value  # type: ignore[assignment]
        if any(len(row) != 2 for row in rows):  # type: ignore[arg-type]
            raise ValueError("matrix must have shape (2, 2).")
        flat = [entry for row in rows for entry in row]  # type: ignore[union-attr]
    else:
        flat = list(value)  # type: ignore[arg-type]
    if len(flat) != 4:
        raise ValueError("matrix must contain four entries.")
    return tuple(
        _exact_int(entry, name=f"matrix[{index}]")
        for index, entry in enumerate(flat)
    )  # type: ignore[return-value]


def matrix4x2(
    value: Sequence[object] | Sequence[Sequence[object]],
) -> Matrix4x2:
    """Return one exact row-major 4 x 2 matrix tuple."""
    if len(value) == 4 and all(hasattr(row, "__len__") for row in value):
        rows = value  # type: ignore[assignment]
        if any(len(row) != 2 for row in rows):  # type: ignore[arg-type]
            raise ValueError("matrix must have shape (4, 2).")
        flat = [entry for row in rows for entry in row]  # type: ignore[union-attr]
    else:
        flat = list(value)  # type: ignore[arg-type]
    if len(flat) != 8:
        raise ValueError("matrix must contain eight entries.")
    return tuple(
        _exact_int(entry, name=f"matrix[{index}]")
        for index, entry in enumerate(flat)
    )  # type: ignore[return-value]


def det2(matrix: Matrix2) -> int:
    """Return the exact determinant of a 2 x 2 matrix."""
    a, b, c, d = matrix
    return a * d - b * c


def multiply2(left: Matrix2, right: Matrix2) -> Matrix2:
    """Return the exact product of two 2 x 2 matrices."""
    a, b, c, d = left
    e, f, g, h = right
    return (
        a * e + b * g,
        a * f + b * h,
        c * e + d * g,
        c * f + d * h,
    )


def stack_pair(block_a: Matrix2, block_b: Matrix2) -> Matrix4x2:
    """Stack two exact 2 x 2 integer maps into one 4 x 2 pair matrix."""
    return block_a + block_b  # type: ignore[return-value]


def split_pair(matrix: Matrix4x2) -> tuple[Matrix2, Matrix2]:
    """Return the A and B 2 x 2 blocks of one pair matrix."""
    return matrix[:4], matrix[4:]  # type: ignore[return-value]


def right_multiply_rank2(matrix: Matrix4x2, transform: Matrix2) -> Matrix4x2:
    """Apply one common exact right transform to every row of a 4 x 2 matrix."""
    a, b, c, d = transform
    output: list[int] = []
    for index in range(0, 8, 2):
        x, y = matrix[index], matrix[index + 1]
        output.extend((x * a + y * c, x * b + y * d))
    return tuple(output)  # type: ignore[return-value]


def _extended_gcd(a: int, b: int) -> tuple[int, int, int]:
    old_r, r = abs(a), abs(b)
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        quotient = old_r // r
        old_r, r = r, old_r - quotient * r
        old_s, s = s, old_s - quotient * s
        old_t, t = t, old_t - quotient * t
    if a < 0:
        old_s = -old_s
    if b < 0:
        old_t = -old_t
    return old_r, old_s, old_t


@dataclass(frozen=True)
class HNFWithTransformReference:
    """Canonical column HNF and its exact right unimodular witness."""

    hnf: Matrix2
    right_transform: Matrix2


def hnf2_col_with_transform(matrix: Matrix2) -> HNFWithTransformReference:
    """Return ``H, U`` with ``H = matrix @ U`` in canonical column HNF."""
    if det2(matrix) == 0:
        raise ValueError("column HNF requires a full-rank matrix.")

    a, b, c, d = matrix
    common = gcd(c, d)
    if common == 0:
        raise ValueError("unexpected zero gcd for a full-rank matrix.")
    bezout_gcd, x, y = _extended_gcd(c, d)
    if bezout_gcd != common:
        raise AssertionError("Bezout witness does not match the gcd.")

    transform: Matrix2 = (d // common, x, -c // common, y)
    reduced = multiply2(matrix, transform)

    if reduced[3] < 0:
        sign_flip: Matrix2 = (1, 0, 0, -1)
        transform = multiply2(transform, sign_flip)
        reduced = multiply2(reduced, sign_flip)
    if reduced[2] != 0:
        raise AssertionError("column HNF elimination did not zero the lower-left entry.")
    if reduced[0] < 0:
        sign_flip = (-1, 0, 0, 1)
        transform = multiply2(transform, sign_flip)
        reduced = multiply2(reduced, sign_flip)

    h11, h12, _, _h22 = reduced
    quotient = (h12 - (h12 % h11)) // h11
    shear: Matrix2 = (1, -quotient, 0, 1)
    transform = multiply2(transform, shear)
    reduced = multiply2(reduced, shear)

    if multiply2(matrix, transform) != reduced:
        raise AssertionError("column HNF witness failed exact reconstruction.")
    if abs(det2(transform)) != 1:
        raise AssertionError("column HNF witness is not unimodular.")
    if not (
        reduced[0] > 0
        and reduced[3] > 0
        and reduced[2] == 0
        and 0 <= reduced[1] < reduced[0]
    ):
        raise AssertionError("column HNF is not canonical.")
    return HNFWithTransformReference(reduced, transform)


def hnf2_col(matrix: Matrix2) -> Matrix2:
    """Return the canonical exact right/column HNF of one 2 x 2 matrix."""
    return hnf2_col_with_transform(matrix).hnf


def _divisors(index: int) -> tuple[int, ...]:
    values: set[int] = set()
    for divisor in range(1, isqrt(index) + 1):
        if index % divisor == 0:
            values.add(divisor)
            values.add(index // divisor)
    return tuple(sorted(values))


def enumerate_hnf_2d_by_index(index: int) -> tuple[Matrix2, ...]:
    """Enumerate every canonical column HNF of one positive determinant."""
    if isinstance(index, bool) or not isinstance(index, Integral):
        raise TypeError("index must be a positive integer.")
    index_int = int(index)
    if index_int <= 0:
        raise ValueError("index must be a positive integer.")
    return tuple(
        (h11, h12, 0, index_int // h11)
        for h11 in _divisors(index_int)
        for h12 in range(h11)
    )


def enumerate_row_hnf_2d_by_index(index: int) -> tuple[Matrix2, ...]:
    """Enumerate row-HNF representatives of determinant ``index``."""
    return tuple((a, 0, b, d) for a, b, _zero, d in enumerate_hnf_2d_by_index(index))


def _rows4x2(matrix: Matrix4x2) -> tuple[tuple[int, int], ...]:
    return tuple((matrix[index], matrix[index + 1]) for index in range(0, 8, 2))


def maximal_minors_rank2(matrix: Matrix4x2) -> tuple[int, ...]:
    """Return all six exact 2 x 2 row minors of a rank-two 4 x 2 matrix."""
    rows = _rows4x2(matrix)
    return tuple(
        rows[i][0] * rows[j][1] - rows[i][1] * rows[j][0]
        for i, j in combinations(range(4), 2)
    )


def determinantal_divisor_rank2(matrix: Matrix4x2) -> int:
    """Return the gcd of the absolute full-rank row minors."""
    divisor = 0
    for minor in maximal_minors_rank2(matrix):
        divisor = gcd(divisor, abs(minor))
    if divisor == 0:
        raise ValueError("matrix must have rank two.")
    return divisor


def exact_right_divide_rank2(
    matrix: Matrix4x2,
    right_factor: Matrix2,
) -> Matrix4x2 | None:
    """Return exact ``C`` satisfying ``matrix = C @ right_factor`` if integral."""
    determinant = det2(right_factor)
    if determinant == 0:
        raise ValueError("right_factor must be full rank.")
    a, b, c, d = right_factor
    adjugate: Matrix2 = (d, -b, -c, a)
    numerators = right_multiply_rank2(matrix, adjugate)
    if any(value % determinant for value in numerators):
        return None
    return tuple(value // determinant for value in numerators)  # type: ignore[return-value]


@dataclass(frozen=True)
class PrimitivePairFactorizationReference:
    """Exact source-to-primitive factorization for one stacked pair matrix."""

    primitive_matrix: Matrix4x2
    source_right_factor: Matrix2
    repeat_index: int
    maximal_minors: tuple[int, ...]


@lru_cache(maxsize=None)
def primitiveize_pair_matrix_2d(
    matrix: Matrix4x2,
) -> PrimitivePairFactorizationReference:
    """Saturate one 4 x 2 column lattice by exhaustive row-HNF factor search."""
    source_minors = maximal_minors_rank2(matrix)
    repeat_index = determinantal_divisor_rank2(matrix)
    if repeat_index == 1:
        return PrimitivePairFactorizationReference(
            primitive_matrix=matrix,
            source_right_factor=IDENTITY_2D,
            repeat_index=1,
            maximal_minors=source_minors,
        )

    for right_factor in enumerate_row_hnf_2d_by_index(repeat_index):
        primitive = exact_right_divide_rank2(matrix, right_factor)
        if primitive is None:
            continue
        if determinantal_divisor_rank2(primitive) != 1:
            continue
        if right_multiply_rank2(primitive, right_factor) != matrix:
            raise AssertionError("primitive factorization failed exact reconstruction.")
        if abs(det2(right_factor)) != repeat_index:
            raise AssertionError("right-factor determinant does not equal repeat index.")
        return PrimitivePairFactorizationReference(
            primitive_matrix=primitive,
            source_right_factor=right_factor,
            repeat_index=repeat_index,
            maximal_minors=source_minors,
        )
    raise AssertionError("no exact primitive factorization was found.")


@dataclass(frozen=True)
class CommonRightCanonicalizationReference:
    """Exact canonical representative under one common right GL(2, Z) action."""

    canonical_matrix: Matrix4x2
    right_transform: Matrix2
    pivot_rows: tuple[int, int]
    key: Matrix4x2


@lru_cache(maxsize=None)
def canonicalize_common_right_rank2(
    matrix: Matrix4x2,
) -> CommonRightCanonicalizationReference:
    """Canonicalize a rank-two 4 x 2 matrix under right unimodular changes."""
    rows = _rows4x2(matrix)
    best: CommonRightCanonicalizationReference | None = None
    for first, second in combinations(range(4), 2):
        pivot: Matrix2 = (
            rows[first][0],
            rows[first][1],
            rows[second][0],
            rows[second][1],
        )
        if det2(pivot) == 0:
            continue
        hnf_result = hnf2_col_with_transform(pivot)
        canonical = right_multiply_rank2(matrix, hnf_result.right_transform)
        candidate = CommonRightCanonicalizationReference(
            canonical_matrix=canonical,
            right_transform=hnf_result.right_transform,
            pivot_rows=(first, second),
            key=canonical,
        )
        if best is None or candidate.key < best.key:
            best = candidate
    if best is None:
        raise ValueError("matrix must have rank two.")
    return best


def _square_groups() -> tuple[tuple[Matrix2, ...], tuple[Matrix2, ...]]:
    proper: list[Matrix2] = []
    operation = IDENTITY_2D
    for _ in range(4):
        proper.append(operation)
        operation = multiply2(operation, ROTATION_90_2D)
    full = proper + [
        (1, 0, 0, -1),
        (-1, 0, 0, 1),
        (0, 1, 1, 0),
        (0, -1, -1, 0),
    ]
    return tuple(sorted(set(proper))), tuple(sorted(set(full)))


PROPER_SQUARE_GROUP, FULL_SQUARE_GROUP = _square_groups()


@lru_cache(maxsize=None)
def _canonicalize_pair_from_common_right_key(
    common_right_key: Matrix4x2,
    point_group: tuple[Matrix2, ...],
) -> Matrix4x2:
    block_a, block_b = split_pair(common_right_key)
    best: Matrix4x2 | None = None
    for operation_a in point_group:
        transformed_a = multiply2(operation_a, block_a)
        for operation_b in point_group:
            transformed = stack_pair(
                transformed_a,
                multiply2(operation_b, block_b),
            )
            key = canonicalize_common_right_rank2(transformed).key
            if best is None or key < best:
                best = key
    if best is None:
        raise AssertionError("point group must be nonempty.")
    return best


def canonicalize_primitive_pair_2d(
    matrix: Matrix4x2,
    *,
    point_group: Sequence[Matrix2],
) -> Matrix4x2:
    """Return the exact pair key under independent left and common-right actions."""
    group = tuple(point_group)
    if not group:
        raise ValueError("point_group must be nonempty.")
    common_key = canonicalize_common_right_rank2(matrix).key
    return _canonicalize_pair_from_common_right_key(common_key, group)


def _surface_orbit_key(
    matrix: Matrix2,
    operations: Sequence[Matrix2],
) -> Matrix2:
    return min(hnf2_col(multiply2(operation, matrix)) for operation in operations)


def _gram(matrix: Matrix2) -> Matrix2:
    a, b, c, d = matrix
    return (
        a * a + c * c,
        a * b + c * d,
        a * b + c * d,
        b * b + d * d,
    )


def _quadratic_form(metric: Matrix2, vector: tuple[int, int]) -> int:
    a, b, _c, d = metric
    x, y = vector
    return a * x * x + 2 * b * x * y + d * y * y


def _bilinear_form(
    metric: Matrix2,
    left: tuple[int, int],
    right: tuple[int, int],
) -> int:
    a, b, _c, d = metric
    x, y = left
    s, t = right
    return x * (a * s + b * t) + y * (b * s + d * t)


@lru_cache(maxsize=None)
def _vectors_with_norm(
    metric: Matrix2,
    target: int,
) -> tuple[tuple[int, int], ...]:
    determinant = det2(metric)
    if determinant <= 0:
        raise ValueError("metric must be positive definite.")
    x_bound = isqrt((target * metric[3]) // determinant)
    y_bound = isqrt((target * metric[0]) // determinant)
    return tuple(
        (x, y)
        for x in range(-x_bound, x_bound + 1)
        for y in range(-y_bound, y_bound + 1)
        if _quadratic_form(metric, (x, y)) == target
    )


@lru_cache(maxsize=None)
def enumerate_exact_proper_correspondences(
    matrix_a: Matrix2,
    matrix_b: Matrix2,
) -> tuple[Matrix2, ...]:
    """Enumerate all determinant-+1 basis maps preserving the two exact Grams."""
    metric_a = _gram(matrix_a)
    metric_b = _gram(matrix_b)
    correspondences: set[Matrix2] = set()
    for first_column in _vectors_with_norm(metric_b, metric_a[0]):
        for second_column in _vectors_with_norm(metric_b, metric_a[3]):
            if (
                _bilinear_form(metric_b, first_column, second_column)
                != metric_a[1]
            ):
                continue
            transform: Matrix2 = (
                first_column[0],
                second_column[0],
                first_column[1],
                second_column[1],
            )
            if det2(transform) == 1:
                correspondences.add(transform)
    return tuple(sorted(correspondences))


@dataclass(frozen=True)
class CoupledSourceStateReference:
    """One exact equal-square source member/correspondence state."""

    index: int
    source_hnf_a: Matrix2
    source_hnf_b: Matrix2
    correspondence_u_b: Matrix2
    source_pair_matrix: Matrix4x2
    factorization: PrimitivePairFactorizationReference
    full_pair_key: Matrix4x2
    proper_pair_key: Matrix4x2


@dataclass(frozen=True)
class EqualSquareIndexOracleReference:
    """Exact stage counts and primitive classes for one equal-square index."""

    index: int
    hnfs: tuple[Matrix2, ...]
    surface_orbits: tuple[tuple[Matrix2, tuple[Matrix2, ...]], ...]
    raw_member_pairs: int
    orbit_pair_schedules: int
    shape_compatible_orbit_pairs: int
    member_pairs_expanded: int
    correspondence_states: int
    full_pair_keys: frozenset[Matrix4x2]
    proper_pair_keys: frozenset[Matrix4x2]
    states: tuple[CoupledSourceStateReference, ...]


def equal_square_index_oracle(
    index: int,
    *,
    hnf_order: Literal["forward", "reverse"] = "forward",
    comparison_group: Sequence[Matrix2] = FULL_SQUARE_GROUP,
    full_pair_group: Sequence[Matrix2] = FULL_SQUARE_GROUP,
    proper_pair_group: Sequence[Matrix2] = PROPER_SQUARE_GROUP,
) -> EqualSquareIndexOracleReference:
    """Return the exact equal-square coupled-match oracle for one index."""
    hnfs = list(enumerate_hnf_2d_by_index(index))
    if hnf_order == "reverse":
        hnfs.reverse()
    elif hnf_order != "forward":
        raise ValueError("hnf_order must be 'forward' or 'reverse'.")

    comparison_operations = tuple(comparison_group)
    if not comparison_operations:
        raise ValueError("comparison_group must be nonempty.")
    bundles: dict[Matrix2, list[Matrix2]] = {}
    for hnf_matrix in hnfs:
        key = _surface_orbit_key(hnf_matrix, comparison_operations)
        bundles.setdefault(key, []).append(hnf_matrix)
    orbit_items = tuple(
        (key, tuple(sorted(members)))
        for key, members in sorted(bundles.items())
    )

    compatible_orbit_pairs = 0
    expanded_member_pairs = 0
    states: list[CoupledSourceStateReference] = []
    for _key_a, members_a in orbit_items:
        for _key_b, members_b in orbit_items:
            orbit_has_state = False
            for hnf_a in members_a:
                for hnf_b in members_b:
                    correspondences = enumerate_exact_proper_correspondences(
                        hnf_a,
                        hnf_b,
                    )
                    if not correspondences:
                        continue
                    orbit_has_state = True
                    expanded_member_pairs += 1
                    for correspondence in correspondences:
                        source_pair = stack_pair(
                            hnf_a,
                            multiply2(hnf_b, correspondence),
                        )
                        factorization = primitiveize_pair_matrix_2d(source_pair)
                        primitive = factorization.primitive_matrix
                        states.append(
                            CoupledSourceStateReference(
                                index=int(index),
                                source_hnf_a=hnf_a,
                                source_hnf_b=hnf_b,
                                correspondence_u_b=correspondence,
                                source_pair_matrix=source_pair,
                                factorization=factorization,
                                full_pair_key=canonicalize_primitive_pair_2d(
                                    primitive,
                                    point_group=tuple(full_pair_group),
                                ),
                                proper_pair_key=canonicalize_primitive_pair_2d(
                                    primitive,
                                    point_group=tuple(proper_pair_group),
                                ),
                            )
                        )
            if orbit_has_state:
                compatible_orbit_pairs += 1

    return EqualSquareIndexOracleReference(
        index=int(index),
        hnfs=tuple(hnfs),
        surface_orbits=orbit_items,
        raw_member_pairs=len(hnfs) ** 2,
        orbit_pair_schedules=len(orbit_items) ** 2,
        shape_compatible_orbit_pairs=compatible_orbit_pairs,
        member_pairs_expanded=expanded_member_pairs,
        correspondence_states=len(states),
        full_pair_keys=frozenset(state.full_pair_key for state in states),
        proper_pair_keys=frozenset(state.proper_pair_key for state in states),
        states=tuple(states),
    )


@dataclass(frozen=True)
class CumulativeSquareClassInventoryReference:
    """Primitive class inventory accumulated through a finite HNF index bound."""

    k_max: int
    pair_symmetry: PairSymmetry
    key_sets_by_bound: tuple[frozenset[Matrix4x2], ...]
    first_discovery: tuple[tuple[Matrix4x2, int], ...]
    repeat_indices_by_key: tuple[tuple[Matrix4x2, tuple[int, ...]], ...]


def cumulative_equal_square_class_inventory(
    k_max: int,
    *,
    pair_symmetry: PairSymmetry = "full",
    hnf_order: Literal["forward", "reverse"] = "forward",
    comparison_group: Sequence[Matrix2] = FULL_SQUARE_GROUP,
    pair_group: Sequence[Matrix2] | None = None,
) -> CumulativeSquareClassInventoryReference:
    """Accumulate exact primitive pair classes through ``k_max``."""
    if pair_symmetry not in {"full", "proper"}:
        raise ValueError("pair_symmetry must be 'full' or 'proper'.")
    selected_group = (
        tuple(pair_group)
        if pair_group is not None
        else (FULL_SQUARE_GROUP if pair_symmetry == "full" else PROPER_SQUARE_GROUP)
    )

    seen: set[Matrix4x2] = set()
    first: dict[Matrix4x2, int] = {}
    repeats: dict[Matrix4x2, set[int]] = {}
    key_sets: list[frozenset[Matrix4x2]] = []
    for index in range(1, int(k_max) + 1):
        oracle = equal_square_index_oracle(
            index,
            hnf_order=hnf_order,
            comparison_group=comparison_group,
            full_pair_group=(
                selected_group if pair_symmetry == "full" else FULL_SQUARE_GROUP
            ),
            proper_pair_group=(
                selected_group if pair_symmetry == "proper" else PROPER_SQUARE_GROUP
            ),
        )
        for state in oracle.states:
            key = (
                state.full_pair_key
                if pair_symmetry == "full"
                else state.proper_pair_key
            )
            seen.add(key)
            first.setdefault(key, index)
            repeats.setdefault(key, set()).add(state.factorization.repeat_index)
        key_sets.append(frozenset(seen))

    return CumulativeSquareClassInventoryReference(
        k_max=int(k_max),
        pair_symmetry=pair_symmetry,
        key_sets_by_bound=tuple(key_sets),
        first_discovery=tuple(sorted(first.items(), key=lambda item: (item[1], item[0]))),
        repeat_indices_by_key=tuple(
            (key, tuple(sorted(values)))
            for key, values in sorted(repeats.items())
        ),
    )


def repeat_source_pair(
    primitive_a: Matrix2,
    primitive_b: Matrix2,
    right_factor: Matrix2,
) -> Matrix4x2:
    """Construct one repeated source pair from a primitive coupled pair."""
    return stack_pair(
        multiply2(primitive_a, right_factor),
        multiply2(primitive_b, right_factor),
    )


def operation_order_variants(
    operations: Sequence[Matrix2],
) -> tuple[tuple[Matrix2, ...], ...]:
    """Return deterministic operation-order variants used by oracle tests."""
    original = tuple(operations)
    return original, tuple(reversed(original))


__all__ = [
    "CommonRightCanonicalizationReference",
    "CoupledSourceStateReference",
    "CumulativeSquareClassInventoryReference",
    "EqualSquareIndexOracleReference",
    "FULL_D4_DISCOVERY_BY_INDEX",
    "FULL_SQUARE_GROUP",
    "HNFWithTransformReference",
    "IDENTITY_2D",
    "IDENTITY_PAIR_KEY_FULL",
    "Matrix2",
    "Matrix4x2",
    "PROPER_SQUARE_GROUP",
    "PrimitivePairFactorizationReference",
    "SIGMA5_CELL_C4",
    "SIGMA5_CELL_C5",
    "SIGMA5_PAIR_KEY_FULL",
    "SIGMA5_PAIR_KEYS_PROPER",
    "canonicalize_common_right_rank2",
    "canonicalize_primitive_pair_2d",
    "cumulative_equal_square_class_inventory",
    "det2",
    "determinantal_divisor_rank2",
    "enumerate_exact_proper_correspondences",
    "enumerate_hnf_2d_by_index",
    "enumerate_row_hnf_2d_by_index",
    "equal_square_index_oracle",
    "exact_right_divide_rank2",
    "hnf2_col",
    "hnf2_col_with_transform",
    "matrix2",
    "matrix4x2",
    "maximal_minors_rank2",
    "multiply2",
    "operation_order_variants",
    "primitiveize_pair_matrix_2d",
    "repeat_source_pair",
    "right_multiply_rank2",
    "split_pair",
    "stack_pair",
]
