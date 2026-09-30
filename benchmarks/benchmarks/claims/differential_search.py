"""C2 production-versus-independent-reference differential qualification.

The production matcher and the reference implementation receive the same exact
rational lattice metrics, finite HNF bound, surface point groups, and identity
policy. The reference implementation is exhaustive and imports no CALM
production matching code.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from ._support import (
    key_text,
    matrix_payload,
    slab_from_basis,
    write_csv_atomic,
    write_jsonl_atomic,
)
from .claim_ids import ClaimId, ClaimStatus
from .manifest import artifact_record, build_manifest, write_json_atomic
from .reference.coupled_match_reference import (
    Matrix2,
    Metric2,
    ReferenceSearchResult,
    enumerate_metric_point_group,
    exhaustive_reference_search,
    metric2,
    transform_metric,
)
from .schemas import ClaimResult, ReferenceComparison


REFERENCE_DIFFERENTIAL_SUMMARY_SCHEMA = "calm.reference_differential_summary/v1"
REFERENCE_FIXTURE_RESULT_SCHEMA = "calm.reference_fixture_result/v1"
REFERENCE_INVENTORY_SCHEMA = "calm.reference_key_inventory/v1"
DEFAULT_PROFILE = "standard"
DEFAULT_EXACT_STRAIN_TOLERANCE = 1.0e-10
DEFAULT_CONDITION_LIMIT = 1.0e9
DEFAULT_ATOM_LIMIT = 100_000


def _fraction_string(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _metric_payload(metric: Metric2) -> list[list[str]]:
    return [
        [_fraction_string(metric[0]), _fraction_string(metric[1])],
        [_fraction_string(metric[2]), _fraction_string(metric[3])],
    ]


def _key_digest(keys: Iterable[Sequence[int]]) -> str:
    payload = sorted(tuple(int(value) for value in key) for key in keys)
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _basis_from_metric(metric: Metric2) -> np.ndarray:
    array = np.array(
        [
            [float(metric[0]), float(metric[1])],
            [float(metric[2]), float(metric[3])],
        ],
        dtype=float,
    )
    return np.linalg.cholesky(array).T


def _rotation(angle_degrees: float) -> np.ndarray:
    angle = math.radians(float(angle_degrees))
    return np.array(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]],
        dtype=float,
    )


@dataclass(frozen=True)
class DifferentialFixture:
    """One exact lattice-pair fixture and its Cartesian realization."""

    fixture_id: str
    family: str
    description: str
    metric_a: Metric2
    metric_b: Metric2
    basis_a: tuple[tuple[float, float], tuple[float, float]]
    basis_b: tuple[tuple[float, float], tuple[float, float]]
    recommended_k_max: int
    right_basis_b: Matrix2 | None = None
    rotation_b_degrees: float = 0.0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        required = (self.fixture_id, self.family, self.description)
        if any(not value.strip() for value in required):
            raise ValueError(
                "fixture identifiers, family, and description must be nonempty"
            )
        metric2(self.metric_a)
        metric2(self.metric_b)
        for name, basis in (("basis_a", self.basis_a), ("basis_b", self.basis_b)):
            array = np.asarray(basis, dtype=float)
            if array.shape != (2, 2) or not np.all(np.isfinite(array)):
                raise ValueError(f"{name} must be a finite 2x2 matrix")
            if float(np.linalg.det(array)) <= 0.0:
                raise ValueError(f"{name} must have positive orientation")
        if self.recommended_k_max <= 0:
            raise ValueError("recommended_k_max must be positive")
        if self.right_basis_b is not None:
            right = np.asarray(self.right_basis_b, dtype=int).reshape(2, 2)
            if round(float(np.linalg.det(right))) != 1:
                raise ValueError("right_basis_b must have determinant +1")
        if not math.isfinite(self.rotation_b_degrees):
            raise ValueError("rotation_b_degrees must be finite")

    def _stable_identity_payload(self) -> dict[str, Any]:
        return {
            "schema": "calm.reference_differential_fixture/v1",
            "fixture_id": self.fixture_id,
            "family": self.family,
            "description": self.description,
            "metric_A": _metric_payload(self.metric_a),
            "metric_B": _metric_payload(self.metric_b),
            "basis_construction": {
                "A": "upper_cholesky_of_exact_metric_A",
                "B_right_basis_transform": (
                    None
                    if self.right_basis_b is None
                    else matrix_payload(self.right_basis_b)
                ),
                "B_cartesian_rotation_degrees": self.rotation_b_degrees,
            },
            "recommended_k_max": self.recommended_k_max,
            "tags": list(self.tags),
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self._stable_identity_payload()
        payload.update(
            {
                "basis_vector_storage": "columns",
                "basis_A": [list(row) for row in self.basis_a],
                "basis_B": [list(row) for row in self.basis_b],
            }
        )
        return payload

    def sha256(self) -> str:
        return _canonical_json_sha256(self._stable_identity_payload())


def _fixture(
    *,
    fixture_id: str,
    family: str,
    description: str,
    metric: Sequence[Sequence[object]],
    recommended_k_max: int,
    right_basis_b: Matrix2 | None = None,
    rotation_b_degrees: float = 0.0,
    tags: Sequence[str] = (),
) -> DifferentialFixture:
    exact_a = metric2(metric)
    basis_a = _basis_from_metric(exact_a)
    if right_basis_b is None:
        exact_b = exact_a
        basis_b = basis_a.copy()
    else:
        right = np.asarray(right_basis_b, dtype=int).reshape(2, 2)
        if round(float(np.linalg.det(right))) != 1:
            raise ValueError("right_basis_b must have determinant +1")
        exact_b = transform_metric(exact_a, right_basis_b)
        basis_b = basis_a @ right
    if rotation_b_degrees:
        basis_b = _rotation(rotation_b_degrees) @ basis_b
    return DifferentialFixture(
        fixture_id=fixture_id,
        family=family,
        description=description,
        metric_a=exact_a,
        metric_b=exact_b,
        basis_a=tuple(
            tuple(float(value) for value in row) for row in basis_a
        ),  # type: ignore[arg-type]
        basis_b=tuple(
            tuple(float(value) for value in row) for row in basis_b
        ),  # type: ignore[arg-type]
        recommended_k_max=int(recommended_k_max),
        right_basis_b=right_basis_b,
        rotation_b_degrees=float(rotation_b_degrees),
        tags=tuple(tags),
    )


def default_differential_fixtures() -> tuple[DifferentialFixture, ...]:
    """Return the deterministic standard C2 fixture matrix."""

    shear: Matrix2 = (1, 1, 0, 1)
    return (
        _fixture(
            fixture_id="square_standard",
            family="square",
            description="Equal square lattices with the full exact D4 group.",
            metric=((1, 0), (0, 1)),
            recommended_k_max=5,
            tags=("high_symmetry", "sigma5", "exact"),
        ),
        _fixture(
            fixture_id="square_rotated_b",
            family="square",
            description="Square B lattice rotated rigidly in Cartesian space.",
            metric=((1, 0), (0, 1)),
            rotation_b_degrees=17.0,
            recommended_k_max=4,
            tags=("cartesian_rotation", "metamorphic"),
        ),
        _fixture(
            fixture_id="square_unimodular_b",
            family="square",
            description="Square B lattice expressed in a sheared primitive basis.",
            metric=((1, 0), (0, 1)),
            right_basis_b=shear,
            recommended_k_max=4,
            tags=("primitive_basis_change", "metamorphic"),
        ),
        _fixture(
            fixture_id="rectangular_standard",
            family="rectangular",
            description="Equal 2:1 rectangular lattices with exact D2 symmetry.",
            metric=((4, 0), (0, 1)),
            recommended_k_max=5,
            tags=("lower_symmetry", "nontrivial_inventory"),
        ),
        _fixture(
            fixture_id="rectangular_rotated_b",
            family="rectangular",
            description="Rectangular B lattice rotated rigidly in Cartesian space.",
            metric=((4, 0), (0, 1)),
            rotation_b_degrees=31.0,
            recommended_k_max=4,
            tags=("cartesian_rotation", "metamorphic"),
        ),
        _fixture(
            fixture_id="rectangular_unimodular_b",
            family="rectangular",
            description="Rectangular B lattice expressed in a sheared primitive basis.",
            metric=((4, 0), (0, 1)),
            right_basis_b=shear,
            recommended_k_max=4,
            tags=("primitive_basis_change", "metamorphic"),
        ),
        _fixture(
            fixture_id="hexagonal_standard",
            family="hexagonal",
            description="Equal 60-degree rhombic lattices with exact D6 symmetry.",
            metric=((1, "1/2"), ("1/2", 1)),
            recommended_k_max=4,
            tags=("high_symmetry", "reduction_degeneracy"),
        ),
        _fixture(
            fixture_id="hexagonal_rotated_b",
            family="hexagonal",
            description="Hexagonal B lattice rotated rigidly in Cartesian space.",
            metric=((1, "1/2"), ("1/2", 1)),
            rotation_b_degrees=23.0,
            recommended_k_max=4,
            tags=("cartesian_rotation", "metamorphic"),
        ),
        _fixture(
            fixture_id="hexagonal_unimodular_b",
            family="hexagonal",
            description=(
                "Hexagonal B lattice expressed in an alternate primitive basis."
            ),
            metric=((1, "1/2"), ("1/2", 1)),
            right_basis_b=shear,
            recommended_k_max=4,
            tags=("primitive_basis_change", "metamorphic"),
        ),
        _fixture(
            fixture_id="oblique_standard",
            family="oblique",
            description="Generic equal oblique lattices with only central inversion.",
            metric=((5, 1), (1, 3)),
            recommended_k_max=5,
            tags=("generic", "low_symmetry"),
        ),
        _fixture(
            fixture_id="oblique_rotated_b",
            family="oblique",
            description="Generic oblique B lattice rotated rigidly in Cartesian space.",
            metric=((5, 1), (1, 3)),
            rotation_b_degrees=19.0,
            recommended_k_max=4,
            tags=("cartesian_rotation", "metamorphic"),
        ),
        _fixture(
            fixture_id="near_square_generic",
            family="near_square",
            description="Near-square rational metric without accidental D4 symmetry.",
            metric=((1, "1/1000"), ("1/1000", "1001/1000")),
            recommended_k_max=4,
            tags=("near_degenerate", "low_symmetry"),
        ),
        _fixture(
            fixture_id="near_hexagonal_generic",
            family="near_hexagonal",
            description=(
                "Near-hexagonal rational metric without accidental D6 symmetry."
            ),
            metric=((1, "499/1000"), ("499/1000", "1001/1000")),
            recommended_k_max=4,
            tags=("near_degenerate", "low_symmetry"),
        ),
        _fixture(
            fixture_id="strong_shear_generic",
            family="oblique",
            description="Strongly sheared generic metric with a finite exact domain.",
            metric=((5, 3), (3, 4)),
            recommended_k_max=4,
            tags=("strong_shear", "low_symmetry"),
        ),
        _fixture(
            fixture_id="high_condition_rectangular",
            family="rectangular",
            description=(
                "Anisotropic rectangular metric exercising conditioning margins."
            ),
            metric=((25, 0), (0, 1)),
            recommended_k_max=4,
            tags=("high_condition", "anisotropic"),
        ),
    )


SMOKE_FIXTURE_IDS = (
    "square_standard",
    "rectangular_standard",
    "hexagonal_standard",
    "oblique_standard",
)


@dataclass(frozen=True)
class ReferenceDifferentialConfig:
    """Configuration for the C2 exact differential stage."""

    profile: str = DEFAULT_PROFILE
    fixture_ids: tuple[str, ...] = ()
    k_max_override: int | None = None
    eps_principal_max: float = DEFAULT_EXACT_STRAIN_TOLERANCE
    cond_max: float = DEFAULT_CONDITION_LIMIT
    atom_limit: int = DEFAULT_ATOM_LIMIT

    def __post_init__(self) -> None:
        if self.profile not in {"smoke", "standard"}:
            raise ValueError("profile must be 'smoke' or 'standard'")
        if self.k_max_override is not None and self.k_max_override <= 0:
            raise ValueError("k_max_override must be positive or None")
        if not math.isfinite(self.eps_principal_max) or self.eps_principal_max < 0:
            raise ValueError("eps_principal_max must be finite and nonnegative")
        if not math.isfinite(self.cond_max) or self.cond_max <= 0:
            raise ValueError("cond_max must be finite and positive")
        if self.atom_limit <= 0:
            raise ValueError("atom_limit must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "fixture_ids": list(self.fixture_ids),
            "k_max_override": self.k_max_override,
            "eps_principal_max": self.eps_principal_max,
            "cond_max": self.cond_max,
            "atom_limit": self.atom_limit,
            "pair_symmetry_policy": "full",
            "correspondence_orientation": "proper",
            "identify_material_exchange": False,
            "correspondence_entry_limit": None,
        }


def select_differential_fixtures(
    config: ReferenceDifferentialConfig,
) -> tuple[DifferentialFixture, ...]:
    fixtures = default_differential_fixtures()
    by_id = {fixture.fixture_id: fixture for fixture in fixtures}
    if config.fixture_ids:
        unknown = sorted(set(config.fixture_ids) - set(by_id))
        if unknown:
            raise ValueError(f"unknown differential fixtures: {unknown}")
        selected_ids = tuple(dict.fromkeys(config.fixture_ids))
        return tuple(by_id[fixture_id] for fixture_id in selected_ids)
    if config.profile == "smoke":
        return tuple(by_id[fixture_id] for fixture_id in SMOKE_FIXTURE_IDS)
    return fixtures


def _production_inventory(match_classes: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for match_class in sorted(match_classes, key=lambda item: tuple(item.pair_key)):
        key = tuple(int(value) for value in match_class.pair_key)
        rows.append(
            {
                "key": list(key),
                "key_text": key_text(key),
                "source_count": int(match_class.source_count),
                "source_index_pairs": [
                    [int(a), int(b)] for a, b in sorted(match_class.source_index_pairs)
                ],
                "repeat_indices": sorted(
                    int(value) for value in match_class.repeat_indices
                ),
                "first_discovery_index": min(
                    max(int(a), int(b)) for a, b in match_class.source_index_pairs
                ),
            }
        )
    return tuple(rows)


def _reference_inventory(result: ReferenceSearchResult) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "key": list(item.key),
            "key_text": key_text(item.key),
            "source_count": len(item.source_pairs),
            "source_index_pairs": [list(pair) for pair in item.source_index_pairs],
            "repeat_indices": list(item.repeat_indices),
            "first_discovery_index": item.first_discovery_index,
        }
        for item in result.classes
    )


def _metadata_mismatches(
    production: Sequence[Mapping[str, Any]],
    reference: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    production_by_key = {str(row["key_text"]): row for row in production}
    reference_by_key = {str(row["key_text"]): row for row in reference}
    messages: list[str] = []
    for key in sorted(set(production_by_key) & set(reference_by_key)):
        observed = production_by_key[key]
        expected = reference_by_key[key]
        for field_name in (
            "source_count",
            "source_index_pairs",
            "repeat_indices",
            "first_discovery_index",
        ):
            if observed[field_name] != expected[field_name]:
                messages.append(
                    f"{key} field {field_name}: production={observed[field_name]!r}, "
                    f"reference={expected[field_name]!r}"
                )
    return tuple(messages)


def evaluate_differential_fixture(
    fixture: DifferentialFixture,
    *,
    config: ReferenceDifferentialConfig,
) -> dict[str, Any]:
    """Run production and exact reference searches for one fixture."""

    from calm.interface.matching._orchestrator import (
        enumerate_coupled_match_classes_core,
    )
    from calm.interface.matching.audit import CoupledMatchEnumerationAudit

    k_max = int(config.k_max_override or fixture.recommended_k_max)
    group_a = enumerate_metric_point_group(fixture.metric_a)
    group_b = enumerate_metric_point_group(fixture.metric_b)

    reference_start = time.perf_counter()
    reference = exhaustive_reference_search(
        fixture.metric_a,
        fixture.metric_b,
        k_max=k_max,
        point_group_a=group_a,
        point_group_b=group_b,
        pair_symmetry="full",
        correspondence_orientation="proper",
        identify_material_exchange=False,
    )
    reference_elapsed = time.perf_counter() - reference_start

    audit = CoupledMatchEnumerationAudit.empty(k_max)
    production_start = time.perf_counter()
    production_classes = tuple(
        enumerate_coupled_match_classes_core(
            slab_from_basis(fixture.basis_a),
            slab_from_basis(fixture.basis_b),
            k_max=k_max,
            cond_max=config.cond_max,
            w_match=0.5,
            eps_principal_max=config.eps_principal_max,
            N_at_max=config.atom_limit,
            surface_symmetry_mode="identity_only",
            surface_metric_tolerance=1.0e-10,
            pair_symmetry_policy="full",
            correspondence_orientation="proper",
            identify_material_exchange=False,
            correspondence_entry_limit=None,
            point_group_A=tuple(
                np.asarray(item, dtype=int).reshape(2, 2) for item in group_a
            ),
            point_group_B=tuple(
                np.asarray(item, dtype=int).reshape(2, 2) for item in group_b
            ),
            audit=audit,
        )
    )
    production_elapsed = time.perf_counter() - production_start
    audit.validate()

    production_inventory = _production_inventory(production_classes)
    reference_inventory = _reference_inventory(reference)
    production_keys = {tuple(row["key"]) for row in production_inventory}
    reference_keys = {tuple(row["key"]) for row in reference_inventory}
    missing = tuple(key_text(key) for key in sorted(reference_keys - production_keys))
    unexpected = tuple(
        key_text(key) for key in sorted(production_keys - reference_keys)
    )
    comparison = ReferenceComparison(
        fixture_id=fixture.fixture_id,
        domain={
            "k_max": k_max,
            "exact_zero_strain": True,
            "eps_principal_max": config.eps_principal_max,
            "cond_max": config.cond_max,
            "atom_limit": config.atom_limit,
            "pair_symmetry_policy": "full",
            "correspondence_orientation": "proper",
            "identify_material_exchange": False,
            "metric_A": _metric_payload(fixture.metric_a),
            "metric_B": _metric_payload(fixture.metric_b),
            "point_group_A_order": len(group_a),
            "point_group_B_order": len(group_b),
        },
        production_key_digest=_key_digest(production_keys),
        reference_key_digest=_key_digest(reference_keys),
        production_count=len(production_keys),
        reference_count=len(reference_keys),
        missing_keys=missing,
        unexpected_keys=unexpected,
    )
    metadata_mismatches = _metadata_mismatches(
        production_inventory,
        reference_inventory,
    )
    exact_match = comparison.exact_match and not metadata_mismatches

    return {
        "schema": REFERENCE_FIXTURE_RESULT_SCHEMA,
        "fixture": fixture.to_dict(),
        "fixture_sha256": fixture.sha256(),
        "comparison": comparison.to_dict(),
        "metadata_exact_match": not metadata_mismatches,
        "exact_match": exact_match,
        "metadata_mismatches": list(metadata_mismatches),
        "production": {
            "implementation": audit.implementation,
            "elapsed_seconds": production_elapsed,
            "class_count": len(production_inventory),
            "inventory": list(production_inventory),
            "audit": audit.to_dict(),
        },
        "reference": {
            "implementation": "independent_exact_rational_reference_v1",
            "elapsed_seconds": reference_elapsed,
            "class_count": len(reference_inventory),
            "hnf_pair_count": reference.hnf_pair_count,
            "correspondence_state_count": reference.correspondence_state_count,
            "point_group_A": [matrix_payload(item) for item in group_a],
            "point_group_B": [matrix_payload(item) for item in group_b],
            "inventory": list(reference_inventory),
        },
    }


@dataclass(frozen=True)
class ReferenceDifferentialArtifacts:
    manifest: Path
    claim_result: Path
    summary: Path
    comparisons: Path
    fixture_results: Path
    summary_csv: Path
    result: ClaimResult

    @property
    def evidence_paths(self) -> tuple[Path, ...]:
        return (
            self.summary,
            self.comparisons,
            self.fixture_results,
            self.summary_csv,
        )


def run_reference_differential_qualification(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    config: ReferenceDifferentialConfig,
) -> ReferenceDifferentialArtifacts:
    """Execute C2 over the selected deterministic exact fixture matrix."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fixtures = select_differential_fixtures(config)
    fixture_results = tuple(
        evaluate_differential_fixture(fixture, config=config) for fixture in fixtures
    )
    comparison_rows = tuple(result["comparison"] for result in fixture_results)
    summary_rows = tuple(
        {
            "schema": REFERENCE_DIFFERENTIAL_SUMMARY_SCHEMA,
            "fixture_id": result["fixture"]["fixture_id"],
            "family": result["fixture"]["family"],
            "k_max": result["comparison"]["domain"]["k_max"],
            "point_group_A_order": result["comparison"]["domain"][
                "point_group_A_order"
            ],
            "point_group_B_order": result["comparison"]["domain"][
                "point_group_B_order"
            ],
            "production_count": result["comparison"]["production_count"],
            "reference_count": result["comparison"]["reference_count"],
            "key_exact_match": result["comparison"]["exact_match"],
            "metadata_exact_match": result["metadata_exact_match"],
            "exact_match": result["exact_match"],
            "production_elapsed_seconds": result["production"]["elapsed_seconds"],
            "reference_elapsed_seconds": result["reference"]["elapsed_seconds"],
            "reference_hnf_pair_count": result["reference"]["hnf_pair_count"],
            "reference_correspondence_state_count": result["reference"][
                "correspondence_state_count"
            ],
            "missing_key_count": len(result["comparison"]["missing_keys"]),
            "unexpected_key_count": len(result["comparison"]["unexpected_keys"]),
            "metadata_mismatch_count": len(result["metadata_mismatches"]),
        }
        for result in fixture_results
    )

    fixture_results_path = write_jsonl_atomic(
        root / "reference_fixture_results.jsonl",
        fixture_results,
    )
    comparisons_path = write_jsonl_atomic(
        root / "reference_comparisons.jsonl",
        comparison_rows,
    )
    summary_csv_path = write_csv_atomic(
        root / "reference_differential_summary.csv",
        summary_rows,
    )

    passed_count = sum(bool(row["exact_match"]) for row in summary_rows)
    all_passed = passed_count == len(summary_rows)
    result = ClaimResult(
        claim_id=ClaimId.C2_FINITE_COMPLETENESS,
        status=ClaimStatus.PASS if all_passed else ClaimStatus.FAIL,
        summary=(
            "The production coupled matcher exactly matches the independent "
            "exhaustive rational reference on every selected finite fixture."
            if all_passed
            else "The production and independent reference inventories disagree "
            "for one or more finite fixtures."
        ),
        evidence_files=(
            "reference_differential_summary.json",
            "reference_comparisons.jsonl",
            "reference_fixture_results.jsonl",
            "reference_differential_summary.csv",
        ),
        metrics={
            "fixture_count": len(summary_rows),
            "exact_match_count": passed_count,
            "failure_count": len(summary_rows) - passed_count,
            "production_class_count_total": sum(
                int(row["production_count"]) for row in summary_rows
            ),
            "reference_class_count_total": sum(
                int(row["reference_count"]) for row in summary_rows
            ),
        },
        notes=(
            "The reference enumerates all HNF pairs and exact rational metric "
            "correspondences without production orbit pruning.",
            "This C2 stage qualifies exact zero-strain equal-lattice and "
            "reparameterized domains; nonzero-strain heterogeneous domains "
            "remain future differential fixtures.",
        ),
    )
    claim_result_path = write_json_atomic(root / "claim_result.json", result.to_dict())
    summary_payload = {
        "schema": REFERENCE_DIFFERENTIAL_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "claim_result": result.to_dict(),
        "config": config.to_dict(),
        "fixture_count": len(fixtures),
        "exact_match_count": passed_count,
        "all_exact": all_passed,
        "fixtures": list(summary_rows),
        "interpretation": {
            "oracle": "independent exhaustive exact-rational reference",
            "pass_criterion": (
                "exact primitive-key equality plus source-count, source-index, "
                "repeat-index, and first-discovery parity"
            ),
            "legacy_suite_modified": False,
            "scope": "small finite exact zero-strain domains",
        },
    }
    summary_path = write_json_atomic(
        root / "reference_differential_summary.json",
        summary_payload,
    )

    artifacts = tuple(
        artifact_record(path, relative_to=root, media_type=media_type)
        for path, media_type in (
            (claim_result_path, "application/json"),
            (summary_path, "application/json"),
            (comparisons_path, "application/x-ndjson"),
            (fixture_results_path, "application/x-ndjson"),
            (summary_csv_path, "text/csv"),
        )
    )
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C2_FINITE_COMPLETENESS,),
        fixture_hashes={fixture.fixture_id: fixture.sha256() for fixture in fixtures},
        policy_settings=config.to_dict(),
        artifacts=artifacts,
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return ReferenceDifferentialArtifacts(
        manifest=manifest_path,
        claim_result=claim_result_path,
        summary=summary_path,
        comparisons=comparisons_path,
        fixture_results=fixture_results_path,
        summary_csv=summary_csv_path,
        result=result,
    )


__all__ = [
    "DEFAULT_PROFILE",
    "DifferentialFixture",
    "ReferenceDifferentialArtifacts",
    "ReferenceDifferentialConfig",
    "default_differential_fixtures",
    "evaluate_differential_fixture",
    "run_reference_differential_qualification",
    "select_differential_fixtures",
]
