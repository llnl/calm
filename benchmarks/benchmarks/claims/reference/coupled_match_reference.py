"""Independent exact reference for small coupled 2D lattice-match domains.

This module intentionally uses only the Python standard library. It does not
import CALM production matching, canonicalization, primitiveization, reduction,
or symmetry code. The implementation is exhaustive and intended only for small
finite qualification domains.

Integer basis maps are stored as row-major tuples. Exact lattice metrics are
stored as :class:`fractions.Fraction` tuples and act on integer coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from math import gcd, isqrt, lcm
from numbers import Integral, Rational
from typing import Literal, Sequence

Matrix2 = tuple[int, int, int, int]
Matrix4x2 = tuple[int, int, int, int, int, int, int, int]
Metric2 = tuple[Fraction, Fraction, Fraction, Fraction]
PairSymmetry = Literal["proper", "full"]
CorrespondenceOrientation = Literal["proper", "all"]

IDENTITY_2D: Matrix2 = (1, 0, 0, 1)


def _exact_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an exact integer")
    return int(value)


def matrix2(value: Sequence[object] | Sequence[Sequence[object]]) -> Matrix2:
    """Return one exact row-major 2x2 integer matrix."""
    if len(value) == 2 and all(hasattr(row, "__len__") for row in value):
        rows = value  # type: ignore[assignment]
        if any(len(row) != 2 for row in rows):  # type: ignore[arg-type]
            raise ValueError("matrix must have shape (2, 2)")
        flat = [entry for row in rows for entry in row]  # type: ignore[union-attr]
    else:
        flat = list(value)  # type: ignore[arg-type]
    if len(flat) != 4:
        raise ValueError("matrix must contain four entries")
    return tuple(
        _exact_int(entry, name=f"matrix[{index}]")
        for index, entry in enumerate(flat)
    )  # type: ignore[return-value]


def matrix4x2(value: Sequence[object] | Sequence[Sequence[object]]) -> Matrix4x2:
    """Return one exact row-major 4x2 integer matrix."""
    if len(value) == 4 and all(hasattr(row, "__len__") for row in value):
        rows = value  # type: ignore[assignment]
        if any(len(row) != 2 for row in rows):  # type: ignore[arg-type]
            raise ValueError("matrix must have shape (4, 2)")
        flat = [entry for row in rows for entry in row]  # type: ignore[union-attr]
    else:
        flat = list(value)  # type: ignore[arg-type]
    if len(flat) != 8:
        raise ValueError("matrix must contain eight entries")
    return tuple(
        _exact_int(entry, name=f"matrix[{index}]")
        for index, entry in enumerate(flat)
    )  # type: ignore[return-value]


def _fraction(value: object, *, name: str) -> Fraction:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be rational")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, Integral):
        return Fraction(int(value), 1)
    if isinstance(value, Rational):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"{name} must be an exact rational or fraction string")


def metric2(value: Sequence[object] | Sequence[Sequence[object]]) -> Metric2:
    """Return one exact symmetric positive-definite 2x2 metric."""
    if len(value) == 2 and all(hasattr(row, "__len__") for row in value):
        rows = value  # type: ignore[assignment]
        if any(len(row) != 2 for row in rows):  # type: ignore[arg-type]
            raise ValueError("metric must have shape (2, 2)")
        flat = [entry for row in rows for entry in row]  # type: ignore[union-attr]
    else:
        flat = list(value)  # type: ignore[arg-type]
    if len(flat) != 4:
        raise ValueError("metric must contain four entries")
    output = tuple(
        _fraction(entry, name=f"metric[{index}]")
        for index, entry in enumerate(flat)
    )
    if output[1] != output[2]:
        raise ValueError("metric must be symmetric")
    if output[0] <= 0 or det_metric(output) <= 0:
        raise ValueError("metric must be positive definite")
    return output  # type: ignore[return-value]


def det2(matrix: Matrix2) -> int:
    a, b, c, d = matrix
    return a * d - b * c


def det_metric(metric: Metric2) -> Fraction:
    a, b, c, d = metric
    return a * d - b * c


def multiply2(left: Matrix2, right: Matrix2) -> Matrix2:
    a, b, c, d = left
    e, f, g, h = right
    return (
        a * e + b * g,
        a * f + b * h,
        c * e + d * g,
        c * f + d * h,
    )


def stack_pair(block_a: Matrix2, block_b: Matrix2) -> Matrix4x2:
    return block_a + block_b  # type: ignore[return-value]


def split_pair(matrix: Matrix4x2) -> tuple[Matrix2, Matrix2]:
    return matrix[:4], matrix[4:]  # type: ignore[return-value]


def right_multiply_rank2(matrix: Matrix4x2, transform: Matrix2) -> Matrix4x2:
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
    hnf: Matrix2
    right_transform: Matrix2


def hnf2_col_with_transform(matrix: Matrix2) -> HNFWithTransformReference:
    """Return ``H, U`` with ``H = matrix @ U`` in canonical column HNF."""
    if det2(matrix) == 0:
        raise ValueError("column HNF requires a full-rank matrix")
    a, b, c, d = matrix
    common = gcd(c, d)
    if common == 0:
        raise ValueError("unexpected zero gcd")
    bezout_gcd, x, y = _extended_gcd(c, d)
    if bezout_gcd != common:
        raise AssertionError("Bezout witness mismatch")
    transform: Matrix2 = (d // common, x, -c // common, y)
    reduced = multiply2(matrix, transform)
    if reduced[3] < 0:
        sign_flip: Matrix2 = (1, 0, 0, -1)
        transform = multiply2(transform, sign_flip)
        reduced = multiply2(reduced, sign_flip)
    if reduced[2] != 0:
        raise AssertionError("column HNF elimination failed")
    if reduced[0] < 0:
        sign_flip = (-1, 0, 0, 1)
        transform = multiply2(transform, sign_flip)
        reduced = multiply2(reduced, sign_flip)
    h11, h12, _, _h22 = reduced
    quotient = (h12 - (h12 % h11)) // h11
    shear: Matrix2 = (1, -quotient, 0, 1)
    transform = multiply2(transform, shear)
    reduced = multiply2(reduced, shear)
    if multiply2(matrix, transform) != reduced or abs(det2(transform)) != 1:
        raise AssertionError("column HNF witness failed")
    if not (
        reduced[0] > 0
        and reduced[3] > 0
        and reduced[2] == 0
        and 0 <= reduced[1] < reduced[0]
    ):
        raise AssertionError("column HNF is not canonical")
    return HNFWithTransformReference(reduced, transform)


def _divisors(index: int) -> tuple[int, ...]:
    values: set[int] = set()
    for divisor in range(1, isqrt(index) + 1):
        if index % divisor == 0:
            values.add(divisor)
            values.add(index // divisor)
    return tuple(sorted(values))


def enumerate_hnf_2d_by_index(index: int) -> tuple[Matrix2, ...]:
    if isinstance(index, bool) or not isinstance(index, Integral):
        raise TypeError("index must be a positive integer")
    index_int = int(index)
    if index_int <= 0:
        raise ValueError("index must be a positive integer")
    return tuple(
        (h11, h12, 0, index_int // h11)
        for h11 in _divisors(index_int)
        for h12 in range(h11)
    )


def enumerate_row_hnf_2d_by_index(index: int) -> tuple[Matrix2, ...]:
    return tuple((a, 0, b, d) for a, b, _zero, d in enumerate_hnf_2d_by_index(index))


def _rows4x2(matrix: Matrix4x2) -> tuple[tuple[int, int], ...]:
    return tuple((matrix[index], matrix[index + 1]) for index in range(0, 8, 2))


def maximal_minors_rank2(matrix: Matrix4x2) -> tuple[int, ...]:
    rows = _rows4x2(matrix)
    return tuple(
        rows[i][0] * rows[j][1] - rows[i][1] * rows[j][0]
        for i, j in combinations(range(4), 2)
    )


def determinantal_divisor_rank2(matrix: Matrix4x2) -> int:
    divisor = 0
    for minor in maximal_minors_rank2(matrix):
        divisor = gcd(divisor, abs(minor))
    if divisor == 0:
        raise ValueError("matrix must have rank two")
    return divisor


def exact_right_divide_rank2(
    matrix: Matrix4x2,
    right_factor: Matrix2,
) -> Matrix4x2 | None:
    determinant = det2(right_factor)
    if determinant == 0:
        raise ValueError("right_factor must be full rank")
    a, b, c, d = right_factor
    adjugate: Matrix2 = (d, -b, -c, a)
    numerators = right_multiply_rank2(matrix, adjugate)
    if any(value % determinant for value in numerators):
        return None
    return tuple(
        value // determinant for value in numerators
    )  # type: ignore[return-value]


@dataclass(frozen=True)
class PrimitivePairFactorizationReference:
    primitive_matrix: Matrix4x2
    source_right_factor: Matrix2
    repeat_index: int


@lru_cache(maxsize=None)
def primitiveize_pair_matrix_2d(
    matrix: Matrix4x2,
) -> PrimitivePairFactorizationReference:
    repeat_index = determinantal_divisor_rank2(matrix)
    if repeat_index == 1:
        return PrimitivePairFactorizationReference(matrix, IDENTITY_2D, 1)
    for right_factor in enumerate_row_hnf_2d_by_index(repeat_index):
        primitive = exact_right_divide_rank2(matrix, right_factor)
        if primitive is None or determinantal_divisor_rank2(primitive) != 1:
            continue
        if right_multiply_rank2(primitive, right_factor) != matrix:
            raise AssertionError("primitive factorization failed")
        return PrimitivePairFactorizationReference(
            primitive_matrix=primitive,
            source_right_factor=right_factor,
            repeat_index=repeat_index,
        )
    raise AssertionError("no exact primitive factorization found")


@lru_cache(maxsize=None)
def canonicalize_common_right_rank2(matrix: Matrix4x2) -> Matrix4x2:
    rows = _rows4x2(matrix)
    best: Matrix4x2 | None = None
    for first, second in combinations(range(4), 2):
        pivot: Matrix2 = (
            rows[first][0], rows[first][1], rows[second][0], rows[second][1]
        )
        if det2(pivot) == 0:
            continue
        witness = hnf2_col_with_transform(pivot)
        candidate = right_multiply_rank2(matrix, witness.right_transform)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise ValueError("matrix must have rank two")
    return best


def _restrict_group(
    group: Sequence[Matrix2],
    pair_symmetry: PairSymmetry,
) -> tuple[Matrix2, ...]:
    operations = tuple(sorted(set(matrix2(item) for item in group)))
    if not operations:
        raise ValueError("point group must be nonempty")
    if pair_symmetry == "full":
        return operations
    if pair_symmetry != "proper":
        raise ValueError("pair_symmetry must be 'proper' or 'full'")
    proper = tuple(item for item in operations if det2(item) == 1)
    if not proper:
        raise ValueError("proper point group must contain a determinant +1 operation")
    return proper


@lru_cache(maxsize=None)
def _canonicalize_primitive_pair_cached(
    matrix: Matrix4x2,
    group_a: tuple[Matrix2, ...],
    group_b: tuple[Matrix2, ...],
    identify_material_exchange: bool,
) -> Matrix4x2:
    block_a, block_b = split_pair(matrix)
    best: Matrix4x2 | None = None
    exchange_modes = (False, True) if identify_material_exchange else (False,)
    for exchanged in exchange_modes:
        first, second = (block_b, block_a) if exchanged else (block_a, block_b)
        first_group, second_group = (
            (group_b, group_a) if exchanged else (group_a, group_b)
        )
        for operation_a in first_group:
            transformed_a = multiply2(operation_a, first)
            for operation_b in second_group:
                transformed = stack_pair(
                    transformed_a,
                    multiply2(operation_b, second),
                )
                candidate = canonicalize_common_right_rank2(transformed)
                if best is None or candidate < best:
                    best = candidate
    if best is None:
        raise AssertionError("pair canonicalization produced no candidates")
    return best


def canonicalize_primitive_pair_2d(
    matrix: Matrix4x2,
    *,
    point_group_a: Sequence[Matrix2],
    point_group_b: Sequence[Matrix2],
    pair_symmetry: PairSymmetry = "full",
    identify_material_exchange: bool = False,
) -> Matrix4x2:
    if determinantal_divisor_rank2(matrix) != 1:
        raise ValueError("matrix must be primitive")
    group_a = _restrict_group(point_group_a, pair_symmetry)
    group_b = _restrict_group(point_group_b, pair_symmetry)
    return _canonicalize_primitive_pair_cached(
        matrix,
        group_a,
        group_b,
        bool(identify_material_exchange),
    )


def transform_metric(metric: Metric2, transform: Matrix2) -> Metric2:
    """Return the exact pullback ``transform.T @ metric @ transform``."""
    g00, g01, _g10, g11 = metric
    a, b, c, d = transform
    first = (a, c)
    second = (b, d)

    def bilinear(left: tuple[int, int], right: tuple[int, int]) -> Fraction:
        x, y = left
        s, t = right
        return x * (g00 * s + g01 * t) + y * (g01 * s + g11 * t)

    return (
        bilinear(first, first),
        bilinear(first, second),
        bilinear(second, first),
        bilinear(second, second),
    )


def _integer_metric_pair(
    metric_a: Metric2,
    metric_b: Metric2,
) -> tuple[
    tuple[int, int, int, int],
    tuple[int, int, int, int],
]:
    denominator = 1
    for value in (*metric_a, *metric_b):
        denominator = lcm(denominator, value.denominator)
    integer_a = tuple(int(value * denominator) for value in metric_a)
    integer_b = tuple(int(value * denominator) for value in metric_b)
    common = 0
    for value in (*integer_a, *integer_b):
        common = gcd(common, abs(value))
    if common > 1:
        integer_a = tuple(value // common for value in integer_a)
        integer_b = tuple(value // common for value in integer_b)
    return integer_a, integer_b  # type: ignore[return-value]


def _integer_metric_det(metric: tuple[int, int, int, int]) -> int:
    a, b, c, d = metric
    return a * d - b * c


def _quadratic_form(metric: tuple[int, int, int, int], vector: tuple[int, int]) -> int:
    a, b, _c, d = metric
    x, y = vector
    return a * x * x + 2 * b * x * y + d * y * y


def _bilinear_form(
    metric: tuple[int, int, int, int],
    left: tuple[int, int],
    right: tuple[int, int],
) -> int:
    a, b, _c, d = metric
    x, y = left
    s, t = right
    return x * (a * s + b * t) + y * (b * s + d * t)


@lru_cache(maxsize=None)
def _vectors_with_norm(
    metric: tuple[int, int, int, int],
    target: int,
) -> tuple[tuple[int, int], ...]:
    determinant = _integer_metric_det(metric)
    if determinant <= 0 or target < 0:
        raise ValueError("metric must be positive definite and target nonnegative")
    if target == 0:
        return ((0, 0),)
    x_bound = isqrt((target * metric[3]) // determinant)
    y_bound = isqrt((target * metric[0]) // determinant)
    return tuple(
        (x, y)
        for x in range(-x_bound, x_bound + 1)
        for y in range(-y_bound, y_bound + 1)
        if _quadratic_form(metric, (x, y)) == target
    )


@lru_cache(maxsize=None)
def enumerate_exact_correspondences(
    metric_a: Metric2,
    metric_b: Metric2,
    orientation: CorrespondenceOrientation = "proper",
) -> tuple[Matrix2, ...]:
    """Enumerate exact unimodular maps ``U`` with ``U.T G_B U = G_A``."""
    if orientation not in {"proper", "all"}:
        raise ValueError("orientation must be 'proper' or 'all'")
    integer_a, integer_b = _integer_metric_pair(metric_a, metric_b)
    if _integer_metric_det(integer_a) != _integer_metric_det(integer_b):
        return ()
    correspondences: set[Matrix2] = set()
    for first_column in _vectors_with_norm(integer_b, integer_a[0]):
        for second_column in _vectors_with_norm(integer_b, integer_a[3]):
            if _bilinear_form(integer_b, first_column, second_column) != integer_a[1]:
                continue
            transform: Matrix2 = (
                first_column[0], second_column[0],
                first_column[1], second_column[1],
            )
            determinant = det2(transform)
            if determinant == 1 or (orientation == "all" and determinant == -1):
                correspondences.add(transform)
    return tuple(sorted(correspondences))


def enumerate_metric_point_group(metric: Metric2) -> tuple[Matrix2, ...]:
    """Return the full exact integral automorphism group of one 2D metric."""
    group = enumerate_exact_correspondences(metric, metric, orientation="all")
    if IDENTITY_2D not in group:
        raise AssertionError("metric point group omitted identity")
    return group


@dataclass(frozen=True)
class ReferenceClass:
    key: Matrix4x2
    source_pairs: tuple[Matrix4x2, ...]
    source_index_pairs: tuple[tuple[int, int], ...]
    repeat_indices: tuple[int, ...]
    first_discovery_index: int


@dataclass(frozen=True)
class ReferenceSearchResult:
    k_max: int
    pair_symmetry: PairSymmetry
    correspondence_orientation: CorrespondenceOrientation
    identify_material_exchange: bool
    point_group_a: tuple[Matrix2, ...]
    point_group_b: tuple[Matrix2, ...]
    hnf_pair_count: int
    correspondence_state_count: int
    classes: tuple[ReferenceClass, ...]

    @property
    def keys(self) -> frozenset[Matrix4x2]:
        return frozenset(item.key for item in self.classes)


def exhaustive_reference_search(
    metric_a: Metric2,
    metric_b: Metric2,
    *,
    k_max: int,
    point_group_a: Sequence[Matrix2] | None = None,
    point_group_b: Sequence[Matrix2] | None = None,
    pair_symmetry: PairSymmetry = "full",
    correspondence_orientation: CorrespondenceOrientation = "proper",
    identify_material_exchange: bool = False,
) -> ReferenceSearchResult:
    """Exhaustively enumerate exact zero-strain primitive coupled classes."""
    if isinstance(k_max, bool) or not isinstance(k_max, Integral) or k_max <= 0:
        raise ValueError("k_max must be a positive integer")
    metric_a = metric2(metric_a)
    metric_b = metric2(metric_b)
    group_a = tuple(point_group_a or enumerate_metric_point_group(metric_a))
    group_b = tuple(point_group_b or enumerate_metric_point_group(metric_b))
    aggregate: dict[Matrix4x2, dict[str, set[object]]] = {}
    hnf_pair_count = 0
    correspondence_state_count = 0
    determinant_a = det_metric(metric_a)
    determinant_b = det_metric(metric_b)

    for index_a in range(1, int(k_max) + 1):
        for index_b in range(1, int(k_max) + 1):
            if determinant_a * index_a * index_a != determinant_b * index_b * index_b:
                continue
            for hnf_a in enumerate_hnf_2d_by_index(index_a):
                cell_metric_a = transform_metric(metric_a, hnf_a)
                for hnf_b in enumerate_hnf_2d_by_index(index_b):
                    hnf_pair_count += 1
                    cell_metric_b = transform_metric(metric_b, hnf_b)
                    correspondences = enumerate_exact_correspondences(
                        cell_metric_a,
                        cell_metric_b,
                        orientation=correspondence_orientation,
                    )
                    for correspondence in correspondences:
                        correspondence_state_count += 1
                        source_pair = stack_pair(
                            hnf_a,
                            multiply2(hnf_b, correspondence),
                        )
                        factorization = primitiveize_pair_matrix_2d(source_pair)
                        key = canonicalize_primitive_pair_2d(
                            factorization.primitive_matrix,
                            point_group_a=group_a,
                            point_group_b=group_b,
                            pair_symmetry=pair_symmetry,
                            identify_material_exchange=identify_material_exchange,
                        )
                        bucket = aggregate.setdefault(
                            key,
                            {
                                "source_pairs": set(),
                                "source_index_pairs": set(),
                                "repeat_indices": set(),
                            },
                        )
                        bucket["source_pairs"].add(source_pair)
                        bucket["source_index_pairs"].add((index_a, index_b))
                        bucket["repeat_indices"].add(factorization.repeat_index)

    classes = tuple(
        ReferenceClass(
            key=key,
            source_pairs=tuple(
                sorted(bucket["source_pairs"])
            ),  # type: ignore[arg-type]
            source_index_pairs=tuple(
                sorted(bucket["source_index_pairs"])
            ),  # type: ignore[arg-type]
            repeat_indices=tuple(
                sorted(bucket["repeat_indices"])
            ),  # type: ignore[arg-type]
            first_discovery_index=min(
                max(index_pair)
                for index_pair in bucket[
                    "source_index_pairs"
                ]  # type: ignore[union-attr]
            ),
        )
        for key, bucket in sorted(aggregate.items())
    )
    return ReferenceSearchResult(
        k_max=int(k_max),
        pair_symmetry=pair_symmetry,
        correspondence_orientation=correspondence_orientation,
        identify_material_exchange=bool(identify_material_exchange),
        point_group_a=tuple(sorted(set(group_a))),
        point_group_b=tuple(sorted(set(group_b))),
        hnf_pair_count=hnf_pair_count,
        correspondence_state_count=correspondence_state_count,
        classes=classes,
    )


__all__ = [
    "CorrespondenceOrientation",
    "IDENTITY_2D",
    "Matrix2",
    "Matrix4x2",
    "Metric2",
    "PairSymmetry",
    "ReferenceClass",
    "ReferenceSearchResult",
    "canonicalize_primitive_pair_2d",
    "det2",
    "det_metric",
    "enumerate_exact_correspondences",
    "enumerate_hnf_2d_by_index",
    "enumerate_metric_point_group",
    "exhaustive_reference_search",
    "matrix2",
    "matrix4x2",
    "metric2",
    "multiply2",
    "primitiveize_pair_matrix_2d",
    "stack_pair",
    "transform_metric",
]
