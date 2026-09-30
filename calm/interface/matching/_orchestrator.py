"""Coupled-v2 primitive lattice-match orchestration.

This module assembles the exact arithmetic, surface-orbit, correspondence, and
pair-identity kernels. Every admitted source correspondence is primitiveized
locally and aggregated online by the exact primitive coupled-pair key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from typing import Any, Literal

import numpy as np

from calm.interface.matching.conditioning import DEFAULT_SUPERCELL_CONDITION_LIMIT
from calm.math2d.paired_lattice import (
    PrimitivePairFactorization2D,
    _canonicalize_common_right_rank2_tuple,
    primitiveize_pair_matrix_2d,
)
from calm.math2d.spd2x2 import cholesky2_spd, geodesic_spd
from calm.symmetry.reduction import oriented_gauss_reduce_2d

from calm.interface.matching._correspondence import (
    DEFAULT_CORRESPONDENCE_ENTRY_LIMIT,
    CorrespondenceEnumerationLimitError,
    _PreparedCorrespondenceMetric2D,
    _enumerate_basis_correspondence_records_prepared_2d,
    _prepare_correspondence_metric_2d,
)
from calm.interface.matching._pair_identity import (
    _PairIdentityContext2D,
    _canonicalize_primitive_pair_tuple_2d,
    _prepare_pair_identity_context_2d,
)
from calm.interface.matching._surface_orbits import (
    _build_surface_cell_orbit_index_prepared,
    _prepare_surface_orbit_build_context_2d,
)
from calm.interface.matching._types import (
    PairCanonicalization2D,
    PairIdentityPolicy2D,
    PrimitiveMatchCandidate2D,
    PrimitiveMatchClass2D,
    SourceMatchProvenance2D,
    SurfaceCellMember2D,
    SurfaceCellOrbit2D,
)
from calm.interface.matching._utils import (
    _compute_d_size,
    _compute_match_score,
    _finite_nonnegative_float,
    _finite_positive_float,
    _normalize_d_cell,
    _normalize_d_size,
    _positive_integer,
    _prim_inplane_basis_2d,
    _unit_interval_float,
    compute_valid_hnf_index_pairs,
)
from calm.interface.matching._audit_trace import (
    _admitted_match_trace_is_active,
    _build_admitted_match_record,
    _build_search_trace_context,
    _emit_admitted_match_record,
    _emit_search_context,
    _search_context_trace_is_active,
)
from calm.interface.matching.audit import (
    CoupledIdentityReductionCounts,
    CoupledMatchEnumerationAudit,
    CoupledSearchSpaceCounts,
)
from calm.interface.config import (
    CorrespondenceOrientation,
    DEFAULT_CORRESPONDENCE_ORIENTATION,
    DEFAULT_IDENTIFY_MATERIAL_EXCHANGE,
    DEFAULT_PAIR_SYMMETRY_POLICY,
    PairSymmetryPolicy,
)
from calm.interface.types import AffineInvariantStrain2D, ZMStrain2D


# Representative-shape comparison is only an optimization.  Bound its work
# independently; an over-limit result is treated as inconclusive.
_PREFILTER_CORRESPONDENCE_ENTRY_LIMIT = 128


def _strict_bool(name: str, value: object) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a boolean")
    return bool(value)


def _validate_policy(
    *,
    pair_symmetry_policy: object,
    correspondence_orientation: object,
    identify_material_exchange: object,
) -> PairIdentityPolicy2D:
    return PairIdentityPolicy2D(
        pair_symmetry=pair_symmetry_policy,  # type: ignore[arg-type]
        correspondence_orientation=correspondence_orientation,  # type: ignore[arg-type]
        identify_material_exchange=_strict_bool(
            "identify_material_exchange",
            identify_material_exchange,
        ),
    )


def _determinant_2d(matrix: np.ndarray) -> int:
    return int(matrix[0, 0]) * int(matrix[1, 1]) - int(matrix[0, 1]) * int(matrix[1, 0])


def _source_index_pair_from_provenance(
    provenance: SourceMatchProvenance2D,
) -> tuple[int, int]:
    return (
        abs(_determinant_2d(provenance.source_H_A)),
        abs(_determinant_2d(provenance.source_H_B)),
    )


def _source_index_pair(candidate: PrimitiveMatchCandidate2D) -> tuple[int, int]:
    return _source_index_pair_from_provenance(candidate.source_provenance)


def _safe_atom_lower_bound(
    k_a: int,
    k_b: int,
    n_a: int,
    n_b: int,
) -> int:
    common = gcd(k_a, k_b)
    return (k_a // common) * n_a + (k_b // common) * n_b


def _admitted_d_cell_for_scoring(
    ai_strain: AffineInvariantStrain2D,
    *,
    strain_limit: float,
    metric_tolerance: float,
) -> float | None:
    """Return the strictly admitted cell distance used for scoring.

    Correspondence enumeration uses ``metric_tolerance`` as a numerical
    search slack.  Final primitive candidates must still satisfy the declared
    physical strain limit.  A tolerance-only correspondence is therefore
    discarded here rather than promoted into a scientific match.

    At an exact zero strain limit, roundoff can leave a dimensionless residual
    of a few machine epsilons after the primitive build gauge is reconstructed.
    Such a residual is numerically indistinguishable from zero and must score
    as zero instead of producing ``inf`` through division by a zero maximum.
    """

    roundoff_slack = 64.0 * np.finfo(float).eps * max(1.0, strain_limit)
    maximum_strain = ai_strain.max_abs_principal_strain
    if maximum_strain <= strain_limit + roundoff_slack:
        if strain_limit == 0.0:
            return 0.0
        return ai_strain.d_cell

    search_slack = (
        64.0
        * np.finfo(float).eps
        * max(
            1.0,
            strain_limit + metric_tolerance,
        )
    )
    numerical_search_limit = strain_limit + metric_tolerance + search_slack
    if maximum_strain <= numerical_search_limit:
        return None
    raise RuntimeError("primitive metrics violate the correspondence enumeration bound")


def _matrix_key(matrix: np.ndarray) -> tuple[int, ...]:
    return tuple(int(value) for value in np.asarray(matrix).ravel())


def _candidate_rank(candidate: PrimitiveMatchCandidate2D) -> tuple[object, ...]:
    provenance = candidate.source_provenance
    return (
        float(candidate.match_score),
        float(candidate.ai_strain.d_cell),
        int(candidate.atom_count),
        float(candidate.d_size),
        candidate.pair_canonicalization.key,
        _source_index_pair(candidate),
        int(provenance.repeat_index),
        _matrix_key(provenance.source_H_A),
        _matrix_key(provenance.source_H_B),
        _matrix_key(provenance.source_N_A),
        _matrix_key(provenance.source_N_B),
        _matrix_key(provenance.correspondence_U_B),
    )


def _class_rank(match_class: PrimitiveMatchClass2D) -> tuple[object, ...]:
    return (*_candidate_rank(match_class.representative), match_class.pair_key)


def _alignment_gauge(basis: np.ndarray) -> np.ndarray:
    """Return an orthogonal gauge aligning a right-handed build basis."""

    matrix = np.asarray(basis, dtype=float)
    if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
        raise RuntimeError("build basis must be a finite 2x2 matrix")
    first = matrix[:, 0]
    length = float(np.linalg.norm(first))
    if not np.isfinite(length) or length <= 0.0:
        raise RuntimeError("build basis must have a nonzero first vector")
    rotation = np.array(
        [
            [first[0] / length, first[1] / length],
            [-first[1] / length, first[0] / length],
        ],
        dtype=float,
    )
    if not np.allclose(rotation.T @ rotation, np.eye(2), atol=1e-12, rtol=1e-12):
        raise RuntimeError("build alignment rotation is not orthogonal")
    if float(np.linalg.det(matrix)) < 0.0:
        rotation = np.diag([1.0, -1.0]) @ rotation
    determinant = float(np.linalg.det(rotation))
    if not np.isclose(abs(determinant), 1.0, atol=1e-12, rtol=1e-12):
        raise RuntimeError("build alignment gauge has invalid determinant")
    if float(np.linalg.det(rotation @ matrix)) <= 0.0:
        raise RuntimeError("build alignment gauge must produce a right-handed basis")
    return rotation


def _common_right_build(
    primitive_matrix: np.ndarray,
    *,
    basis_a: np.ndarray,
    basis_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return one symmetric common-right primitive build gauge.

    The common integer basis is selected by reducing the affine-invariant
    midpoint of the two primitive physical metrics.  The same proper right
    transform is then applied to both integer blocks.  Independent orthogonal
    Cartesian gauges fix deterministic right-handed embeddings; a reflection
    appears only for an explicitly orientation-reversed correspondence.
    """

    primitive = np.asarray(primitive_matrix, dtype=int)
    primitive_a = primitive[:2, :]
    primitive_b = primitive[2:, :]
    physical_a = np.asarray(basis_a, dtype=float) @ primitive_a
    physical_b = np.asarray(basis_b, dtype=float) @ primitive_b
    gram_a = physical_a.T @ physical_a
    gram_b = physical_b.T @ physical_b
    metric_scale = max(
        float(np.max(np.abs(gram_a))),
        float(np.max(np.abs(gram_b))),
    )
    if not np.isfinite(metric_scale) or metric_scale <= 0.0:
        raise RuntimeError("primitive physical metrics must have finite positive scale")
    midpoint = geodesic_spd(
        gram_a / metric_scale,
        gram_b / metric_scale,
        0.5,
    )
    midpoint_basis = cholesky2_spd(midpoint, upper=True)
    _reduced, right, _embedding = oriented_gauss_reduce_2d(midpoint_basis)
    right = np.asarray(right, dtype=int)
    if _determinant_2d(right) != 1:
        raise RuntimeError("common build transform must have determinant +1")

    build = primitive @ right
    build_a = build[:2, :]
    build_b = build[2:, :]
    rotation_a = _alignment_gauge(np.asarray(basis_a, dtype=float) @ build_a)
    rotation_b = _alignment_gauge(np.asarray(basis_b, dtype=float) @ build_b)
    return build, right, rotation_a, rotation_b


def _primitive_atom_count(
    primitive_matrix: np.ndarray,
    *,
    n_a: int,
    n_b: int,
) -> int:
    determinant_a = abs(_determinant_2d(primitive_matrix[:2, :]))
    determinant_b = abs(_determinant_2d(primitive_matrix[2:, :]))
    if determinant_a <= 0 or determinant_b <= 0:
        raise RuntimeError("primitive pair blocks must both have full rank")
    return determinant_a * n_a + determinant_b * n_b


@dataclass(frozen=True)
class _CandidateGeometry2D:
    """Primitive-pair geometry shared by every repeated source witness."""

    primitive_matrix: np.ndarray
    build_matrix: np.ndarray
    build_right: np.ndarray
    build_r_a: np.ndarray
    build_r_b: np.ndarray
    ai_strain: AffineInvariantStrain2D
    zm_strain: ZMStrain2D
    atom_count: int
    d_size: float
    match_score: float


def _build_candidate_geometry(
    *,
    primitive_matrix: np.ndarray,
    basis_a: np.ndarray,
    basis_b: np.ndarray,
    n_a: int,
    n_b: int,
    atom_limit: int,
    strain_limit: float,
    metric_tolerance: float,
    weight: float,
    d_size_max: float,
) -> _CandidateGeometry2D | None:
    """Build translation-independent geometry once per primitive pair."""

    primitive = np.asarray(primitive_matrix, dtype=int)
    atom_count = _primitive_atom_count(
        primitive,
        n_a=n_a,
        n_b=n_b,
    )
    if atom_count > atom_limit:
        return None

    build_matrix, build_right, build_r_a, build_r_b = _common_right_build(
        primitive,
        basis_a=basis_a,
        basis_b=basis_b,
    )
    build_n_a = build_matrix[:2, :]
    build_n_b = build_matrix[2:, :]
    physical_a = build_r_a @ (np.asarray(basis_a, dtype=float) @ build_n_a)
    physical_b = build_r_b @ (np.asarray(basis_b, dtype=float) @ build_n_b)
    gram_a = physical_a.T @ physical_a
    gram_b = physical_b.T @ physical_b
    metric_scale = max(
        float(np.max(np.abs(gram_a))),
        float(np.max(np.abs(gram_b))),
    )
    if not np.isfinite(metric_scale) or metric_scale <= 0.0:
        raise RuntimeError("primitive physical metrics must have finite positive scale")
    ai_strain = AffineInvariantStrain2D.from_grams(
        gram_a / metric_scale,
        gram_b / metric_scale,
    )
    admitted_d_cell = _admitted_d_cell_for_scoring(
        ai_strain,
        strain_limit=strain_limit,
        metric_tolerance=metric_tolerance,
    )
    if admitted_d_cell is None:
        return None

    d_size = _compute_d_size(float(atom_count), n_a, n_b)
    d_cell_max = 2.0 * np.sqrt(2.0) * strain_limit
    match_score = _compute_match_score(
        _normalize_d_cell(admitted_d_cell, d_cell_max),
        _normalize_d_size(d_size, d_size_max),
        weight,
    )
    zm_strain = ZMStrain2D.from_bases(physical_a, physical_b)
    return _CandidateGeometry2D(
        primitive_matrix=primitive,
        build_matrix=build_matrix,
        build_right=build_right,
        build_r_a=build_r_a,
        build_r_b=build_r_b,
        ai_strain=ai_strain,
        zm_strain=zm_strain,
        atom_count=atom_count,
        d_size=d_size,
        match_score=match_score,
    )


def _build_source_provenance(
    *,
    member_a: SurfaceCellMember2D,
    member_b: SurfaceCellMember2D,
    correspondence_u_b: np.ndarray,
    factorization: PrimitivePairFactorization2D,
) -> SourceMatchProvenance2D:
    """Materialize the exact source witness for one admitted correspondence."""

    source_n_a = np.array(member_a.oriented_N, dtype=int, copy=True)
    source_n_b = np.array(member_b.oriented_N, dtype=int, copy=True)
    correspondence = np.array(correspondence_u_b, dtype=int, copy=True)
    source_pair = np.vstack([source_n_a, source_n_b @ correspondence])
    return SourceMatchProvenance2D(
        source_H_A=np.array(member_a.H, dtype=int, copy=True),
        source_H_B=np.array(member_b.H, dtype=int, copy=True),
        source_orbit_key_A=member_a.surface_orbit_key,
        source_orbit_key_B=member_b.surface_orbit_key,
        source_N_A=source_n_a,
        source_N_B=source_n_b,
        correspondence_U_B=correspondence,
        source_pair_matrix=source_pair,
        source_right_factor=factorization.source_right_factor,
        repeat_index=factorization.repeat_index,
        maximal_minors=factorization.maximal_minors,
    )


def _candidate_rank_from_parts(
    *,
    geometry: _CandidateGeometry2D,
    pair_canonicalization: PairCanonicalization2D,
    provenance: SourceMatchProvenance2D,
) -> tuple[object, ...]:
    return (
        float(geometry.match_score),
        float(geometry.ai_strain.d_cell),
        int(geometry.atom_count),
        float(geometry.d_size),
        pair_canonicalization.key,
        _source_index_pair_from_provenance(provenance),
        int(provenance.repeat_index),
        _matrix_key(provenance.source_H_A),
        _matrix_key(provenance.source_H_B),
        _matrix_key(provenance.source_N_A),
        _matrix_key(provenance.source_N_B),
        _matrix_key(provenance.correspondence_U_B),
    )


def _build_candidate(
    *,
    geometry: _CandidateGeometry2D,
    provenance: SourceMatchProvenance2D,
    pair_canonicalization: PairCanonicalization2D,
    pair_identity_policy: PairIdentityPolicy2D,
    weight: float,
) -> PrimitiveMatchCandidate2D:
    """Materialize a candidate only when it can be a representative."""

    primitive_matrix = geometry.primitive_matrix
    build_matrix = geometry.build_matrix
    return PrimitiveMatchCandidate2D(
        primitive_N_A=primitive_matrix[:2, :],
        primitive_N_B=primitive_matrix[2:, :],
        build_N_A=build_matrix[:2, :],
        build_N_B=build_matrix[2:, :],
        build_common_right_transform=geometry.build_right,
        build_R_A=geometry.build_r_a,
        build_R_B=geometry.build_r_b,
        pair_canonicalization=pair_canonicalization,
        pair_identity_policy=pair_identity_policy,
        source_provenance=provenance,
        ai_strain=geometry.ai_strain,
        zm_strain=geometry.zm_strain,
        atom_count=geometry.atom_count,
        d_size=geometry.d_size,
        match_score=geometry.match_score,
        w_match=weight,
    )


def _consider_candidate(
    classes_by_key: dict[tuple[int, ...], PrimitiveMatchClass2D],
    representative_ranks: dict[tuple[int, ...], tuple[object, ...]],
    *,
    geometry: _CandidateGeometry2D,
    provenance: SourceMatchProvenance2D,
    pair_canonicalization: PairCanonicalization2D,
    pair_identity_policy: PairIdentityPolicy2D,
    weight: float,
) -> bool:
    pair_key = pair_canonicalization.key
    source_index_pair = _source_index_pair_from_provenance(provenance)
    repeat_index = provenance.repeat_index
    rank = _candidate_rank_from_parts(
        geometry=geometry,
        pair_canonicalization=pair_canonicalization,
        provenance=provenance,
    )
    match_class = classes_by_key.get(pair_key)
    if match_class is None:
        candidate = _build_candidate(
            geometry=geometry,
            provenance=provenance,
            pair_canonicalization=pair_canonicalization,
            pair_identity_policy=pair_identity_policy,
            weight=weight,
        )
        classes_by_key[pair_key] = PrimitiveMatchClass2D(
            pair_key=pair_key,
            representative=candidate,
            source_count=1,
            source_index_pairs={source_index_pair},
            repeat_indices={repeat_index},
        )
        representative_ranks[pair_key] = rank
        return True

    match_class.source_count += 1
    match_class.source_index_pairs.add(source_index_pair)
    match_class.repeat_indices.add(repeat_index)
    if rank < representative_ranks[pair_key]:
        match_class.representative = _build_candidate(
            geometry=geometry,
            provenance=provenance,
            pair_canonicalization=pair_canonicalization,
            pair_identity_policy=pair_identity_policy,
            weight=weight,
        )
        representative_ranks[pair_key] = rank
    return False


def _copy_surface_audit(
    audit: CoupledMatchEnumerationAudit,
    stats_a: dict[int, dict[str, int]],
    stats_b: dict[int, dict[str, int]],
) -> None:
    """Copy exact surface-orbit accounting into the coupled audit."""

    for k in range(1, audit.k_max + 1):
        for target, stats in (
            (audit.surface_A, stats_a),
            (audit.surface_B, stats_b),
        ):
            values = stats.get(k, {})
            target.hnf_generated[k - 1] = int(values.get("hnf_total", 0))
            target.reduction_failed[k - 1] = int(values.get("reduction_failed", 0))
            target.condition_rejected[k - 1] = int(values.get("condition_rejected", 0))
            target.admitted_members[k - 1] = int(values.get("generated_members", 0))
            target.comparison_orbits[k - 1] = int(values.get("orbit_count", 0))


def _prepared_correspondence_metric(
    metric: np.ndarray,
    *,
    metric_tolerance: float,
    cache: dict[tuple[str, ...], _PreparedCorrespondenceMetric2D],
) -> _PreparedCorrespondenceMetric2D:
    """Prepare one search-owned metric once from its exact float payload."""

    matrix = np.asarray(metric, dtype=float)
    key = (
        float(metric_tolerance).hex(),
        *(float(value).hex() for value in matrix.ravel()),
    )
    prepared = cache.get(key)
    if prepared is None:
        prepared = _prepare_correspondence_metric_2d(
            "correspondence metric",
            matrix,
            tolerance=metric_tolerance,
        )
        cache[key] = prepared
    return prepared


def _orbit_pair_prefilter_status(
    orbit_a: SurfaceCellOrbit2D,
    orbit_b: SurfaceCellOrbit2D,
    *,
    strain_limit: float,
    metric_tolerance: float,
    entry_limit: int | None,
    metric_cache: (
        dict[tuple[str, ...], _PreparedCorrespondenceMetric2D] | None
    ) = None,
) -> Literal["admitted", "rejected", "inconclusive"]:
    """Classify the optimization-only representative-shape prefilter."""

    cache = {} if metric_cache is None else metric_cache
    metric_a = _prepared_correspondence_metric(
        orbit_a.representative.shape_gram,
        metric_tolerance=metric_tolerance,
        cache=cache,
    )
    metric_b = _prepared_correspondence_metric(
        orbit_b.representative.shape_gram,
        metric_tolerance=metric_tolerance,
        cache=cache,
    )
    try:
        enumeration = _enumerate_basis_correspondence_records_prepared_2d(
            metric_a,
            metric_b,
            eps_principal_max=strain_limit,
            orientation="all",
            metric_tolerance=metric_tolerance,
            entry_limit=(
                _PREFILTER_CORRESPONDENCE_ENTRY_LIMIT
                if entry_limit is None
                else entry_limit
            ),
        )
    except CorrespondenceEnumerationLimitError:
        return "inconclusive"
    return "admitted" if enumeration.records else "rejected"


def _resolve_surface_groups(
    slab_a: Any,
    slab_b: Any,
    *,
    surface_symmetry_mode: str,
    surface_symprec: float,
    surface_angle_tolerance: float,
    surface_metric_tolerance: float,
) -> tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]:
    from calm.interface.matching._surface_symmetry import resolve_surface_pointgroup_2d

    resolution_a = resolve_surface_pointgroup_2d(
        slab_a,
        mode=surface_symmetry_mode,
        symprec=surface_symprec,
        angle_tolerance=surface_angle_tolerance,
        metric_tolerance=surface_metric_tolerance,
    )
    resolution_b = resolve_surface_pointgroup_2d(
        slab_b,
        mode=surface_symmetry_mode,
        symprec=surface_symprec,
        angle_tolerance=surface_angle_tolerance,
        metric_tolerance=surface_metric_tolerance,
    )
    return tuple(resolution_a.operations), tuple(resolution_b.operations)


@dataclass(frozen=True, slots=True)
class _CoupledMatchSearchPlan:
    """Validated search-wide inputs and catalogs for one coupled search."""

    n_a: int
    n_b: int
    k_max: int
    condition_limit: float
    weight: float
    strain_limit: float
    atom_limit: int
    metric_tolerance: float
    entry_limit: int | None
    policy: PairIdentityPolicy2D
    basis_a: np.ndarray
    basis_b: np.ndarray
    point_group_a: tuple[np.ndarray, ...]
    point_group_b: tuple[np.ndarray, ...]
    orbit_index_a: dict[int, tuple[SurfaceCellOrbit2D, ...]]
    orbit_index_b: dict[int, tuple[SurfaceCellOrbit2D, ...]]
    pair_identity_context: _PairIdentityContext2D
    d_size_max: float
    index_pairs: tuple[tuple[int, int], ...]


@dataclass(slots=True)
class _CoupledMatchSearchState:
    """Mutable aggregation and reuse state owned by one coupled search."""

    audit: CoupledMatchEnumerationAudit | None
    primitive_cache: dict[tuple[int, ...], PrimitivePairFactorization2D] = field(
        default_factory=dict
    )
    identity_cache: dict[tuple[int, ...], PairCanonicalization2D] = field(
        default_factory=dict
    )
    geometry_cache: dict[tuple[int, ...], _CandidateGeometry2D | None] = field(
        default_factory=dict
    )
    correspondence_metric_cache: dict[
        tuple[str, ...], _PreparedCorrespondenceMetric2D
    ] = field(default_factory=dict)
    classes_by_key: dict[tuple[int, ...], PrimitiveMatchClass2D] = field(
        default_factory=dict
    )
    representative_ranks: dict[tuple[int, ...], tuple[object, ...]] = field(
        default_factory=dict
    )
    admitted_source_count: int = 0


def _prepare_coupled_match_search(
    slab_a: Any,
    slab_b: Any,
    *,
    k_max: int,
    cond_max: float,
    w_match: float,
    eps_principal_max: float,
    n_at_max: int,
    reduction_kwargs: dict[str, Any] | None,
    surface_symmetry_mode: str,
    surface_symprec: float,
    surface_angle_tolerance: float,
    surface_metric_tolerance: float,
    pair_symmetry_policy: PairSymmetryPolicy,
    correspondence_orientation: CorrespondenceOrientation,
    identify_material_exchange: bool,
    correspondence_entry_limit: int | None,
    point_group_a: tuple[np.ndarray, ...] | None,
    point_group_b: tuple[np.ndarray, ...] | None,
    audit: CoupledMatchEnumerationAudit | None,
) -> tuple[_CoupledMatchSearchPlan, _CoupledMatchSearchState]:
    """Validate inputs and prepare every search-wide immutable object."""

    n_a = _positive_integer("slab_A.n_atoms", slab_a.n_atoms)
    n_b = _positive_integer("slab_B.n_atoms", slab_b.n_atoms)
    k_limit = _positive_integer("k_max", k_max)
    if audit is not None:
        if not isinstance(audit, CoupledMatchEnumerationAudit):
            raise TypeError("audit must be a CoupledMatchEnumerationAudit")
        if audit.k_max != k_limit:
            raise ValueError("audit.k_max must equal k_max")

    condition_limit = _finite_positive_float("cond_max", cond_max)
    weight = _unit_interval_float("w_match", w_match)
    strain_limit = _finite_nonnegative_float("eps_principal_max", eps_principal_max)
    atom_limit = _positive_integer("N_at_max", n_at_max)
    metric_tolerance = _finite_nonnegative_float(
        "surface_metric_tolerance", surface_metric_tolerance
    )
    entry_limit = (
        None
        if correspondence_entry_limit is None
        else _positive_integer("correspondence_entry_limit", correspondence_entry_limit)
    )
    if reduction_kwargs is not None and not isinstance(reduction_kwargs, dict):
        raise TypeError("reduction_kwargs must be a dictionary or None")
    policy = _validate_policy(
        pair_symmetry_policy=pair_symmetry_policy,
        correspondence_orientation=correspondence_orientation,
        identify_material_exchange=identify_material_exchange,
    )

    basis_a, area_a = _prim_inplane_basis_2d(slab_a)
    basis_b, area_b = _prim_inplane_basis_2d(slab_b)
    if (point_group_a is None) != (point_group_b is None):
        raise ValueError("point_group_A and point_group_B must be supplied together")
    if point_group_a is None:
        group_a, group_b = _resolve_surface_groups(
            slab_a,
            slab_b,
            surface_symmetry_mode=surface_symmetry_mode,
            surface_symprec=surface_symprec,
            surface_angle_tolerance=surface_angle_tolerance,
            surface_metric_tolerance=metric_tolerance,
        )
    else:
        group_a = tuple(np.asarray(operation, dtype=int) for operation in point_group_a)
        group_b = tuple(np.asarray(operation, dtype=int) for operation in point_group_b)

    surface_context_a = _prepare_surface_orbit_build_context_2d(
        prim_basis=basis_a,
        PG_ops=group_a,
        cond_max=condition_limit,
        reduction_kwargs=reduction_kwargs,
    )
    surface_context_b = _prepare_surface_orbit_build_context_2d(
        prim_basis=basis_b,
        PG_ops=group_b,
        cond_max=condition_limit,
        reduction_kwargs=reduction_kwargs,
    )
    surface_stats_a: dict[int, dict[str, int]] = {}
    surface_stats_b: dict[int, dict[str, int]] = {}
    orbit_index_a = _build_surface_cell_orbit_index_prepared(
        context=surface_context_a,
        k_max=k_limit,
        stats=surface_stats_a if audit is not None else None,
    )
    if surface_context_a.key == surface_context_b.key:
        orbit_index_b = orbit_index_a
        if audit is not None:
            surface_stats_b = {
                index: dict(values) for index, values in surface_stats_a.items()
            }
    else:
        orbit_index_b = _build_surface_cell_orbit_index_prepared(
            context=surface_context_b,
            k_max=k_limit,
            stats=surface_stats_b if audit is not None else None,
        )
    if audit is not None:
        _copy_surface_audit(audit, surface_stats_a, surface_stats_b)

    pair_identity_context = _prepare_pair_identity_context_2d(
        point_group_A=group_a,
        point_group_B=group_b,
        policy=policy,
    )
    index_pairs_array = compute_valid_hnf_index_pairs(
        area_a,
        area_b,
        k_limit,
        k_limit,
        strain_limit,
    )
    index_pairs = tuple((int(k_a), int(k_b)) for k_a, k_b in index_pairs_array)
    if audit is not None:
        valid_index_pairs = set(index_pairs)
        for k_a in range(1, k_limit + 1):
            for k_b in range(1, k_limit + 1):
                if (k_a, k_b) not in valid_index_pairs:
                    audit.pairs.increment(
                        max(k_a, k_b),
                        "area_bound_rejected",
                    )

        member_counts_a = {
            k: sum(len(orbit.members) for orbit in orbit_index_a.get(k, ()))
            for k in range(1, k_limit + 1)
        }
        member_counts_b = {
            k: sum(len(orbit.members) for orbit in orbit_index_b.get(k, ()))
            for k in range(1, k_limit + 1)
        }
        surface_a_totals = audit.surface_A.totals()
        surface_b_totals = audit.surface_B.totals()
        area_admissible_hnf_pairs = sum(
            member_counts_a[k_a] * member_counts_b[k_b]
            for k_a, k_b in index_pairs
        )
        atom_lower_bound_admissible_hnf_pairs = sum(
            member_counts_a[k_a] * member_counts_b[k_b]
            for k_a, k_b in index_pairs
            if _safe_atom_lower_bound(k_a, k_b, n_a, n_b) <= atom_limit
        )
        audit.search_space = CoupledSearchSpaceCounts(
            raw_hnf_pairs=(
                surface_a_totals["hnf_generated"]
                * surface_b_totals["hnf_generated"]
            ),
            searchable_hnf_pairs=(
                surface_a_totals["admitted_members"]
                * surface_b_totals["admitted_members"]
            ),
            area_admissible_hnf_pairs=area_admissible_hnf_pairs,
            atom_lower_bound_admissible_hnf_pairs=(
                atom_lower_bound_admissible_hnf_pairs
            ),
            orbit_prefilter_surviving_hnf_pairs=0,
        )

    plan = _CoupledMatchSearchPlan(
        n_a=n_a,
        n_b=n_b,
        k_max=k_limit,
        condition_limit=condition_limit,
        weight=weight,
        strain_limit=strain_limit,
        atom_limit=atom_limit,
        metric_tolerance=metric_tolerance,
        entry_limit=entry_limit,
        policy=policy,
        basis_a=basis_a,
        basis_b=basis_b,
        point_group_a=group_a,
        point_group_b=group_b,
        orbit_index_a=orbit_index_a,
        orbit_index_b=orbit_index_b,
        pair_identity_context=pair_identity_context,
        d_size_max=_compute_d_size(float(atom_limit), n_a, n_b),
        index_pairs=index_pairs,
    )
    return plan, _CoupledMatchSearchState(audit=audit)


def _traverse_orbit_pair(
    plan: _CoupledMatchSearchPlan,
    state: _CoupledMatchSearchState,
    *,
    orbit_a: SurfaceCellOrbit2D,
    orbit_b: SurfaceCellOrbit2D,
    audit_k: int,
) -> None:
    """Traverse one admitted surface-orbit pair and aggregate its sources."""

    audit = state.audit
    metric_cache = state.correspondence_metric_cache
    strain_limit = plan.strain_limit
    metric_tolerance = plan.metric_tolerance
    entry_limit = plan.entry_limit
    policy = plan.policy
    n_a = plan.n_a
    n_b = plan.n_b
    atom_limit = plan.atom_limit
    basis_a = plan.basis_a
    basis_b = plan.basis_b
    weight = plan.weight
    d_size_max = plan.d_size_max
    pair_identity_context = plan.pair_identity_context
    if audit is not None:
        audit.pairs.increment(audit_k, "orbit_pairs_considered")
    prefilter_status = _orbit_pair_prefilter_status(
        orbit_a,
        orbit_b,
        strain_limit=strain_limit,
        metric_tolerance=metric_tolerance,
        entry_limit=entry_limit,
        metric_cache=metric_cache,
    )
    if audit is not None:
        audit.pairs.increment(
            audit_k,
            f"orbit_prefilter_{prefilter_status}",
        )
    if prefilter_status == "rejected":
        return

    primitive_cache = state.primitive_cache
    identity_cache = state.identity_cache
    geometry_cache = state.geometry_cache
    classes_by_key = state.classes_by_key
    representative_ranks = state.representative_ranks
    policy = plan.policy

    for member_a in orbit_a.members:
        for member_b in orbit_b.members:
            correspondence_stats: dict[str, int] = {}
            if audit is not None:
                audit.pairs.increment(audit_k, "member_pairs_expanded")
                audit.pairs.increment(audit_k, "correspondence_domains")
            metric_a = _prepared_correspondence_metric(
                member_a.oriented_gram,
                metric_tolerance=metric_tolerance,
                cache=metric_cache,
            )
            metric_b = _prepared_correspondence_metric(
                member_b.oriented_gram,
                metric_tolerance=metric_tolerance,
                cache=metric_cache,
            )
            try:
                enumeration = _enumerate_basis_correspondence_records_prepared_2d(
                    metric_a,
                    metric_b,
                    eps_principal_max=plan.strain_limit,
                    orientation=policy.correspondence_orientation,
                    metric_tolerance=metric_tolerance,
                    entry_limit=entry_limit,
                    stats=(correspondence_stats if audit is not None else None),
                )
            except CorrespondenceEnumerationLimitError:
                if audit is not None:
                    audit.pairs.increment(
                        audit_k,
                        "correspondence_limit_failures",
                    )
                raise
            if audit is not None:
                audit.pairs.increment(
                    audit_k,
                    "correspondence_column_pairs_tested",
                    correspondence_stats["column_pairs_tested"],
                )
                audit.pairs.increment(
                    audit_k,
                    "unimodular_correspondences_tested",
                    correspondence_stats["unimodular_states_tested"],
                )
                audit.pairs.increment(
                    audit_k,
                    "strain_admissible_correspondences",
                    correspondence_stats["strain_admissible_states"],
                )

            for transform_key, enumerated_strains in enumeration.records:
                correspondence_u_b = np.asarray(
                    transform_key,
                    dtype=int,
                ).reshape(2, 2)
                source_pair = np.vstack(
                    [
                        member_a.oriented_N,
                        member_b.oriented_N @ correspondence_u_b,
                    ]
                ).astype(int)
                source_key = _matrix_key(source_pair)
                factorization = primitive_cache.get(source_key)
                if factorization is None:
                    factorization = primitiveize_pair_matrix_2d(source_pair)
                    primitive_cache[source_key] = factorization
                    if audit is not None:
                        audit.pairs.increment(
                            audit_k,
                            "unique_source_pairs_primitiveized",
                        )
                elif audit is not None:
                    audit.pairs.increment(
                        audit_k,
                        "primitiveization_cache_hits",
                    )
                if audit is not None and factorization.repeat_index > 1:
                    audit.pairs.increment(
                        audit_k,
                        "nonprimitive_repetitions",
                    )

                primitive_matrix = np.asarray(
                    factorization.primitive_matrix,
                    dtype=int,
                )
                if (
                    _primitive_atom_count(
                        primitive_matrix,
                        n_a=n_a,
                        n_b=n_b,
                    )
                    > atom_limit
                ):
                    if audit is not None:
                        audit.pairs.increment(
                            audit_k,
                            "primitive_atom_rejected",
                        )
                    continue

                primitive_key = _matrix_key(primitive_matrix)
                pair_canonicalization = identity_cache.get(primitive_key)
                if pair_canonicalization is None:
                    pair_canonicalization = _canonicalize_primitive_pair_tuple_2d(
                        primitive_key,
                        context=pair_identity_context,
                    )
                    identity_cache[primitive_key] = pair_canonicalization

                if primitive_key not in geometry_cache:
                    geometry_cache[primitive_key] = _build_candidate_geometry(
                        primitive_matrix=primitive_matrix,
                        basis_a=basis_a,
                        basis_b=basis_b,
                        n_a=n_a,
                        n_b=n_b,
                        atom_limit=atom_limit,
                        strain_limit=strain_limit,
                        metric_tolerance=metric_tolerance,
                        weight=weight,
                        d_size_max=d_size_max,
                    )
                geometry = geometry_cache[primitive_key]
                if geometry is None:
                    if audit is not None:
                        audit.pairs.increment(
                            audit_k,
                            "strict_strain_rejected",
                        )
                    continue

                provenance = _build_source_provenance(
                    member_a=member_a,
                    member_b=member_b,
                    correspondence_u_b=correspondence_u_b,
                    factorization=factorization,
                )
                if audit is not None:
                    audit.pairs.increment(audit_k, "candidates_admitted")
                audit_index = state.admitted_source_count
                state.admitted_source_count += 1
                if _admitted_match_trace_is_active():
                    _emit_admitted_match_record(
                        _build_admitted_match_record(
                            audit_index=audit_index,
                            audit_k=audit_k,
                            basis_A=basis_a,
                            basis_B=basis_b,
                            n_atoms_A=n_a,
                            n_atoms_B=n_b,
                            member_A=member_a,
                            member_B=member_b,
                            enumerated_principal_log_strains=enumerated_strains,
                            geometry=geometry,
                            provenance=provenance,
                            pair_canonicalization=pair_canonicalization,
                            pair_identity_policy=policy,
                        )
                    )
                class_created = _consider_candidate(
                    classes_by_key,
                    representative_ranks,
                    geometry=geometry,
                    provenance=provenance,
                    pair_canonicalization=pair_canonicalization,
                    pair_identity_policy=policy,
                    weight=weight,
                )
                if audit is not None:
                    audit.pairs.increment(
                        audit_k,
                        (
                            "primitive_classes_created"
                            if class_created
                            else "sources_aggregated_by_pair_key"
                        ),
                    )


def _traverse_scheduled_index_pair(
    plan: _CoupledMatchSearchPlan,
    state: _CoupledMatchSearchState,
    *,
    k_a: int,
    k_b: int,
) -> None:
    """Traverse one area-admitted pair of HNF indices."""

    audit = state.audit
    audit_k = max(k_a, k_b)
    if audit is not None:
        audit.pairs.increment(audit_k, "index_pairs_scheduled")
    if _safe_atom_lower_bound(k_a, k_b, plan.n_a, plan.n_b) > plan.atom_limit:
        if audit is not None:
            audit.pairs.increment(audit_k, "atom_lower_bound_rejected")
        return

    for orbit_a in plan.orbit_index_a.get(k_a, ()):
        for orbit_b in plan.orbit_index_b.get(k_b, ()):
            _traverse_orbit_pair(
                plan,
                state,
                orbit_a=orbit_a,
                orbit_b=orbit_b,
                audit_k=audit_k,
            )


def _finalize_coupled_match_search(
    state: _CoupledMatchSearchState,
) -> list[PrimitiveMatchClass2D]:
    """Return deterministically ordered classes and validate audit accounting."""

    classes = list(state.classes_by_key.values())
    classes.sort(key=_class_rank)
    if state.audit is not None:
        search_space = state.audit.search_space
        if search_space is None:
            raise RuntimeError(
                "coupled matcher did not prepare search-space accounting"
            )
        pair_totals = state.audit.pairs.totals()
        state.audit.search_space = CoupledSearchSpaceCounts(
            raw_hnf_pairs=search_space.raw_hnf_pairs,
            searchable_hnf_pairs=search_space.searchable_hnf_pairs,
            area_admissible_hnf_pairs=search_space.area_admissible_hnf_pairs,
            atom_lower_bound_admissible_hnf_pairs=(
                search_space.atom_lower_bound_admissible_hnf_pairs
            ),
            orbit_prefilter_surviving_hnf_pairs=pair_totals[
                "member_pairs_expanded"
            ],
        )
        admitted_primitive_keys = {
            key
            for key, geometry in state.geometry_cache.items()
            if geometry is not None
        }
        admitted_source_count = sum(
            1
            for factorization in state.primitive_cache.values()
            if _matrix_key(factorization.primitive_matrix)
            in admitted_primitive_keys
        )
        common_right_keys = {
            _canonicalize_common_right_rank2_tuple(key).key
            for key in admitted_primitive_keys
        }
        state.audit.identity_reduction = CoupledIdentityReductionCounts(
            admitted_descriptions=pair_totals["candidates_admitted"],
            unique_admitted_source_pairs=admitted_source_count,
            unique_admitted_primitive_pairs=len(admitted_primitive_keys),
            unique_admitted_common_right_classes=len(common_right_keys),
            unique_final_pair_classes=len(classes),
        )
        state.audit.validate()
    return classes


def enumerate_coupled_match_classes_core(
    slab_A: Any,
    slab_B: Any,
    *,
    k_max: int = 10,
    cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT,
    w_match: float = 1.0,
    eps_principal_max: float = 0.15,
    N_at_max: int = 1000,
    reduction_kwargs: dict[str, Any] | None = None,
    surface_symmetry_mode: str = "discover",
    surface_symprec: float = 1e-5,
    surface_angle_tolerance: float = 1e-8,
    surface_metric_tolerance: float = 1e-5,
    pair_symmetry_policy: PairSymmetryPolicy = DEFAULT_PAIR_SYMMETRY_POLICY,
    correspondence_orientation: CorrespondenceOrientation = (
        DEFAULT_CORRESPONDENCE_ORIENTATION
    ),
    identify_material_exchange: bool = DEFAULT_IDENTIFY_MATERIAL_EXCHANGE,
    correspondence_entry_limit: int | None = DEFAULT_CORRESPONDENCE_ENTRY_LIMIT,
    point_group_A: tuple[np.ndarray, ...] | None = None,
    point_group_B: tuple[np.ndarray, ...] | None = None,
    audit: CoupledMatchEnumerationAudit | None = None,
) -> list[PrimitiveMatchClass2D]:
    """Enumerate complete primitive coupled-pair classes in the finite domain."""

    plan, state = _prepare_coupled_match_search(
        slab_A,
        slab_B,
        k_max=k_max,
        cond_max=cond_max,
        w_match=w_match,
        eps_principal_max=eps_principal_max,
        n_at_max=N_at_max,
        reduction_kwargs=reduction_kwargs,
        surface_symmetry_mode=surface_symmetry_mode,
        surface_symprec=surface_symprec,
        surface_angle_tolerance=surface_angle_tolerance,
        surface_metric_tolerance=surface_metric_tolerance,
        pair_symmetry_policy=pair_symmetry_policy,
        correspondence_orientation=correspondence_orientation,
        identify_material_exchange=identify_material_exchange,
        correspondence_entry_limit=correspondence_entry_limit,
        point_group_a=point_group_A,
        point_group_b=point_group_B,
        audit=audit,
    )
    if _search_context_trace_is_active():
        _emit_search_context(_build_search_trace_context(plan))
    for k_a, k_b in plan.index_pairs:
        _traverse_scheduled_index_pair(
            plan,
            state,
            k_a=k_a,
            k_b=k_b,
        )
    return _finalize_coupled_match_search(state)


__all__ = [
    "CorrespondenceOrientation",
    "PairSymmetryPolicy",
    "enumerate_coupled_match_classes_core",
]
