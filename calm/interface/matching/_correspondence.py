"""Complete strain-bounded basis-correspondence enumeration for coupled matching."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import chain
import math

import numpy as np

from calm.math2d._core import sym2
from calm.math2d.spd2x2 import check_spd2, invsqrt_spd
from calm.math2d.sym2x2 import eigvals2_spd

from calm.interface.config import CorrespondenceOrientation
from calm.interface.matching._types import BasisCorrespondence2D
from calm.interface.matching._utils import (
    _finite_nonnegative_float,
    _positive_integer,
)

# High-level coupled searches enumerate the complete proven finite domain by
# default. Callers may provide an explicit positive entry limit when they need
# a hard safety cap; such a configured cap is never exceeded silently.
DEFAULT_CORRESPONDENCE_ENTRY_LIMIT: int | None = None

# Large Cartesian products are screened in bounded NumPy chunks. Small products
# remain in scalar Python because array construction costs more than the loop.
_VECTOR_DETERMINANT_PAIR_THRESHOLD = 4096
_VECTOR_DETERMINANT_TARGET_BYTES = 4 * 1024 * 1024
_VECTOR_DETERMINANT_BYTES_PER_PAIR = 32
_INT64_DETERMINANT_SAFE_COMPONENT = math.isqrt(int(np.iinfo(np.int64).max) // 2)

_SymmetricMetric2D = tuple[float, float, float]
_TransformKey2D = tuple[int, int, int, int]
_CorrespondenceRecord = tuple[_TransformKey2D, tuple[float, float]]


class CorrespondenceEnumerationLimitError(RuntimeError):
    """Raised when the proven complete integer search exceeds its safety limit."""

    def __init__(self, *, required_entry_bound: int, entry_limit: int) -> None:
        self.required_entry_bound = int(required_entry_bound)
        self.entry_limit = int(entry_limit)
        super().__init__(
            "complete basis-correspondence enumeration requires integer "
            f"entries through {self.required_entry_bound}, which exceeds "
            f"entry_limit={self.entry_limit}"
        )


@dataclass(frozen=True)
class _PreparedCorrespondenceMetric2D:
    """One validated symmetric metric reusable within a coupled search."""

    values: _SymmetricMetric2D
    scale: float


@dataclass(frozen=True)
class _CachedCorrespondenceEnumeration:
    records: tuple[_CorrespondenceRecord, ...]
    required_entry_bound: int
    first_column_candidates: int
    second_column_candidates: int
    column_pairs_tested: int
    unimodular_states_tested: int
    determinant_chunks: int


def _orientation(value: object) -> CorrespondenceOrientation:
    if value not in {"proper", "all"}:
        raise ValueError("orientation must be either 'proper' or 'all'")
    return value  # type: ignore[return-value]


def _metric(
    name: str,
    value: object,
    *,
    tolerance: float,
) -> np.ndarray:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2)")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")

    scale = float(np.max(np.abs(matrix)))
    if scale <= 0.0:
        raise ValueError(f"{name} must be positive definite")
    asymmetry = float(np.max(np.abs(matrix - matrix.T)))
    if asymmetry > tolerance * scale:
        raise ValueError(f"{name} must be symmetric within metric_tolerance")

    symmetric = sym2(matrix)
    # Validate positive definiteness in a dimensionless gauge. Computing the
    # raw 2x2 determinant can underflow for physically valid cells with very
    # small common length scales, or overflow for very large common scales.
    # The correspondence relation is invariant under one positive common
    # metric factor, so this normalization changes neither admissibility nor
    # the proven integer search bounds.
    check_spd2(symmetric / scale, tol=0.0, symmetrize=False)
    return symmetric


def _prepare_correspondence_metric_2d(
    name: str,
    value: object,
    *,
    tolerance: float,
) -> _PreparedCorrespondenceMetric2D:
    """Validate one metric once and retain an immutable scalar representation."""

    matrix = _metric(name, value, tolerance=tolerance)
    values = (
        float(matrix[0, 0]),
        float(matrix[0, 1]),
        float(matrix[1, 1]),
    )
    return _PreparedCorrespondenceMetric2D(
        values=values,
        scale=max(abs(values[0]), abs(values[1]), abs(values[2])),
    )


def _metric_hex(
    metric: _PreparedCorrespondenceMetric2D,
    *,
    common_scale: float,
) -> tuple[str, str, str]:
    normalized = tuple((value / common_scale).hex() for value in metric.values)
    return normalized  # type: ignore[return-value]


def _metric_from_hex(values: tuple[str, str, str]) -> _SymmetricMetric2D:
    return tuple(float.fromhex(value) for value in values)  # type: ignore[return-value]


def _inverse_diagonal(metric: _SymmetricMetric2D) -> tuple[float, float]:
    a, b, d = metric
    determinant = a * d - b * b
    return d / determinant, a / determinant


def _entry_bounds(
    metric_a: _SymmetricMetric2D,
    metric_b_inverse_diagonal: tuple[float, float],
    *,
    upper_factor: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return proven component bounds for the two integer columns.

    If ``x.T @ G_B @ x <= q``, dual-norm Cauchy-Schwarz gives
    ``|x_i|^2 <= q * (G_B^{-1})_ii``. Applying this to each diagonal
    consequence of the upper metric inequality bounds every admissible integer
    column of the correspondence matrix.
    """

    columns: list[tuple[int, int]] = []
    for diagonal in (metric_a[0], metric_a[2]):
        q_max = upper_factor * diagonal
        component_bounds: list[int] = []
        for inverse_diagonal in metric_b_inverse_diagonal:
            squared_bound = q_max * inverse_diagonal
            if not math.isfinite(squared_bound) or squared_bound < 0.0:
                raise ValueError("failed to derive a finite correspondence-entry bound")
            roundoff = 64.0 * np.finfo(float).eps * max(1.0, squared_bound)
            conservative = math.nextafter(squared_bound + roundoff, math.inf)
            component_bounds.append(int(math.floor(math.sqrt(conservative))))
        columns.append((component_bounds[0], component_bounds[1]))
    return columns[0], columns[1]


def _quadratic_form(
    metric: _SymmetricMetric2D,
    vector: tuple[int, int],
) -> float:
    a, b, d = metric
    x, y = vector
    return float(a * x * x + 2.0 * b * x * y + d * y * y)


def _column_vectors(
    metric_b: _SymmetricMetric2D,
    *,
    component_bounds: tuple[int, int],
    q_min: float,
    q_max: float,
    tolerance: float,
) -> tuple[tuple[int, int], ...]:
    bound_x, bound_y = component_bounds
    vectors: list[tuple[int, int]] = []
    scale = max(np.finfo(float).tiny, abs(q_min), abs(q_max))
    absolute_tolerance = tolerance * scale + 64.0 * np.finfo(float).eps * scale
    for x in range(-bound_x, bound_x + 1):
        for y in range(-bound_y, bound_y + 1):
            if x == 0 and y == 0:
                continue
            value = _quadratic_form(metric_b, (x, y))
            if q_min - absolute_tolerance <= value <= q_max + absolute_tolerance:
                vectors.append((x, y))
    return tuple(vectors)


def _determinant_columns(
    first: tuple[int, int],
    second: tuple[int, int],
) -> int:
    return first[0] * second[1] - second[0] * first[1]


def _metric_array(metric: _SymmetricMetric2D) -> np.ndarray:
    a, b, d = metric
    return np.asarray([[a, b], [b, d]], dtype=float)


def _principal_strains(
    metric_a_inverse_sqrt: np.ndarray,
    transformed_metric_b: np.ndarray,
) -> tuple[float, float] | None:
    relative_metric = sym2(
        metric_a_inverse_sqrt @ transformed_metric_b @ metric_a_inverse_sqrt
    )
    eigenvalues = eigvals2_spd(relative_metric)
    if np.any(eigenvalues <= 0.0) or not np.all(np.isfinite(eigenvalues)):
        return None
    values = 0.5 * np.log(eigenvalues)
    if not np.all(np.isfinite(values)):
        return None
    return float(values[0]), float(values[1])


def _admissible_record(
    metric_b: np.ndarray,
    metric_a_inverse_sqrt: np.ndarray,
    first: tuple[int, int],
    second: tuple[int, int],
    *,
    effective_eps: float,
    strain_slack: float,
) -> _CorrespondenceRecord | None:
    transform = np.asarray(
        [
            [first[0], second[0]],
            [first[1], second[1]],
        ],
        dtype=int,
    )
    transformed_metric = sym2(transform.T @ metric_b @ transform)
    strains = _principal_strains(metric_a_inverse_sqrt, transformed_metric)
    if strains is None:
        return None
    if max(abs(strains[0]), abs(strains[1])) > effective_eps + strain_slack:
        return None
    return (first[0], second[0], first[1], second[1]), strains


def _use_vectorized_determinants(
    candidates_first: tuple[tuple[int, int], ...],
    candidates_second: tuple[tuple[int, int], ...],
) -> bool:
    pair_count = len(candidates_first) * len(candidates_second)
    if pair_count < _VECTOR_DETERMINANT_PAIR_THRESHOLD:
        return False
    maximum_component = max(
        (
            abs(component)
            for vector in chain(candidates_first, candidates_second)
            for component in vector
        ),
        default=0,
    )
    return maximum_component <= _INT64_DETERMINANT_SAFE_COMPONENT


def _determinant_chunk_size(second_count: int) -> int:
    estimated_row_bytes = max(
        1,
        second_count * _VECTOR_DETERMINANT_BYTES_PER_PAIR,
    )
    return max(1, _VECTOR_DETERMINANT_TARGET_BYTES // estimated_row_bytes)


def _enumerate_scalar_pairs(
    candidates_first: tuple[tuple[int, int], ...],
    candidates_second: tuple[tuple[int, int], ...],
    *,
    orientation: CorrespondenceOrientation,
    metric_b: np.ndarray,
    metric_a_inverse_sqrt: np.ndarray,
    effective_eps: float,
    strain_slack: float,
) -> tuple[list[_CorrespondenceRecord], int]:
    output: list[_CorrespondenceRecord] = []
    unimodular_states_tested = 0
    for first in candidates_first:
        for second in candidates_second:
            determinant = _determinant_columns(first, second)
            if orientation == "proper":
                if determinant != 1:
                    continue
            elif abs(determinant) != 1:
                continue
            unimodular_states_tested += 1
            record = _admissible_record(
                metric_b,
                metric_a_inverse_sqrt,
                first,
                second,
                effective_eps=effective_eps,
                strain_slack=strain_slack,
            )
            if record is not None:
                output.append(record)
    return output, unimodular_states_tested


def _enumerate_vectorized_determinants(
    candidates_first: tuple[tuple[int, int], ...],
    candidates_second: tuple[tuple[int, int], ...],
    *,
    orientation: CorrespondenceOrientation,
    metric_b: np.ndarray,
    metric_a_inverse_sqrt: np.ndarray,
    effective_eps: float,
    strain_slack: float,
) -> tuple[list[_CorrespondenceRecord], int, int]:
    """Screen determinant states in bounded arrays, then evaluate strains scalar."""

    output: list[_CorrespondenceRecord] = []
    unimodular_states_tested = 0
    determinant_chunks = 0
    second_array = np.asarray(candidates_second, dtype=np.int64)
    second_x = second_array[:, 0]
    second_y = second_array[:, 1]
    chunk_size = _determinant_chunk_size(len(candidates_second))

    for start in range(0, len(candidates_first), chunk_size):
        first_chunk = candidates_first[start : start + chunk_size]
        first_array = np.asarray(first_chunk, dtype=np.int64)
        determinants = (
            first_array[:, 0, None] * second_y[None, :]
            - second_x[None, :] * first_array[:, 1, None]
        )
        if orientation == "proper":
            admitted = determinants == 1
        else:
            admitted = np.abs(determinants) == 1
        rows, columns = np.nonzero(admitted)
        determinant_chunks += 1
        unimodular_states_tested += len(rows)

        for row, column in zip(rows.tolist(), columns.tolist(), strict=True):
            first = first_chunk[row]
            second = candidates_second[column]
            record = _admissible_record(
                metric_b,
                metric_a_inverse_sqrt,
                first,
                second,
                effective_eps=effective_eps,
                strain_slack=strain_slack,
            )
            if record is not None:
                output.append(record)

    return output, unimodular_states_tested, determinant_chunks


@lru_cache(maxsize=4096)
def _enumerate_cached(
    metric_a_hex: tuple[str, str, str],
    metric_b_hex: tuple[str, str, str],
    eps_hex: str,
    orientation: CorrespondenceOrientation,
    tolerance_hex: str,
    entry_limit: int | None,
) -> _CachedCorrespondenceEnumeration:
    metric_a = _metric_from_hex(metric_a_hex)
    metric_b = _metric_from_hex(metric_b_hex)
    eps = float.fromhex(eps_hex)
    tolerance = float.fromhex(tolerance_hex)
    effective_eps = eps + tolerance

    try:
        upper_factor = math.exp(2.0 * effective_eps)
    except OverflowError as exc:
        raise ValueError(
            "eps_principal_max is too large for finite enumeration"
        ) from exc
    if not math.isfinite(upper_factor):
        raise ValueError("eps_principal_max is too large for finite enumeration")
    lower_factor = 1.0 / upper_factor

    bounds_first, bounds_second = _entry_bounds(
        metric_a,
        _inverse_diagonal(metric_b),
        upper_factor=upper_factor,
    )
    required_bound = max(*bounds_first, *bounds_second)
    if entry_limit is not None and required_bound > entry_limit:
        raise CorrespondenceEnumerationLimitError(
            required_entry_bound=required_bound,
            entry_limit=entry_limit,
        )

    candidates_first = _column_vectors(
        metric_b,
        component_bounds=bounds_first,
        q_min=lower_factor * metric_a[0],
        q_max=upper_factor * metric_a[0],
        tolerance=tolerance,
    )
    candidates_second = _column_vectors(
        metric_b,
        component_bounds=bounds_second,
        q_min=lower_factor * metric_a[2],
        q_max=upper_factor * metric_a[2],
        tolerance=tolerance,
    )

    metric_b_array = _metric_array(metric_b)
    metric_a_inverse_sqrt = invsqrt_spd(_metric_array(metric_a))
    strain_slack = 64.0 * np.finfo(float).eps * max(1.0, effective_eps)
    determinant_chunks = 0
    if _use_vectorized_determinants(candidates_first, candidates_second):
        output, unimodular_states_tested, determinant_chunks = (
            _enumerate_vectorized_determinants(
                candidates_first,
                candidates_second,
                orientation=orientation,
                metric_b=metric_b_array,
                metric_a_inverse_sqrt=metric_a_inverse_sqrt,
                effective_eps=effective_eps,
                strain_slack=strain_slack,
            )
        )
    else:
        output, unimodular_states_tested = _enumerate_scalar_pairs(
            candidates_first,
            candidates_second,
            orientation=orientation,
            metric_b=metric_b_array,
            metric_a_inverse_sqrt=metric_a_inverse_sqrt,
            effective_eps=effective_eps,
            strain_slack=strain_slack,
        )

    output.sort(key=lambda item: item[0])
    return _CachedCorrespondenceEnumeration(
        records=tuple(output),
        required_entry_bound=required_bound,
        first_column_candidates=len(candidates_first),
        second_column_candidates=len(candidates_second),
        column_pairs_tested=len(candidates_first) * len(candidates_second),
        unimodular_states_tested=unimodular_states_tested,
        determinant_chunks=determinant_chunks,
    )


def _update_enumeration_stats(
    stats: dict[str, int] | None,
    cached: _CachedCorrespondenceEnumeration,
) -> None:
    if stats is None:
        return
    stats.update(
        {
            "required_entry_bound": cached.required_entry_bound,
            "first_column_candidates": cached.first_column_candidates,
            "second_column_candidates": cached.second_column_candidates,
            "column_pairs_tested": cached.column_pairs_tested,
            "unimodular_states_tested": cached.unimodular_states_tested,
            "strain_admissible_states": len(cached.records),
            "determinant_chunks": cached.determinant_chunks,
        }
    )


def _enumerate_basis_correspondence_records_prepared_2d(
    metric_a: _PreparedCorrespondenceMetric2D,
    metric_b: _PreparedCorrespondenceMetric2D,
    *,
    eps_principal_max: float,
    orientation: CorrespondenceOrientation,
    metric_tolerance: float,
    entry_limit: int | None,
    stats: dict[str, int] | None = None,
) -> _CachedCorrespondenceEnumeration:
    """Enumerate immutable records from metrics validated by the caller."""

    common_scale = max(metric_a.scale, metric_b.scale)
    cached = _enumerate_cached(
        _metric_hex(metric_a, common_scale=common_scale),
        _metric_hex(metric_b, common_scale=common_scale),
        float(eps_principal_max).hex(),
        orientation,
        float(metric_tolerance).hex(),
        entry_limit,
    )
    _update_enumeration_stats(stats, cached)
    return cached


def enumerate_basis_correspondences_2d(
    G_A: np.ndarray,
    G_B: np.ndarray,
    *,
    eps_principal_max: float,
    orientation: CorrespondenceOrientation,
    metric_tolerance: float,
    entry_limit: int | None = DEFAULT_CORRESPONDENCE_ENTRY_LIMIT,
    stats: dict[str, int] | None = None,
) -> tuple[BasisCorrespondence2D, ...]:
    """Enumerate every strain-admissible integer basis correspondence.

    The returned matrices ``U_B`` satisfy ``det(U_B)=+1`` for ``proper``
    orientation and ``abs(det(U_B))=1`` for ``all`` orientation. Admission is
    evaluated from the principal logarithmic strains of
    ``G_A^{-1/2} U_B.T G_B U_B G_A^{-1/2}``.

    The search is complete within the declared strain bound. A finite entry
    bound is proved from the upper metric inequality before enumeration. With
    ``entry_limit=None`` the complete proven domain is searched automatically.
    If an explicit positive limit is supplied and the proven bound exceeds it,
    the function raises :class:`CorrespondenceEnumerationLimitError` rather
    than returning a truncated result.
    """

    tolerance = _finite_nonnegative_float("metric_tolerance", metric_tolerance)
    eps = _finite_nonnegative_float("eps_principal_max", eps_principal_max)
    limit = (
        None if entry_limit is None else _positive_integer("entry_limit", entry_limit)
    )
    orientation_value = _orientation(orientation)

    metric_a = _prepare_correspondence_metric_2d(
        "G_A",
        G_A,
        tolerance=tolerance,
    )
    metric_b = _prepare_correspondence_metric_2d(
        "G_B",
        G_B,
        tolerance=tolerance,
    )
    cached = _enumerate_basis_correspondence_records_prepared_2d(
        metric_a,
        metric_b,
        eps_principal_max=eps,
        orientation=orientation_value,
        metric_tolerance=tolerance,
        entry_limit=limit,
        stats=stats,
    )

    correspondences: list[BasisCorrespondence2D] = []
    metric_b_array = _metric_array(metric_b.values)
    for transform_key, strains in cached.records:
        transform = np.asarray(transform_key, dtype=int).reshape(2, 2)
        transformed_metric = sym2(transform.T @ metric_b_array @ transform)
        correspondences.append(
            BasisCorrespondence2D(
                U_B=transform,
                principal_strains=np.asarray(strains, dtype=float),
                transformed_gram_B=transformed_metric,
            )
        )
    return tuple(correspondences)


__all__ = [
    "DEFAULT_CORRESPONDENCE_ENTRY_LIMIT",
    "CorrespondenceEnumerationLimitError",
    "enumerate_basis_correspondences_2d",
]
