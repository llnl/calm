"""Versioned, JSON-serializable evidence records for CALM qualification."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .claim_ids import ClaimId, ClaimStatus


CLAIM_SUITE_VERSION = "claims_v1"
CLAIM_RESULT_SCHEMA = "calm.claim_result/v1"
CLAIM_SUMMARY_SCHEMA = "calm.claim_summary/v1"
BENCHMARK_MANIFEST_SCHEMA = "calm.benchmark_manifest/v1"
RAW_EXTERNAL_MATCH_SCHEMA = "calm.raw_external_match/v1"
PROJECTED_MATCH_SCHEMA = "calm.projected_match/v1"
GATE_CANDIDATE_SCHEMA = "calm.gate_candidate/v1"
GATE_DECISION_SCHEMA = "calm.gate_decision/v1"
REFERENCE_COMPARISON_SCHEMA = "calm.reference_comparison/v1"
PERFORMANCE_MEASUREMENT_SCHEMA = "calm.performance_measurement/v1"
IDENTITY_POLICY_OBSERVATION_SCHEMA = "calm.identity_policy_observation/v1"
METAMORPHIC_OBSERVATION_SCHEMA = "calm.metamorphic_observation/v1"
SEARCH_EXTENSION_SNAPSHOT_SCHEMA = "calm.search_extension_snapshot/v1"
SEARCH_EXTENSION_TRANSITION_SCHEMA = "calm.search_extension_transition/v1"
PUBLIC_API_PARITY_SUMMARY_SCHEMA = "calm.public_api_parity_summary/v1"
PUBLIC_API_PARITY_FIXTURE_SCHEMA = "calm.public_api_parity_fixture/v1"
PUBLIC_API_PARITY_INVENTORY_SCHEMA = "calm.public_api_parity_inventory/v1"
PUBLIC_API_PARITY_COMPARISON_SCHEMA = "calm.public_api_parity_comparison/v1"
ZSL_ORACLE_SUMMARY_SCHEMA = "calm.zsl_oracle_summary/v1"
ZSL_ORACLE_FIXTURE_SCHEMA = "calm.zsl_oracle_fixture/v1"
ZSL_ORACLE_COMPARISON_SCHEMA = "calm.zsl_oracle_comparison/v1"
ZSL_ORACLE_KEY_OBSERVATION_SCHEMA = "calm.zsl_oracle_key_observation/v1"


def _require_nonempty(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be nonempty")
    return normalized


def _require_sha256(value: str, *, field_name: str) -> str:
    digest = _require_nonempty(value, field_name=field_name)
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ValueError(
            f"{field_name} must be a lowercase 64-character SHA-256 digest"
        )
    return digest


def _require_schema(actual: str, expected: str) -> None:
    if actual != expected:
        raise ValueError(f"unsupported schema {actual!r}; expected {expected!r}")


def _require_json_value(value: Any, *, field_name: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite float")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field_name} mapping keys must be strings")
            _require_json_value(item, field_name=f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_json_value(item, field_name=f"{field_name}[{index}]")
        return
    raise TypeError(
        f"{field_name} contains non-JSON value of type {type(value).__name__}"
    )


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(value)
    _require_json_value(copied)
    return copied


def _copy_strings(values: Sequence[str]) -> list[str]:
    copied = list(values)
    for value in copied:
        _require_nonempty(value, field_name="sequence item")
    return copied


@dataclass(frozen=True)
class ArtifactRecord:
    """One immutable output artifact referenced by a manifest or claim."""

    path: str
    sha256: str
    media_type: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.path, field_name="path")
        _require_sha256(self.sha256, field_name="sha256")
        if self.media_type is not None:
            _require_nonempty(self.media_type, field_name="media_type")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "media_type": self.media_type,
        }


@dataclass(frozen=True)
class RepositoryState:
    """Git provenance for one benchmark invocation."""

    root: str
    commit: str | None
    dirty: bool | None

    def __post_init__(self) -> None:
        _require_nonempty(self.root, field_name="root")
        if self.commit is not None:
            _require_nonempty(self.commit, field_name="commit")
        if self.dirty is not None and not isinstance(self.dirty, bool):
            raise TypeError("dirty must be bool or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "commit": self.commit,
            "dirty": self.dirty,
        }


@dataclass(frozen=True)
class BenchmarkManifest:
    """Environment, command, input, policy, and artifact provenance."""

    created_at_utc: str
    suite_version: str
    command: tuple[str, ...]
    output_root: str
    repository: RepositoryState
    environment: Mapping[str, Any]
    fixture_hashes: Mapping[str, str] = field(default_factory=dict)
    policy_settings: Mapping[str, Any] = field(default_factory=dict)
    seeds: Mapping[str, int] = field(default_factory=dict)
    selected_claims: tuple[ClaimId, ...] = field(default_factory=tuple)
    artifacts: tuple[ArtifactRecord, ...] = field(default_factory=tuple)
    schema: str = BENCHMARK_MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, BENCHMARK_MANIFEST_SCHEMA)
        _require_nonempty(self.created_at_utc, field_name="created_at_utc")
        _require_nonempty(self.suite_version, field_name="suite_version")
        _require_nonempty(self.output_root, field_name="output_root")
        if not self.command:
            raise ValueError("command must contain at least one token")
        _copy_strings(self.command)
        if not isinstance(self.repository, RepositoryState):
            raise TypeError("repository must be a RepositoryState")
        _copy_mapping(self.environment)
        fixture_hashes = _copy_mapping(self.fixture_hashes)
        for name, digest in fixture_hashes.items():
            _require_nonempty(name, field_name="fixture hash name")
            _require_sha256(digest, field_name=f"fixture_hashes[{name!r}]")
        _copy_mapping(self.policy_settings)
        seeds = _copy_mapping(self.seeds)
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in seeds.values()
        ):
            raise TypeError("all manifest seeds must be integers")
        if any(not isinstance(claim, ClaimId) for claim in self.selected_claims):
            raise TypeError("selected_claims must contain only ClaimId values")
        if any(not isinstance(artifact, ArtifactRecord) for artifact in self.artifacts):
            raise TypeError("artifacts must contain only ArtifactRecord values")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "suite_version": self.suite_version,
            "created_at_utc": self.created_at_utc,
            "command": list(self.command),
            "output_root": self.output_root,
            "repository": self.repository.to_dict(),
            "environment": _copy_mapping(self.environment),
            "fixture_hashes": _copy_mapping(self.fixture_hashes),
            "policy_settings": _copy_mapping(self.policy_settings),
            "seeds": dict(self.seeds),
            "selected_claims": [claim.value for claim in self.selected_claims],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclass(frozen=True)
class ClaimResult:
    """Disposition and evidence references for one stable manuscript claim."""

    claim_id: ClaimId
    status: ClaimStatus
    summary: str
    evidence_files: tuple[str, ...] = field(default_factory=tuple)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)
    suite_version: str = CLAIM_SUITE_VERSION
    schema: str = CLAIM_RESULT_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, CLAIM_RESULT_SCHEMA)
        if not isinstance(self.claim_id, ClaimId):
            raise TypeError("claim_id must be a ClaimId")
        if not isinstance(self.status, ClaimStatus):
            raise TypeError("status must be a ClaimStatus")
        _require_nonempty(self.summary, field_name="summary")
        _require_nonempty(self.suite_version, field_name="suite_version")
        evidence = _copy_strings(self.evidence_files)
        _copy_mapping(self.metrics)
        _copy_strings(self.notes)
        if self.status is ClaimStatus.NOT_RUN and evidence:
            raise ValueError("not_run claims must not cite scientific evidence")
        if self.status is not ClaimStatus.NOT_RUN and not evidence:
            raise ValueError(
                f"{self.status.value} claims must cite at least one evidence file"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "suite_version": self.suite_version,
            "claim_id": self.claim_id.value,
            "status": self.status.value,
            "summary": self.summary,
            "evidence_files": list(self.evidence_files),
            "metrics": _copy_mapping(self.metrics),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class RawExternalMatch:
    """Lossless external-tool record before CALM-specific projection."""

    tool: str
    tool_version: str
    fixture_id: str
    raw_index: int
    payload: Mapping[str, Any]
    schema: str = RAW_EXTERNAL_MATCH_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, RAW_EXTERNAL_MATCH_SCHEMA)
        _require_nonempty(self.tool, field_name="tool")
        _require_nonempty(self.tool_version, field_name="tool_version")
        _require_nonempty(self.fixture_id, field_name="fixture_id")
        if self.raw_index < 0:
            raise ValueError("raw_index must be nonnegative")
        _copy_mapping(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "fixture_id": self.fixture_id,
            "raw_index": self.raw_index,
            "payload": _copy_mapping(self.payload),
        }


@dataclass(frozen=True)
class ProjectedMatch:
    """One declared projection of a retained raw external match."""

    source_match_id: str
    projection_kind: str
    status: str
    identity: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    schema: str = PROJECTED_MATCH_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, PROJECTED_MATCH_SCHEMA)
        _require_nonempty(self.source_match_id, field_name="source_match_id")
        _require_nonempty(self.projection_kind, field_name="projection_kind")
        _require_nonempty(self.status, field_name="status")
        _copy_mapping(self.identity)
        _copy_mapping(self.metrics)
        _copy_mapping(self.diagnostics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_match_id": self.source_match_id,
            "projection_kind": self.projection_kind,
            "status": self.status,
            "identity": _copy_mapping(self.identity),
            "metrics": _copy_mapping(self.metrics),
            "diagnostics": _copy_mapping(self.diagnostics),
        }


@dataclass(frozen=True)
class GateCandidate:
    """One common candidate evaluated by several admissibility predicates."""

    candidate_id: str
    population: str
    basis_A: Sequence[Sequence[float]]
    basis_B: Sequence[Sequence[float]]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    schema: str = GATE_CANDIDATE_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, GATE_CANDIDATE_SCHEMA)
        _require_nonempty(self.candidate_id, field_name="candidate_id")
        _require_nonempty(self.population, field_name="population")
        basis_a = [list(row) for row in self.basis_A]
        basis_b = [list(row) for row in self.basis_B]
        if len(basis_a) != 2 or any(len(row) != 2 for row in basis_a):
            raise ValueError("basis_A must be a 2x2 matrix")
        if len(basis_b) != 2 or any(len(row) != 2 for row in basis_b):
            raise ValueError("basis_B must be a 2x2 matrix")
        _require_json_value(basis_a, field_name="basis_A")
        _require_json_value(basis_b, field_name="basis_B")
        _copy_mapping(self.parameters)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "candidate_id": self.candidate_id,
            "population": self.population,
            "basis_A": [list(row) for row in self.basis_A],
            "basis_B": [list(row) for row in self.basis_B],
            "parameters": _copy_mapping(self.parameters),
        }


@dataclass(frozen=True)
class GateDecision:
    """Decision of one named admissibility predicate on one common candidate."""

    candidate_id: str
    gate_id: str
    admitted: bool
    measurements: Mapping[str, Any]
    thresholds: Mapping[str, Any]
    schema: str = GATE_DECISION_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, GATE_DECISION_SCHEMA)
        _require_nonempty(self.candidate_id, field_name="candidate_id")
        _require_nonempty(self.gate_id, field_name="gate_id")
        _copy_mapping(self.measurements)
        _copy_mapping(self.thresholds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "candidate_id": self.candidate_id,
            "gate_id": self.gate_id,
            "admitted": self.admitted,
            "measurements": _copy_mapping(self.measurements),
            "thresholds": _copy_mapping(self.thresholds),
        }


@dataclass(frozen=True)
class ReferenceComparison:
    """Exact set comparison between production and independent reference keys."""

    fixture_id: str
    domain: Mapping[str, Any]
    production_key_digest: str
    reference_key_digest: str
    production_count: int
    reference_count: int
    missing_keys: tuple[str, ...] = field(default_factory=tuple)
    unexpected_keys: tuple[str, ...] = field(default_factory=tuple)
    schema: str = REFERENCE_COMPARISON_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, REFERENCE_COMPARISON_SCHEMA)
        _require_nonempty(self.fixture_id, field_name="fixture_id")
        _copy_mapping(self.domain)
        for field_name, digest in (
            ("production_key_digest", self.production_key_digest),
            ("reference_key_digest", self.reference_key_digest),
        ):
            _require_sha256(digest, field_name=field_name)
        if self.production_count < 0 or self.reference_count < 0:
            raise ValueError("reference comparison counts must be nonnegative")
        _copy_strings(self.missing_keys)
        _copy_strings(self.unexpected_keys)

    @property
    def exact_match(self) -> bool:
        return (
            self.production_key_digest == self.reference_key_digest
            and self.production_count == self.reference_count
            and not self.missing_keys
            and not self.unexpected_keys
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "fixture_id": self.fixture_id,
            "domain": _copy_mapping(self.domain),
            "production_key_digest": self.production_key_digest,
            "reference_key_digest": self.reference_key_digest,
            "production_count": self.production_count,
            "reference_count": self.reference_count,
            "missing_keys": list(self.missing_keys),
            "unexpected_keys": list(self.unexpected_keys),
            "exact_match": self.exact_match,
        }


@dataclass(frozen=True)
class IdentityPolicyObservation:
    """One hand-declared policy-sensitive coupled-identity expectation."""

    observation_id: str
    claim_id: ClaimId
    category: str
    expected_outcome: str
    actual_outcome: str
    passed: bool
    policy: Mapping[str, Any]
    baseline: Mapping[str, Any]
    variant: Mapping[str, Any]
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    schema: str = IDENTITY_POLICY_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, IDENTITY_POLICY_OBSERVATION_SCHEMA)
        _require_nonempty(self.observation_id, field_name="observation_id")
        if self.claim_id not in {
            ClaimId.C3_COUPLED_IDENTITY,
            ClaimId.C4_REPRESENTATION_INVARIANCE,
        }:
            raise ValueError("identity-policy observations must evaluate C3 or C4")
        _require_nonempty(self.category, field_name="category")
        _require_nonempty(self.expected_outcome, field_name="expected_outcome")
        _require_nonempty(self.actual_outcome, field_name="actual_outcome")
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool")
        _copy_mapping(self.policy)
        _copy_mapping(self.baseline)
        _copy_mapping(self.variant)
        _copy_mapping(self.diagnostics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "observation_id": self.observation_id,
            "claim_id": self.claim_id.value,
            "category": self.category,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "passed": self.passed,
            "policy": _copy_mapping(self.policy),
            "baseline": _copy_mapping(self.baseline),
            "variant": _copy_mapping(self.variant),
            "diagnostics": _copy_mapping(self.diagnostics),
        }


@dataclass(frozen=True)
class MetamorphicObservation:
    """One representation transformation with an explicit expected relation."""

    observation_id: str
    transformation: str
    expected_relation: str
    actual_relation: str
    passed: bool
    policy: Mapping[str, Any]
    baseline: Mapping[str, Any]
    transformed: Mapping[str, Any]
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    claim_id: ClaimId = ClaimId.C4_REPRESENTATION_INVARIANCE
    schema: str = METAMORPHIC_OBSERVATION_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, METAMORPHIC_OBSERVATION_SCHEMA)
        _require_nonempty(self.observation_id, field_name="observation_id")
        if self.claim_id is not ClaimId.C4_REPRESENTATION_INVARIANCE:
            raise ValueError("metamorphic observations evaluate claim C4")
        _require_nonempty(self.transformation, field_name="transformation")
        _require_nonempty(self.expected_relation, field_name="expected_relation")
        _require_nonempty(self.actual_relation, field_name="actual_relation")
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool")
        _copy_mapping(self.policy)
        _copy_mapping(self.baseline)
        _copy_mapping(self.transformed)
        _copy_mapping(self.diagnostics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "observation_id": self.observation_id,
            "claim_id": self.claim_id.value,
            "transformation": self.transformation,
            "expected_relation": self.expected_relation,
            "actual_relation": self.actual_relation,
            "passed": self.passed,
            "policy": _copy_mapping(self.policy),
            "baseline": _copy_mapping(self.baseline),
            "transformed": _copy_mapping(self.transformed),
            "diagnostics": _copy_mapping(self.diagnostics),
        }


@dataclass(frozen=True)
class SearchExtensionSnapshot:
    """One cumulative production-search inventory at a declared finite bound."""

    fixture_id: str
    k_max: int
    implementation: str
    key_digest: str
    identity_digest: str
    inventory: Sequence[Mapping[str, Any]]
    audit_totals: Mapping[str, int]
    oracle_status: str
    elapsed_seconds: float
    schema: str = SEARCH_EXTENSION_SNAPSHOT_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, SEARCH_EXTENSION_SNAPSHOT_SCHEMA)
        _require_nonempty(self.fixture_id, field_name="fixture_id")
        if self.k_max <= 0:
            raise ValueError("k_max must be positive")
        _require_nonempty(self.implementation, field_name="implementation")
        _require_sha256(self.key_digest, field_name="key_digest")
        _require_sha256(self.identity_digest, field_name="identity_digest")
        if not self.inventory:
            raise ValueError("inventory must contain at least one class")
        for index, row in enumerate(self.inventory):
            _copy_mapping(row)
            if "pair_key" not in row:
                raise ValueError(f"inventory[{index}] must contain pair_key")
        totals = _copy_mapping(self.audit_totals)
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in totals.values()
        ):
            raise TypeError("audit_totals values must be nonnegative integers")
        _require_nonempty(self.oracle_status, field_name="oracle_status")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "fixture_id": self.fixture_id,
            "k_max": self.k_max,
            "implementation": self.implementation,
            "key_digest": self.key_digest,
            "identity_digest": self.identity_digest,
            "class_count": len(self.inventory),
            "inventory": [_copy_mapping(row) for row in self.inventory],
            "audit_totals": dict(self.audit_totals),
            "oracle_status": self.oracle_status,
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass(frozen=True)
class SearchExtensionTransition:
    """One adjacent-bound comparison for cumulative search-extension stability."""

    fixture_id: str
    previous_k_max: int
    current_k_max: int
    passed: bool
    checks: Mapping[str, bool]
    new_keys: Sequence[str] = field(default_factory=tuple)
    disappeared_keys: Sequence[str] = field(default_factory=tuple)
    violations: Sequence[str] = field(default_factory=tuple)
    schema: str = SEARCH_EXTENSION_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, SEARCH_EXTENSION_TRANSITION_SCHEMA)
        _require_nonempty(self.fixture_id, field_name="fixture_id")
        if self.previous_k_max <= 0:
            raise ValueError("previous_k_max must be positive")
        if self.current_k_max != self.previous_k_max + 1:
            raise ValueError("transitions must compare adjacent cumulative bounds")
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool")
        checks = _copy_mapping(self.checks)
        if not checks or any(not isinstance(value, bool) for value in checks.values()):
            raise TypeError("checks must contain one or more boolean values")
        _copy_strings(self.new_keys)
        _copy_strings(self.disappeared_keys)
        _copy_strings(self.violations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "fixture_id": self.fixture_id,
            "previous_k_max": self.previous_k_max,
            "current_k_max": self.current_k_max,
            "passed": self.passed,
            "checks": dict(self.checks),
            "new_keys": list(self.new_keys),
            "disappeared_keys": list(self.disappeared_keys),
            "violations": list(self.violations),
        }


@dataclass(frozen=True)
class PerformanceMeasurement:
    """One isolated timing and memory observation guarded by an output digest."""

    implementation: str
    fixture_id: str
    repetition: int
    elapsed_seconds: float
    peak_rss_bytes: int | None
    output_digest: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    schema: str = PERFORMANCE_MEASUREMENT_SCHEMA

    def __post_init__(self) -> None:
        _require_schema(self.schema, PERFORMANCE_MEASUREMENT_SCHEMA)
        _require_nonempty(self.implementation, field_name="implementation")
        _require_nonempty(self.fixture_id, field_name="fixture_id")
        _require_sha256(self.output_digest, field_name="output_digest")
        if self.repetition < 0:
            raise ValueError("repetition must be nonnegative")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be finite and nonnegative")
        if self.peak_rss_bytes is not None and self.peak_rss_bytes < 0:
            raise ValueError("peak_rss_bytes must be nonnegative")
        _copy_mapping(self.parameters)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "implementation": self.implementation,
            "fixture_id": self.fixture_id,
            "repetition": self.repetition,
            "elapsed_seconds": self.elapsed_seconds,
            "peak_rss_bytes": self.peak_rss_bytes,
            "output_digest": self.output_digest,
            "parameters": _copy_mapping(self.parameters),
        }
