"""Private observation hook for admitted coupled-match descriptions.

The production matcher aggregates admitted source descriptions online.  The
benchmark suite occasionally needs the complete pre-aggregation population,
but that population is deliberately not part of the public search result or
the persisted project schema.  This module provides a context-local observer
for that narrow use case.

Observers run synchronously.  An observer failure aborts the search so a
benchmark cannot silently continue with an incomplete trace.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, cast

import numpy as np

if TYPE_CHECKING:
    from calm.interface.matching._orchestrator import (
        _CandidateGeometry2D,
        _CoupledMatchSearchPlan,
    )
    from calm.interface.matching._types import (
        PairCanonicalization2D,
        PairIdentityPolicy2D,
        SourceMatchProvenance2D,
        SurfaceCellMember2D,
    )


IntMatrix = tuple[tuple[int, ...], ...]
FloatMatrix = tuple[tuple[float, ...], ...]


def _int_matrix(value: object, *, shape: tuple[int, int]) -> IntMatrix:
    matrix = np.asarray(value)
    if matrix.shape != shape or matrix.dtype.kind not in {"i", "u"}:
        raise TypeError(f"trace matrix must be an exact integer {shape} matrix")
    return tuple(tuple(int(item) for item in row) for row in matrix)


def _float_matrix(value: object, *, shape: tuple[int, int]) -> FloatMatrix:
    matrix = np.asarray(value, dtype=float)
    if matrix.shape != shape or not np.all(np.isfinite(matrix)):
        raise ValueError(f"trace matrix must be a finite {shape} matrix")
    return tuple(tuple(float(item) for item in row) for row in matrix)


def _float_vector(value: object, *, length: int) -> tuple[float, ...]:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (length,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"trace vector must contain {length} finite values")
    return tuple(float(item) for item in vector)


def _determinant_2d(matrix: np.ndarray) -> int:
    return (
        int(matrix[0, 0]) * int(matrix[1, 1])
        - int(matrix[0, 1]) * int(matrix[1, 0])
    )


def _gram(basis: np.ndarray) -> np.ndarray:
    matrix = basis.T @ basis
    return 0.5 * (matrix + matrix.T)


def _json_native(value: object) -> object:
    """Recursively convert a dataclass payload to JSON-native containers."""

    if isinstance(value, dict):
        return {str(key): _json_native(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_native(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported trace payload value: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class _CoupledMatchSearchTraceContext:
    """Immutable search-wide inputs shared by every emitted source record."""

    k_max: int
    condition_number_limit: float
    strain_limit: float
    atom_limit: int
    match_weight: float
    d_size_max: float
    metric_tolerance: float
    correspondence_entry_limit: int | None
    n_atoms_A: int
    n_atoms_B: int
    pair_symmetry: str
    correspondence_orientation: str
    identify_material_exchange: bool
    pair_key_version: int
    surface_basis_A: FloatMatrix
    surface_basis_B: FloatMatrix
    surface_point_group_A: tuple[IntMatrix, ...]
    surface_point_group_B: tuple[IntMatrix, ...]
    area_admissible_index_pairs: tuple[tuple[int, int], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a detached payload using JSON arrays rather than tuples."""

        return cast(dict[str, Any], _json_native(asdict(self)))


@dataclass(frozen=True, slots=True)
class _AdmittedMatchTraceRecord:
    """Immutable, JSON-serializable state of one admitted source description."""

    audit_index: int
    audit_k: int
    source_index_A: int
    source_index_B: int
    source_H_A: IntMatrix
    source_H_B: IntMatrix
    source_orbit_key_A: tuple[int, ...]
    source_orbit_key_B: tuple[int, ...]
    source_N_A: IntMatrix
    source_N_B: IntMatrix
    correspondence_U_B: IntMatrix
    source_pair_matrix: IntMatrix
    source_right_factor: IntMatrix
    repeat_index: int
    maximal_minors: tuple[int, ...]
    primitive_pair_matrix: IntMatrix
    final_pair_key: tuple[int, ...]
    canonical_pair_matrix: IntMatrix
    canonical_point_operation_A: IntMatrix
    canonical_point_operation_B: IntMatrix
    canonical_common_right_transform: IntMatrix
    canonical_pivot_rows: tuple[int, int]
    material_exchange_applied: bool
    pair_symmetry: str
    correspondence_orientation: str
    identify_material_exchange: bool
    pair_key_version: int
    surface_basis_A: FloatMatrix
    surface_basis_B: FloatMatrix
    source_basis_A: FloatMatrix
    source_basis_B: FloatMatrix
    source_gram_A: FloatMatrix
    source_gram_B: FloatMatrix
    primitive_basis_A: FloatMatrix
    primitive_basis_B: FloatMatrix
    primitive_gram_A: FloatMatrix
    primitive_gram_B: FloatMatrix
    member_condition_number_A: float
    member_condition_number_B: float
    source_condition_number_A: float
    source_condition_number_B: float
    enumerated_principal_log_strains: tuple[float, ...]
    principal_log_strains: tuple[float, ...]
    relative_metric_eigenvalues: tuple[float, ...]
    max_abs_principal_strain: float
    d_cell: float
    d_area: float
    d_shape: float
    source_atom_count: int
    primitive_atom_count: int
    atom_count: int
    d_size: float
    match_score: float

    def to_dict(self) -> dict[str, Any]:
        """Return a detached payload using JSON arrays rather than tuples."""

        return cast(dict[str, Any], _json_native(asdict(self)))


_AdmittedMatchObserver = Callable[[_AdmittedMatchTraceRecord], None]
_SearchContextObserver = Callable[[_CoupledMatchSearchTraceContext], None]
_ADMITTED_MATCH_OBSERVERS: ContextVar[tuple[_AdmittedMatchObserver, ...]] = (
    ContextVar("calm_admitted_match_observers", default=())
)
_SEARCH_CONTEXT_OBSERVERS: ContextVar[tuple[_SearchContextObserver, ...]] = (
    ContextVar("calm_match_search_context_observers", default=())
)


@contextmanager
def _observe_admitted_match_records(
    observer: _AdmittedMatchObserver,
) -> Iterator[None]:
    """Install one context-local observer for the duration of a benchmark."""

    if not callable(observer):
        raise TypeError("observer must be callable")
    current = _ADMITTED_MATCH_OBSERVERS.get()
    token = _ADMITTED_MATCH_OBSERVERS.set((*current, observer))
    try:
        yield
    finally:
        _ADMITTED_MATCH_OBSERVERS.reset(token)


@contextmanager
def _capture_admitted_match_records(
) -> Iterator[list[_AdmittedMatchTraceRecord]]:
    """Collect records in memory within one context-local benchmark scope."""

    records: list[_AdmittedMatchTraceRecord] = []
    with _observe_admitted_match_records(records.append):
        yield records


@dataclass(slots=True)
class _CoupledMatchTraceCapture:
    """Mutable sink containing immutable search contexts and source records."""

    search_contexts: list[_CoupledMatchSearchTraceContext] = field(
        default_factory=list
    )
    records: list[_AdmittedMatchTraceRecord] = field(default_factory=list)


@contextmanager
def _capture_coupled_match_trace() -> Iterator[_CoupledMatchTraceCapture]:
    """Capture complete private benchmark evidence for one matcher invocation.

    ``audit_index`` is local to an invocation.  Callers comparing several
    searches must therefore open a separate capture scope for each search, as
    the LiF/Li2O comparison driver does.
    """

    capture = _CoupledMatchTraceCapture()
    context_token = _SEARCH_CONTEXT_OBSERVERS.set(
        (*_SEARCH_CONTEXT_OBSERVERS.get(), capture.search_contexts.append)
    )
    try:
        with _observe_admitted_match_records(capture.records.append):
            yield capture
    finally:
        _SEARCH_CONTEXT_OBSERVERS.reset(context_token)


def _admitted_match_trace_is_active() -> bool:
    """Return whether the current context contains at least one observer."""

    return bool(_ADMITTED_MATCH_OBSERVERS.get())


def _search_context_trace_is_active() -> bool:
    """Return whether the current context contains a search-context observer."""

    return bool(_SEARCH_CONTEXT_OBSERVERS.get())


def _emit_admitted_match_record(record: _AdmittedMatchTraceRecord) -> None:
    """Synchronously emit one immutable record to current-context observers."""

    if not isinstance(record, _AdmittedMatchTraceRecord):
        raise TypeError("record must be an _AdmittedMatchTraceRecord")
    for observer in _ADMITTED_MATCH_OBSERVERS.get():
        observer(record)


def _emit_search_context(context: _CoupledMatchSearchTraceContext) -> None:
    """Synchronously emit one search context to current-context observers."""

    if not isinstance(context, _CoupledMatchSearchTraceContext):
        raise TypeError("context must be a _CoupledMatchSearchTraceContext")
    for observer in _SEARCH_CONTEXT_OBSERVERS.get():
        observer(context)


def _build_search_trace_context(
    plan: _CoupledMatchSearchPlan,
) -> _CoupledMatchSearchTraceContext:
    """Snapshot the search-wide state needed by external classifiers."""

    policy = plan.policy
    return _CoupledMatchSearchTraceContext(
        k_max=int(plan.k_max),
        condition_number_limit=float(plan.condition_limit),
        strain_limit=float(plan.strain_limit),
        atom_limit=int(plan.atom_limit),
        match_weight=float(plan.weight),
        d_size_max=float(plan.d_size_max),
        metric_tolerance=float(plan.metric_tolerance),
        correspondence_entry_limit=(
            None if plan.entry_limit is None else int(plan.entry_limit)
        ),
        n_atoms_A=int(plan.n_a),
        n_atoms_B=int(plan.n_b),
        pair_symmetry=str(policy.pair_symmetry),
        correspondence_orientation=str(policy.correspondence_orientation),
        identify_material_exchange=bool(policy.identify_material_exchange),
        pair_key_version=int(policy.key_version),
        surface_basis_A=_float_matrix(plan.basis_a, shape=(2, 2)),
        surface_basis_B=_float_matrix(plan.basis_b, shape=(2, 2)),
        surface_point_group_A=tuple(
            _int_matrix(operation, shape=(2, 2))
            for operation in plan.point_group_a
        ),
        surface_point_group_B=tuple(
            _int_matrix(operation, shape=(2, 2))
            for operation in plan.point_group_b
        ),
        area_admissible_index_pairs=tuple(
            (int(index_a), int(index_b))
            for index_a, index_b in plan.index_pairs
        ),
    )


def _build_admitted_match_record(
    *,
    audit_index: int,
    audit_k: int,
    basis_A: np.ndarray,
    basis_B: np.ndarray,
    n_atoms_A: int,
    n_atoms_B: int,
    member_A: SurfaceCellMember2D,
    member_B: SurfaceCellMember2D,
    enumerated_principal_log_strains: object,
    geometry: _CandidateGeometry2D,
    provenance: SourceMatchProvenance2D,
    pair_canonicalization: PairCanonicalization2D,
    pair_identity_policy: PairIdentityPolicy2D,
) -> _AdmittedMatchTraceRecord:
    """Snapshot one admitted source without retaining mutable search objects."""

    surface_a = np.asarray(basis_A, dtype=float)
    surface_b = np.asarray(basis_B, dtype=float)
    source_pair = np.asarray(provenance.source_pair_matrix, dtype=int)
    primitive_pair = np.asarray(geometry.primitive_matrix, dtype=int)
    source_basis_a = surface_a @ source_pair[:2, :]
    source_basis_b = surface_b @ source_pair[2:, :]
    primitive_basis_a = surface_a @ primitive_pair[:2, :]
    primitive_basis_b = surface_b @ primitive_pair[2:, :]
    source_atom_count = (
        abs(_determinant_2d(source_pair[:2, :])) * int(n_atoms_A)
        + abs(_determinant_2d(source_pair[2:, :])) * int(n_atoms_B)
    )
    strain = geometry.ai_strain
    canonicalization = pair_canonicalization
    policy = pair_identity_policy
    return _AdmittedMatchTraceRecord(
        audit_index=int(audit_index),
        audit_k=int(audit_k),
        source_index_A=abs(_determinant_2d(provenance.source_H_A)),
        source_index_B=abs(_determinant_2d(provenance.source_H_B)),
        source_H_A=_int_matrix(provenance.source_H_A, shape=(2, 2)),
        source_H_B=_int_matrix(provenance.source_H_B, shape=(2, 2)),
        source_orbit_key_A=tuple(int(x) for x in provenance.source_orbit_key_A),
        source_orbit_key_B=tuple(int(x) for x in provenance.source_orbit_key_B),
        source_N_A=_int_matrix(provenance.source_N_A, shape=(2, 2)),
        source_N_B=_int_matrix(provenance.source_N_B, shape=(2, 2)),
        correspondence_U_B=_int_matrix(
            provenance.correspondence_U_B,
            shape=(2, 2),
        ),
        source_pair_matrix=_int_matrix(source_pair, shape=(4, 2)),
        source_right_factor=_int_matrix(
            provenance.source_right_factor,
            shape=(2, 2),
        ),
        repeat_index=int(provenance.repeat_index),
        maximal_minors=tuple(int(x) for x in provenance.maximal_minors),
        primitive_pair_matrix=_int_matrix(primitive_pair, shape=(4, 2)),
        final_pair_key=tuple(int(x) for x in canonicalization.key),
        canonical_pair_matrix=_int_matrix(
            canonicalization.canonical_matrix,
            shape=(4, 2),
        ),
        canonical_point_operation_A=_int_matrix(
            canonicalization.point_operation_A,
            shape=(2, 2),
        ),
        canonical_point_operation_B=_int_matrix(
            canonicalization.point_operation_B,
            shape=(2, 2),
        ),
        canonical_common_right_transform=_int_matrix(
            canonicalization.common_right_transform,
            shape=(2, 2),
        ),
        canonical_pivot_rows=tuple(canonicalization.pivot_rows),
        material_exchange_applied=bool(
            canonicalization.material_exchange_applied
        ),
        pair_symmetry=str(policy.pair_symmetry),
        correspondence_orientation=str(policy.correspondence_orientation),
        identify_material_exchange=bool(policy.identify_material_exchange),
        pair_key_version=int(policy.key_version),
        surface_basis_A=_float_matrix(surface_a, shape=(2, 2)),
        surface_basis_B=_float_matrix(surface_b, shape=(2, 2)),
        source_basis_A=_float_matrix(source_basis_a, shape=(2, 2)),
        source_basis_B=_float_matrix(source_basis_b, shape=(2, 2)),
        source_gram_A=_float_matrix(_gram(source_basis_a), shape=(2, 2)),
        source_gram_B=_float_matrix(_gram(source_basis_b), shape=(2, 2)),
        primitive_basis_A=_float_matrix(primitive_basis_a, shape=(2, 2)),
        primitive_basis_B=_float_matrix(primitive_basis_b, shape=(2, 2)),
        primitive_gram_A=_float_matrix(_gram(primitive_basis_a), shape=(2, 2)),
        primitive_gram_B=_float_matrix(_gram(primitive_basis_b), shape=(2, 2)),
        member_condition_number_A=float(member_A.condition_number),
        member_condition_number_B=float(member_B.condition_number),
        source_condition_number_A=float(np.linalg.cond(source_basis_a)),
        source_condition_number_B=float(np.linalg.cond(source_basis_b)),
        enumerated_principal_log_strains=_float_vector(
            enumerated_principal_log_strains,
            length=2,
        ),
        principal_log_strains=_float_vector(
            strain.principal_strains,
            length=2,
        ),
        relative_metric_eigenvalues=_float_vector(strain.mu, length=2),
        max_abs_principal_strain=float(strain.max_abs_principal_strain),
        d_cell=float(strain.d_cell),
        d_area=float(strain.d_area),
        d_shape=float(strain.d_shape),
        source_atom_count=source_atom_count,
        primitive_atom_count=int(geometry.atom_count),
        atom_count=int(geometry.atom_count),
        d_size=float(geometry.d_size),
        match_score=float(geometry.match_score),
    )
