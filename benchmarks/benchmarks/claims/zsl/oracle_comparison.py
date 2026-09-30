"""C7 controlled pymatgen ZSL comparison against finite CALM oracles.

The stage preserves every external source record, reconstructs its integer
source transformations, evaluates mechanical diagnostics on the retained ZSL
vector correspondence, and projects the source pair onto CALM's declared
primitive coupled-pair identity.  ZSL is an external comparator, not a CALM
correctness oracle; the claim disposition is therefore descriptive whenever
CALM's internal oracle guards pass.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ...benchmark_pairs import LatticePair2D, basis_to_3d_vectors
from .._support import (
    key_text,
    slab_from_basis,
    write_canonical_jsonl_atomic,
    write_csv_atomic,
)
from ..claim_ids import ClaimId, ClaimStatus
from ..differential_search import DifferentialFixture, default_differential_fixtures
from ..manifest import (
    artifact_record,
    build_manifest,
    canonical_json_bytes,
    write_json_atomic,
)
from ..reference.coupled_match_reference import (
    Matrix2,
    enumerate_metric_point_group,
    exhaustive_reference_search,
)
from ..schemas import (
    ZSL_ORACLE_COMPARISON_SCHEMA,
    ZSL_ORACLE_FIXTURE_SCHEMA,
    ZSL_ORACLE_KEY_OBSERVATION_SCHEMA,
    ZSL_ORACLE_SUMMARY_SCHEMA,
    ClaimResult,
    ProjectedMatch,
    RawExternalMatch,
)
from .raw_adapter import capture_raw_zsl_match
from .source_capture import (
    GeneratorFactory,
    call_zsl_generator,
    default_generator_factory,
    pymatgen_version,
)
from .transformation_reconstruction import reconstruct_zsl_source_pair


DEFAULT_PROFILE = "standard"
SUPPORTED_PROFILES = ("smoke", "standard")
DEFAULT_EXACT_STRAIN_TOLERANCE = 1.0e-10
DEFAULT_COMMON_STRAIN_LIMIT = 0.03
DEFAULT_LENGTH_TOLERANCE = 0.03
DEFAULT_ANGLE_TOLERANCE = 0.01
DEFAULT_AREA_RATIO_TOLERANCE = 0.09
DEFAULT_RECONSTRUCTION_TOLERANCE = 1.0e-8
DEFAULT_CONDITION_LIMIT = 1.0e9
DEFAULT_ATOM_LIMIT = 100_000
DEFAULT_DIRECTIONALITY = "both"
SUPPORTED_DIRECTIONALITIES = ("unidirectional", "bidirectional", "both")


@dataclass(frozen=True)
class ZSLOracleCase:
    """One finite exact fixture and comparison bound."""

    case_id: str
    fixture: DifferentialFixture
    k_max: int
    oracle_kind: str
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must be nonempty")
        if self.k_max <= 0:
            raise ValueError("k_max must be positive")
        if self.oracle_kind not in {
            "independent_exact_rational_reference_v1",
            "frozen_equal_square_full_d4_k30_v1",
        }:
            raise ValueError(f"unsupported oracle_kind {self.oracle_kind!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ZSL_ORACLE_FIXTURE_SCHEMA,
            "case_id": self.case_id,
            "fixture": self.fixture.to_dict(),
            "fixture_sha256": self.fixture.sha256(),
            "k_max": self.k_max,
            "oracle_kind": self.oracle_kind,
            "tags": list(self.tags),
        }

    def sha256(self) -> str:
        payload = {
            "schema": ZSL_ORACLE_FIXTURE_SCHEMA,
            "case_id": self.case_id,
            "fixture_sha256": self.fixture.sha256(),
            "k_max": self.k_max,
            "oracle_kind": self.oracle_kind,
            "tags": list(self.tags),
        }
        return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True)
class ZSLOracleComparisonConfig:
    """Configuration for the C7 controlled external comparison."""

    profile: str = DEFAULT_PROFILE
    case_ids: tuple[str, ...] = ()
    k_max_override: int | None = None
    directionality: str = DEFAULT_DIRECTIONALITY
    max_area_ratio_tol: float = DEFAULT_AREA_RATIO_TOLERANCE
    max_length_tol: float = DEFAULT_LENGTH_TOLERANCE
    max_angle_tol: float = DEFAULT_ANGLE_TOLERANCE
    exact_strain_tolerance: float = DEFAULT_EXACT_STRAIN_TOLERANCE
    common_strain_limit: float = DEFAULT_COMMON_STRAIN_LIMIT
    reconstruction_atol: float = DEFAULT_RECONSTRUCTION_TOLERANCE
    reconstruction_rtol: float = DEFAULT_RECONSTRUCTION_TOLERANCE
    cond_max: float = DEFAULT_CONDITION_LIMIT
    atom_limit: int = DEFAULT_ATOM_LIMIT

    def __post_init__(self) -> None:
        if self.profile not in SUPPORTED_PROFILES:
            raise ValueError(f"profile must be one of {SUPPORTED_PROFILES}")
        if self.directionality not in SUPPORTED_DIRECTIONALITIES:
            raise ValueError(
                f"directionality must be one of {SUPPORTED_DIRECTIONALITIES}"
            )
        if self.k_max_override is not None and self.k_max_override <= 0:
            raise ValueError("k_max_override must be positive or None")
        for name in (
            "max_area_ratio_tol",
            "max_length_tol",
            "max_angle_tol",
            "exact_strain_tolerance",
            "common_strain_limit",
            "reconstruction_atol",
            "reconstruction_rtol",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.common_strain_limit < self.exact_strain_tolerance:
            raise ValueError(
                "common_strain_limit must be at least exact_strain_tolerance"
            )
        if not math.isfinite(self.cond_max) or self.cond_max <= 0:
            raise ValueError("cond_max must be finite and positive")
        if self.atom_limit <= 0:
            raise ValueError("atom_limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "case_ids": list(self.case_ids),
            "k_max_override": self.k_max_override,
            "directionality": self.directionality,
            "max_area_ratio_tol": self.max_area_ratio_tol,
            "max_length_tol": self.max_length_tol,
            "max_angle_tol": self.max_angle_tol,
            "exact_strain_tolerance": self.exact_strain_tolerance,
            "common_strain_limit": self.common_strain_limit,
            "reconstruction_atol": self.reconstruction_atol,
            "reconstruction_rtol": self.reconstruction_rtol,
            "cond_max": self.cond_max,
            "atom_limit": self.atom_limit,
            "pair_symmetry_policy": "full",
            "correspondence_orientation": "proper",
            "identify_material_exchange": False,
            "comparison_semantics": {
                "oracle_overlap_gate": "exact principal strain",
                "descriptive_population_gate": "common 3% principal strain",
                "identity": "CALM primitive coupled-pair projection",
                "source_bound": "both reconstructed source indices <= k_max",
            },
        }


@dataclass(frozen=True)
class ZSLOracleComparisonArtifacts:
    manifest: Path
    claim_result: Path
    summary: Path
    summary_csv: Path
    comparisons: Path
    key_observations: Path
    raw_matches: Path
    reconstructions: Path
    metric_projections: Path
    coupled_projections: Path
    result: ClaimResult

    @property
    def evidence_paths(self) -> tuple[Path, ...]:
        return (
            self.summary,
            self.summary_csv,
            self.comparisons,
            self.key_observations,
            self.raw_matches,
            self.reconstructions,
            self.metric_projections,
            self.coupled_projections,
        )


def default_zsl_oracle_cases() -> tuple[ZSLOracleCase, ...]:
    """Return the deterministic C7 fixture matrix."""

    fixtures = {item.fixture_id: item for item in default_differential_fixtures()}
    return (
        ZSLOracleCase(
            case_id="equal_square_k5",
            fixture=fixtures["square_standard"],
            k_max=5,
            oracle_kind="independent_exact_rational_reference_v1",
            tags=("equal_square", "sigma5", "small_oracle"),
        ),
        ZSLOracleCase(
            case_id="equal_square_k30",
            fixture=fixtures["square_standard"],
            k_max=30,
            oracle_kind="frozen_equal_square_full_d4_k30_v1",
            tags=("equal_square", "publication_oracle", "six_classes"),
        ),
        ZSLOracleCase(
            case_id="equal_rectangular_k5",
            fixture=fixtures["rectangular_standard"],
            k_max=5,
            oracle_kind="independent_exact_rational_reference_v1",
            tags=("rectangular", "small_oracle"),
        ),
        ZSLOracleCase(
            case_id="equal_hexagonal_k4",
            fixture=fixtures["hexagonal_standard"],
            k_max=4,
            oracle_kind="independent_exact_rational_reference_v1",
            tags=("hexagonal", "small_oracle"),
        ),
        ZSLOracleCase(
            case_id="equal_oblique_k5",
            fixture=fixtures["oblique_standard"],
            k_max=5,
            oracle_kind="independent_exact_rational_reference_v1",
            tags=("oblique", "small_oracle"),
        ),
    )


SMOKE_CASE_IDS = ("equal_square_k5", "equal_rectangular_k5")


def select_zsl_oracle_cases(
    config: ZSLOracleComparisonConfig,
) -> tuple[ZSLOracleCase, ...]:
    cases = default_zsl_oracle_cases()
    by_id = {case.case_id: case for case in cases}
    if config.case_ids:
        unknown = sorted(set(config.case_ids) - set(by_id))
        if unknown:
            raise ValueError(f"unknown ZSL oracle cases: {unknown}")
        selected = tuple(by_id[item] for item in dict.fromkeys(config.case_ids))
    elif config.profile == "smoke":
        selected = tuple(by_id[item] for item in SMOKE_CASE_IDS)
    else:
        selected = cases
    if config.k_max_override is None:
        return selected
    return tuple(
        ZSLOracleCase(
            case_id=case.case_id,
            fixture=case.fixture,
            k_max=config.k_max_override,
            oracle_kind=(
                "frozen_equal_square_full_d4_k30_v1"
                if case.fixture.fixture_id == "square_standard"
                and config.k_max_override <= 30
                and config.k_max_override > 5
                else "independent_exact_rational_reference_v1"
            ),
            tags=case.tags + ("k_max_override",),
        )
        for case in selected
    )


def _directionality_modes(config: ZSLOracleComparisonConfig) -> tuple[bool, ...]:
    if config.directionality == "unidirectional":
        return (False,)
    if config.directionality == "bidirectional":
        return (True,)
    return (False, True)


def _key_tuple(value: Sequence[Any]) -> tuple[int, ...]:
    return tuple(int(item) for item in value)


def _key_digest(keys: Iterable[Sequence[int]]) -> str:
    payload = sorted(_key_tuple(key) for key in keys)
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def _production_inventory(
    case: ZSLOracleCase,
    *,
    config: ZSLOracleComparisonConfig,
    point_group_a: Sequence[Matrix2],
    point_group_b: Sequence[Matrix2],
) -> tuple[dict[str, Any], ...]:
    from calm.interface.matching._orchestrator import (
        enumerate_coupled_match_classes_core,
    )
    from calm.interface.matching.audit import CoupledMatchEnumerationAudit

    audit = CoupledMatchEnumerationAudit.empty(case.k_max)
    classes = tuple(
        enumerate_coupled_match_classes_core(
            slab_from_basis(case.fixture.basis_a),
            slab_from_basis(case.fixture.basis_b),
            k_max=case.k_max,
            cond_max=config.cond_max,
            w_match=0.5,
            eps_principal_max=config.exact_strain_tolerance,
            N_at_max=config.atom_limit,
            surface_symmetry_mode="identity_only",
            surface_metric_tolerance=1.0e-10,
            pair_symmetry_policy="full",
            correspondence_orientation="proper",
            identify_material_exchange=False,
            correspondence_entry_limit=None,
            point_group_A=tuple(
                np.asarray(item, dtype=int).reshape(2, 2) for item in point_group_a
            ),
            point_group_B=tuple(
                np.asarray(item, dtype=int).reshape(2, 2) for item in point_group_b
            ),
            audit=audit,
        )
    )
    audit.validate()
    rows: list[dict[str, Any]] = []
    for item in sorted(classes, key=lambda value: tuple(value.pair_key)):
        key = tuple(int(value) for value in item.pair_key)
        rows.append(
            {
                "key": list(key),
                "key_text": key_text(key),
                "source_count": int(item.source_count),
                "source_index_pairs": [
                    [int(a), int(b)] for a, b in sorted(item.source_index_pairs)
                ],
                "repeat_indices": sorted(int(value) for value in item.repeat_indices),
                "first_discovery_index": min(
                    max(int(a), int(b)) for a, b in item.source_index_pairs
                ),
            }
        )
    return tuple(rows)


def _oracle_inventory(
    case: ZSLOracleCase,
    *,
    point_group_a: Sequence[Matrix2],
    point_group_b: Sequence[Matrix2],
) -> tuple[dict[str, Any], ...]:
    if case.oracle_kind == "frozen_equal_square_full_d4_k30_v1":
        from ...qualification_fixtures import expected_full_d4_keys

        return tuple(
            {
                "key": list(key),
                "key_text": key_text(key),
                "first_discovery_index": next(
                    index
                    for index in (1, 5, 13, 17, 25, 29)
                    if key in expected_full_d4_keys(index)
                ),
            }
            for key in expected_full_d4_keys(case.k_max)
        )
    reference = exhaustive_reference_search(
        case.fixture.metric_a,
        case.fixture.metric_b,
        k_max=case.k_max,
        point_group_a=point_group_a,
        point_group_b=point_group_b,
        pair_symmetry="full",
        correspondence_orientation="proper",
        identify_material_exchange=False,
    )
    return tuple(
        {
            "key": list(item.key),
            "key_text": key_text(item.key),
            "source_count": len(item.source_pairs),
            "source_index_pairs": [list(pair) for pair in item.source_index_pairs],
            "repeat_indices": list(item.repeat_indices),
            "first_discovery_index": item.first_discovery_index,
        }
        for item in reference.classes
    )


def _area_bound(case: ZSLOracleCase) -> float:
    area_a = abs(float(np.linalg.det(np.asarray(case.fixture.basis_a, dtype=float))))
    area_b = abs(float(np.linalg.det(np.asarray(case.fixture.basis_b, dtype=float))))
    boundary = max(area_a, area_b) * case.k_max
    padding = max(1.0e-12, abs(boundary) * 1.0e-12)
    return float(boundary + padding)


def _pair(case: ZSLOracleCase) -> LatticePair2D:
    return LatticePair2D(
        name=case.case_id,
        A=np.asarray(case.fixture.basis_a, dtype=float),
        B=np.asarray(case.fixture.basis_b, dtype=float),
        comment=case.fixture.description,
    )



def _project_matches(
    *,
    case: ZSLOracleCase,
    bidirectional: bool,
    config: ZSLOracleComparisonConfig,
    generator_factory: GeneratorFactory,
    tool_version: str,
    point_group_a: Sequence[Matrix2],
    point_group_b: Sequence[Matrix2],
) -> dict[str, Any]:
    from calm.interface.matching._types import PairIdentityPolicy2D

    from .coupled_projection import project_zsl_coupled_pair
    from .metric_projection import project_zsl_metric_pair

    pair = _pair(case)
    max_area = _area_bound(case)
    settings = {
        "max_area_ratio_tol": config.max_area_ratio_tol,
        "max_area": max_area,
        "max_length_tol": config.max_length_tol,
        "max_angle_tol": config.max_angle_tol,
        "bidirectional": bidirectional,
    }
    generator = generator_factory(**settings)
    started = time.perf_counter()
    matches = call_zsl_generator(
        generator,
        basis_to_3d_vectors(pair.A),
        basis_to_3d_vectors(pair.B),
    )
    elapsed = time.perf_counter() - started
    run_id = (
        f"{case.case_id}:k{case.k_max}:"
        f"{'bidirectional' if bidirectional else 'unidirectional'}"
    )
    invocation = {
        "run_id": run_id,
        "film_role": "A",
        "substrate_role": "B",
        "basis_vector_storage": "external_rows",
        "input_film_vectors": basis_to_3d_vectors(pair.A),
        "input_substrate_vectors": basis_to_3d_vectors(pair.B),
        "common_source_bound": case.k_max,
        "exact_strain_tolerance": config.exact_strain_tolerance,
        "common_strain_limit": config.common_strain_limit,
    }
    policy = PairIdentityPolicy2D(
        pair_symmetry="full",
        correspondence_orientation="proper",
        identify_material_exchange=False,
    )
    group_a = tuple(np.asarray(item, dtype=int).reshape(2, 2) for item in point_group_a)
    group_b = tuple(np.asarray(item, dtype=int).reshape(2, 2) for item in point_group_b)
    raw_records: list[RawExternalMatch] = []
    reconstruction_records: list[ProjectedMatch] = []
    metric_records: list[ProjectedMatch] = []
    coupled_records: list[ProjectedMatch] = []
    normalized: list[dict[str, Any]] = []

    for raw_index, match in enumerate(matches):
        raw = capture_raw_zsl_match(
            match,
            tool_version=tool_version,
            fixture_id=case.case_id,
            run_id=run_id,
            raw_index=raw_index,
            generator_settings=settings,
            invocation=invocation,
        )
        reconstruction = reconstruct_zsl_source_pair(
            raw,
            atol=config.reconstruction_atol,
            rtol=config.reconstruction_rtol,
        )
        metric = project_zsl_metric_pair(raw)
        coupled = project_zsl_coupled_pair(
            raw,
            reconstruction,
            policy=policy,
            point_group_A=group_a,
            point_group_B=group_b,
            surface_metric_tolerance=1.0e-8,
        )
        raw_records.append(raw)
        reconstruction_records.append(reconstruction)
        metric_records.append(metric)
        coupled_records.append(coupled)

        source_index_a = coupled.identity.get("film_source_index")
        source_index_b = coupled.identity.get("substrate_source_index")
        within_bound = bool(
            isinstance(source_index_a, int)
            and isinstance(source_index_b, int)
            and source_index_a <= case.k_max
            and source_index_b <= case.k_max
        )
        strain = metric.metrics.get("max_abs_principal_strain")
        strain_value = float(strain) if isinstance(strain, (int, float)) else None
        key_value = coupled.identity.get("primitive_pair_key")
        key = (
            _key_tuple(key_value)
            if coupled.status == "projected" and isinstance(key_value, list)
            else None
        )
        normalized.append(
            {
                "source_match_id": coupled.source_match_id,
                "case_id": case.case_id,
                "k_max": case.k_max,
                "bidirectional": bidirectional,
                "raw_index": raw_index,
                "reconstruction_status": reconstruction.status,
                "metric_projection_status": metric.status,
                "coupled_projection_status": coupled.status,
                "film_source_index": source_index_a,
                "substrate_source_index": source_index_b,
                "within_common_source_bound": within_bound,
                "max_abs_principal_strain": strain_value,
                "passes_exact_strain_gate": bool(
                    strain_value is not None
                    and strain_value <= config.exact_strain_tolerance
                ),
                "passes_common_strain_gate": bool(
                    strain_value is not None
                    and strain_value <= config.common_strain_limit
                ),
                "primitive_pair_key": None if key is None else list(key),
                "primitive_pair_key_text": None if key is None else key_text(key),
                "repeat_index": coupled.identity.get("repeat_index"),
            }
        )

    return {
        "run_id": run_id,
        "settings": settings,
        "elapsed_seconds": elapsed,
        "raw": raw_records,
        "reconstructions": reconstruction_records,
        "metrics": metric_records,
        "coupled": coupled_records,
        "normalized": normalized,
    }


def _keys(
    rows: Sequence[Mapping[str, Any]],
    *,
    gate: str,
) -> frozenset[tuple[int, ...]]:
    selected: set[tuple[int, ...]] = set()
    for row in rows:
        if not row.get("within_common_source_bound"):
            continue
        if row.get("coupled_projection_status") != "projected":
            continue
        if gate == "exact" and not row.get("passes_exact_strain_gate"):
            continue
        if gate == "common" and not row.get("passes_common_strain_gate"):
            continue
        value = row.get("primitive_pair_key")
        if isinstance(value, list):
            selected.add(_key_tuple(value))
    return frozenset(selected)


def _multiplicity(
    rows: Sequence[Mapping[str, Any]],
    *,
    gate: str,
) -> Counter[tuple[int, ...]]:
    counter: Counter[tuple[int, ...]] = Counter()
    for row in rows:
        if not row.get("within_common_source_bound"):
            continue
        if row.get("coupled_projection_status") != "projected":
            continue
        if gate == "exact" and not row.get("passes_exact_strain_gate"):
            continue
        if gate == "common" and not row.get("passes_common_strain_gate"):
            continue
        value = row.get("primitive_pair_key")
        if isinstance(value, list):
            counter[_key_tuple(value)] += 1
    return counter


def _comparison_row(
    *,
    case: ZSLOracleCase,
    bidirectional: bool,
    oracle_inventory: Sequence[Mapping[str, Any]],
    production_inventory: Sequence[Mapping[str, Any]],
    run: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    oracle_keys = frozenset(_key_tuple(row["key"]) for row in oracle_inventory)
    production_keys = frozenset(
        _key_tuple(row["key"]) for row in production_inventory
    )
    normalized = run["normalized"]
    exact_keys = _keys(normalized, gate="exact")
    common_keys = _keys(normalized, gate="common")
    exact_multiplicity = _multiplicity(normalized, gate="exact")
    common_multiplicity = _multiplicity(normalized, gate="common")
    missing_exact = sorted(oracle_keys - exact_keys)
    extra_exact = sorted(exact_keys - oracle_keys)
    common_nonoracle = sorted(common_keys - oracle_keys)
    production_guard = production_keys == oracle_keys
    exact_recall = (
        1.0
        if not oracle_keys
        else len(oracle_keys & exact_keys) / len(oracle_keys)
    )
    exact_precision = (
        1.0
        if not exact_keys
        else len(oracle_keys & exact_keys) / len(exact_keys)
    )

    status_counts = Counter(str(row["coupled_projection_status"]) for row in normalized)
    reconstruction_counts = Counter(
        str(row["reconstruction_status"]) for row in normalized
    )
    metric_counts = Counter(str(row["metric_projection_status"]) for row in normalized)
    comparison = {
        "schema": ZSL_ORACLE_COMPARISON_SCHEMA,
        "case_id": case.case_id,
        "fixture_id": case.fixture.fixture_id,
        "family": case.fixture.family,
        "k_max": case.k_max,
        "oracle_kind": case.oracle_kind,
        "bidirectional": bidirectional,
        "zsl_run_id": run["run_id"],
        "zsl_settings": run["settings"],
        "zsl_elapsed_seconds": run["elapsed_seconds"],
        "oracle_key_count": len(oracle_keys),
        "oracle_key_digest": _key_digest(oracle_keys),
        "calm_production_key_count": len(production_keys),
        "calm_production_key_digest": _key_digest(production_keys),
        "calm_production_matches_oracle": production_guard,
        "zsl_raw_match_count": len(normalized),
        "zsl_reconstruction_status_counts": dict(sorted(reconstruction_counts.items())),
        "zsl_metric_projection_status_counts": dict(sorted(metric_counts.items())),
        "zsl_coupled_projection_status_counts": dict(sorted(status_counts.items())),
        "zsl_within_source_bound_count": sum(
            bool(row["within_common_source_bound"]) for row in normalized
        ),
        "zsl_exact_gate_description_count": sum(
            bool(row["within_common_source_bound"])
            and bool(row["passes_exact_strain_gate"])
            and row["coupled_projection_status"] == "projected"
            for row in normalized
        ),
        "zsl_common_gate_description_count": sum(
            bool(row["within_common_source_bound"])
            and bool(row["passes_common_strain_gate"])
            and row["coupled_projection_status"] == "projected"
            for row in normalized
        ),
        "zsl_exact_key_count": len(exact_keys),
        "zsl_exact_key_digest": _key_digest(exact_keys),
        "zsl_exact_reference_intersection_count": len(oracle_keys & exact_keys),
        "zsl_exact_reference_recall": exact_recall,
        "zsl_exact_reference_precision": exact_precision,
        "zsl_exact_missing_keys": [key_text(key) for key in missing_exact],
        "zsl_exact_extra_keys": [key_text(key) for key in extra_exact],
        "zsl_common_gate_key_count": len(common_keys),
        "zsl_common_gate_key_digest": _key_digest(common_keys),
        "zsl_common_gate_nonoracle_keys": [
            key_text(key) for key in common_nonoracle
        ],
        "comparison_disposition": "descriptive_only",
        "interpretation": {
            "exact_overlap": (
                "ZSL descriptions passing the exact principal-strain gate are "
                "compared with the finite exact oracle."
            ),
            "common_gate": (
                "The 3% principal-strain subset is reported separately; keys "
                "outside the zero-strain oracle are not labeled incorrect."
            ),
            "identity": (
                "External source pairs are classified under CALM's primitive "
                "coupled-pair equivalence relation."
            ),
        },
    }

    observations: list[dict[str, Any]] = []
    for key in sorted(oracle_keys | exact_keys | common_keys):
        in_oracle = key in oracle_keys
        in_exact = key in exact_keys
        in_common = key in common_keys
        if in_oracle and in_exact:
            classification = "oracle_key_generated_under_exact_gate"
        elif in_oracle and in_common:
            classification = "oracle_key_generated_only_under_common_gate"
        elif in_oracle:
            classification = "oracle_key_not_generated"
        elif in_exact:
            classification = "exact_gate_key_absent_from_oracle"
        else:
            classification = "common_gate_nonzero_strain_key"
        observations.append(
            {
                "schema": ZSL_ORACLE_KEY_OBSERVATION_SCHEMA,
                "case_id": case.case_id,
                "k_max": case.k_max,
                "bidirectional": bidirectional,
                "primitive_pair_key": list(key),
                "primitive_pair_key_text": key_text(key),
                "in_exact_oracle": in_oracle,
                "generated_by_zsl_exact_gate": in_exact,
                "generated_by_zsl_common_gate": in_common,
                "zsl_exact_description_multiplicity": exact_multiplicity[key],
                "zsl_common_description_multiplicity": common_multiplicity[key],
                "classification": classification,
            }
        )
    return comparison, tuple(observations)


def run_zsl_oracle_comparison(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    config: ZSLOracleComparisonConfig,
    generator_factory: GeneratorFactory | None = None,
    tool_version: str | None = None,
) -> ZSLOracleComparisonArtifacts:
    """Execute C7 with common finite bounds, gates, and coupled identity."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = select_zsl_oracle_cases(config)
    factory = generator_factory or default_generator_factory
    version = tool_version or pymatgen_version()

    raw_records: list[dict[str, Any]] = []
    reconstruction_records: list[dict[str, Any]] = []
    metric_records: list[dict[str, Any]] = []
    coupled_records: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    key_observations: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for case in cases:
        group_a = enumerate_metric_point_group(case.fixture.metric_a)
        group_b = enumerate_metric_point_group(case.fixture.metric_b)
        oracle_inventory = _oracle_inventory(
            case,
            point_group_a=group_a,
            point_group_b=group_b,
        )
        production_inventory = _production_inventory(
            case,
            config=config,
            point_group_a=group_a,
            point_group_b=group_b,
        )
        for bidirectional in _directionality_modes(config):
            run = _project_matches(
                case=case,
                bidirectional=bidirectional,
                config=config,
                generator_factory=factory,
                tool_version=version,
                point_group_a=group_a,
                point_group_b=group_b,
            )
            raw_records.extend(record.to_dict() for record in run["raw"])
            reconstruction_records.extend(
                record.to_dict() for record in run["reconstructions"]
            )
            metric_records.extend(record.to_dict() for record in run["metrics"])
            coupled_records.extend(record.to_dict() for record in run["coupled"])
            comparison, observations = _comparison_row(
                case=case,
                bidirectional=bidirectional,
                oracle_inventory=oracle_inventory,
                production_inventory=production_inventory,
                run=run,
            )
            comparison_rows.append(comparison)
            key_observations.extend(observations)
            summary_rows.append(
                {
                    "schema": ZSL_ORACLE_SUMMARY_SCHEMA,
                    "case_id": case.case_id,
                    "fixture_id": case.fixture.fixture_id,
                    "family": case.fixture.family,
                    "k_max": case.k_max,
                    "bidirectional": bidirectional,
                    "oracle_key_count": comparison["oracle_key_count"],
                    "calm_production_matches_oracle": comparison[
                        "calm_production_matches_oracle"
                    ],
                    "zsl_raw_match_count": comparison["zsl_raw_match_count"],
                    "zsl_exact_key_count": comparison["zsl_exact_key_count"],
                    "zsl_exact_reference_recall": comparison[
                        "zsl_exact_reference_recall"
                    ],
                    "zsl_exact_reference_precision": comparison[
                        "zsl_exact_reference_precision"
                    ],
                    "zsl_exact_missing_key_count": len(
                        comparison["zsl_exact_missing_keys"]
                    ),
                    "zsl_exact_extra_key_count": len(
                        comparison["zsl_exact_extra_keys"]
                    ),
                    "zsl_common_gate_key_count": comparison[
                        "zsl_common_gate_key_count"
                    ],
                    "zsl_common_gate_nonoracle_key_count": len(
                        comparison["zsl_common_gate_nonoracle_keys"]
                    ),
                    "zsl_elapsed_seconds": comparison["zsl_elapsed_seconds"],
                }
            )

    raw_path = write_canonical_jsonl_atomic(root / "zsl_oracle_raw_matches.jsonl", raw_records)
    reconstruction_path = write_canonical_jsonl_atomic(
        root / "zsl_oracle_reconstructions.jsonl", reconstruction_records
    )
    metric_path = write_canonical_jsonl_atomic(
        root / "zsl_oracle_metric_projections.jsonl", metric_records
    )
    coupled_path = write_canonical_jsonl_atomic(
        root / "zsl_oracle_coupled_projections.jsonl", coupled_records
    )
    comparisons_path = write_canonical_jsonl_atomic(
        root / "zsl_oracle_comparisons.jsonl", comparison_rows
    )
    key_observations_path = write_canonical_jsonl_atomic(
        root / "zsl_oracle_key_observations.jsonl", key_observations
    )
    summary_csv_path = write_csv_atomic(
        root / "zsl_oracle_summary.csv", summary_rows
    )

    internal_guard_passed = all(
        bool(row["calm_production_matches_oracle"]) for row in summary_rows
    )
    projection_failure_count = sum(
        sum(
            count
            for status, count in comparison[
                "zsl_coupled_projection_status_counts"
            ].items()
            if status != "projected"
        )
        for comparison in comparison_rows
    )
    result = ClaimResult(
        claim_id=ClaimId.C7_ZSL_COMPARISON,
        status=(
            ClaimStatus.DESCRIPTIVE_ONLY
            if internal_guard_passed
            else ClaimStatus.FAIL
        ),
        summary=(
            "CALM and pymatgen ZSL were compared under common finite source "
            "bounds, exact and 3% principal-strain gates, and CALM's primitive "
            "coupled-pair identity."
            if internal_guard_passed
            else "The controlled external comparison could not be interpreted "
            "because CALM's production inventory disagreed with its exact oracle."
        ),
        evidence_files=(
            "zsl_oracle_summary.json",
            "zsl_oracle_summary.csv",
            "zsl_oracle_comparisons.jsonl",
            "zsl_oracle_key_observations.jsonl",
            "zsl_oracle_raw_matches.jsonl",
            "zsl_oracle_reconstructions.jsonl",
            "zsl_oracle_metric_projections.jsonl",
            "zsl_oracle_coupled_projections.jsonl",
        ),
        metrics={
            "case_count": len(cases),
            "comparison_run_count": len(summary_rows),
            "internal_oracle_guard_passed": internal_guard_passed,
            "zsl_raw_match_count_total": sum(
                int(row["zsl_raw_match_count"]) for row in summary_rows
            ),
            "zsl_projection_failure_count": projection_failure_count,
            "mean_zsl_exact_reference_recall": (
                sum(float(row["zsl_exact_reference_recall"]) for row in summary_rows)
                / len(summary_rows)
            ),
            "complete_exact_inventory_run_count": sum(
                float(row["zsl_exact_reference_recall"]) == 1.0
                and int(row["zsl_exact_extra_key_count"]) == 0
                for row in summary_rows
            ),
        },
        notes=(
            "ZSL is an external comparator, not a correctness oracle for CALM; "
            "the normal successful disposition is descriptive_only.",
            "Exact-oracle overlap uses an effectively zero-strain gate. The "
            "3% principal-strain population is reported separately and may "
            "legitimately contain nonzero-strain classes absent from the exact oracle.",
            "Projected primitive keys classify external ZSL source pairs under "
            "CALM's equivalence relation; pymatgen does not claim to implement "
            "that identity or deduplication policy.",
        ),
    )
    claim_result_path = write_json_atomic(root / "claim_result.json", result.to_dict())
    summary_payload = {
        "schema": ZSL_ORACLE_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "claim_result": result.to_dict(),
        "config": config.to_dict(),
        "pymatgen_version": version,
        "case_count": len(cases),
        "comparison_run_count": len(summary_rows),
        "cases": [case.to_dict() for case in cases],
        "comparisons": summary_rows,
        "interpretation": {
            "claim_disposition": (
                "descriptive_only unless an internal CALM/oracle guard fails"
            ),
            "oracle_gate": (
                "max_abs_principal_strain <= "
                f"{config.exact_strain_tolerance}"
            ),
            "common_gate": f"max_abs_principal_strain <= {config.common_strain_limit}",
            "source_bound": "film_source_index and substrate_source_index <= k_max",
            "identity": (
                "CALM primitive coupled-pair projection with full point groups, "
                "proper correspondences, and ordered materials"
            ),
            "legacy_suite_modified": False,
        },
    }
    summary_path = write_json_atomic(root / "zsl_oracle_summary.json", summary_payload)

    artifact_specs = (
        (claim_result_path, "application/json"),
        (summary_path, "application/json"),
        (summary_csv_path, "text/csv"),
        (comparisons_path, "application/x-ndjson"),
        (key_observations_path, "application/x-ndjson"),
        (raw_path, "application/x-ndjson"),
        (reconstruction_path, "application/x-ndjson"),
        (metric_path, "application/x-ndjson"),
        (coupled_path, "application/x-ndjson"),
    )
    artifacts = tuple(
        artifact_record(path, relative_to=root, media_type=media_type)
        for path, media_type in artifact_specs
    )
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C7_ZSL_COMPARISON,),
        fixture_hashes={case.case_id: case.sha256() for case in cases},
        policy_settings=config.to_dict(),
        artifacts=artifacts,
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return ZSLOracleComparisonArtifacts(
        manifest=manifest_path,
        claim_result=claim_result_path,
        summary=summary_path,
        summary_csv=summary_csv_path,
        comparisons=comparisons_path,
        key_observations=key_observations_path,
        raw_matches=raw_path,
        reconstructions=reconstruction_path,
        metric_projections=metric_path,
        coupled_projections=coupled_path,
        result=result,
    )


__all__ = [
    "DEFAULT_DIRECTIONALITY",
    "DEFAULT_PROFILE",
    "SUPPORTED_DIRECTIONALITIES",
    "SUPPORTED_PROFILES",
    "ZSL_ORACLE_COMPARISON_SCHEMA",
    "ZSL_ORACLE_FIXTURE_SCHEMA",
    "ZSL_ORACLE_KEY_OBSERVATION_SCHEMA",
    "ZSL_ORACLE_SUMMARY_SCHEMA",
    "ZSLOracleCase",
    "ZSLOracleComparisonArtifacts",
    "ZSLOracleComparisonConfig",
    "default_zsl_oracle_cases",
    "run_zsl_oracle_comparison",
    "select_zsl_oracle_cases",
]
