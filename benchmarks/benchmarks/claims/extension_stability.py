"""C5 cumulative finite-search extension-stability qualification.

Every selected fixture is rerun independently at each cumulative bound
``K = 1, ..., K_max``.  Adjacent inventories are compared by complete primitive
coupled-pair identity and source provenance.  The standard equal-square profile
also checks the frozen full-D4 inventory and first-discovery oracle at every
bound through ``K = 30``.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from ._support import (
    key_text,
    matrix_payload,
    slab_from_basis,
    write_csv_atomic,
    write_jsonl_atomic,
)
from .claim_ids import ClaimId, ClaimStatus
from .differential_search import (
    DifferentialFixture,
    default_differential_fixtures,
)
from .manifest import (
    artifact_record,
    build_manifest,
    canonical_json_bytes,
    sha256_bytes,
    write_json_atomic,
)
from .reference.coupled_match_reference import enumerate_metric_point_group
from .schemas import (
    ClaimResult,
    SearchExtensionSnapshot,
    SearchExtensionTransition,
)


SEARCH_EXTENSION_SUMMARY_SCHEMA = "calm.search_extension_summary/v1"
SEARCH_EXTENSION_FIXTURE_RESULT_SCHEMA = "calm.search_extension_fixture_result/v1"
DEFAULT_PROFILE = "standard"
SUPPORTED_PROFILES = ("smoke", "standard")
IMPLEMENTATION = "primitive_coupled_pair_v2"
DEFAULT_EXACT_STRAIN_TOLERANCE = 1.0e-10
DEFAULT_CONDITION_LIMIT = 1.0e9
DEFAULT_ATOM_LIMIT = 100_000
DEFAULT_WORKERS = 4

_SELECTED_FIXTURE_IDS = (
    "square_standard",
    "rectangular_standard",
    "hexagonal_standard",
    "oblique_standard",
)
_STANDARD_MAX_K = {
    "square_standard": 30,
    "rectangular_standard": 8,
    "hexagonal_standard": 8,
    "oblique_standard": 8,
}
_SMOKE_MAX_K = {
    "square_standard": 5,
    "rectangular_standard": 3,
    "hexagonal_standard": 3,
    "oblique_standard": 3,
}


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _identity_payload(match_class: Any) -> dict[str, Any]:
    representative = match_class.representative
    policy = representative.pair_identity_policy
    canonical = np.asarray(
        representative.pair_canonicalization.canonical_matrix,
        dtype=int,
    )
    return {
        "identity_algorithm": IMPLEMENTATION,
        "key_version": int(policy.key_version),
        "primitive_pair_key": [int(value) for value in match_class.pair_key],
        "canonical_matrix": matrix_payload(canonical),
        "pair_symmetry_policy": str(policy.pair_symmetry),
        "correspondence_orientation": str(policy.correspondence_orientation),
        "material_exchange_identified": bool(policy.identify_material_exchange),
    }


def _class_inventory(match_classes: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for match_class in sorted(match_classes, key=lambda item: tuple(item.pair_key)):
        pair_key = tuple(int(value) for value in match_class.pair_key)
        source_index_pairs = tuple(
            sorted((int(a), int(b)) for a, b in match_class.source_index_pairs)
        )
        repeat_indices = tuple(
            sorted(int(value) for value in match_class.repeat_indices)
        )
        identity = _identity_payload(match_class)
        representative = match_class.representative
        rows.append(
            {
                "pair_key": list(pair_key),
                "pair_key_text": key_text(pair_key),
                "identity": identity,
                "identity_sha256": _digest_payload(identity),
                "source_count": int(match_class.source_count),
                "source_index_pairs": [list(pair) for pair in source_index_pairs],
                "repeat_indices": list(repeat_indices),
                "first_discovery_index": min(
                    max(first, second) for first, second in source_index_pairs
                ),
                "representative": {
                    "primitive_N_A": matrix_payload(representative.primitive_N_A),
                    "primitive_N_B": matrix_payload(representative.primitive_N_B),
                    "atom_count": int(representative.atom_count),
                    "match_score": float(representative.match_score),
                    "max_abs_principal_strain": float(
                        representative.ai_strain.max_abs_principal_strain
                    ),
                },
            }
        )
    return tuple(rows)


def _audit_totals(audit: Any) -> dict[str, int]:
    audit.validate()
    surface_a = audit.surface_A.totals()
    surface_b = audit.surface_B.totals()
    pairs = audit.pairs.totals()
    return {
        **{f"surface_A_{name}": int(value) for name, value in surface_a.items()},
        **{f"surface_B_{name}": int(value) for name, value in surface_b.items()},
        **{f"pairs_{name}": int(value) for name, value in pairs.items()},
    }


def _square_oracle_violations(
    inventory: Sequence[Mapping[str, Any]],
    *,
    k_max: int,
) -> tuple[str, ...]:
    if not 1 <= int(k_max) <= 30:
        return ()
    from benchmarks.benchmarks.qualification_fixtures import (
        FULL_D4_DISCOVERY_BY_INDEX,
        expected_full_d4_keys,
    )

    expected_keys = set(expected_full_d4_keys(k_max))
    observed_by_key = {
        tuple(int(value) for value in row["pair_key"]): row for row in inventory
    }
    observed_keys = set(observed_by_key)
    violations: list[str] = []
    if observed_keys != expected_keys:
        violations.append(
            "frozen full-D4 inventory mismatch: "
            f"expected={sorted(expected_keys)}, observed={sorted(observed_keys)}"
        )
    expected_discoveries = {
        tuple(key): int(first_index)
        for first_index, key in FULL_D4_DISCOVERY_BY_INDEX
        if first_index <= k_max
    }
    observed_discoveries = {
        key: int(row["first_discovery_index"])
        for key, row in observed_by_key.items()
    }
    if observed_discoveries != expected_discoveries:
        violations.append(
            "frozen full-D4 first-discovery mismatch: "
            f"expected={expected_discoveries}, observed={observed_discoveries}"
        )
    return tuple(violations)


@dataclass(frozen=True)
class ExtensionStabilityConfig:
    """Configuration for cumulative C5 production-search reruns."""

    profile: str = DEFAULT_PROFILE
    fixture_ids: tuple[str, ...] = ()
    k_max_override: int | None = None
    eps_principal_max: float = DEFAULT_EXACT_STRAIN_TOLERANCE
    cond_max: float = DEFAULT_CONDITION_LIMIT
    atom_limit: int = DEFAULT_ATOM_LIMIT
    workers: int = DEFAULT_WORKERS

    def __post_init__(self) -> None:
        if self.profile not in SUPPORTED_PROFILES:
            raise ValueError(f"profile must be one of {SUPPORTED_PROFILES}")
        if self.k_max_override is not None and self.k_max_override <= 0:
            raise ValueError("k_max_override must be positive or None")
        if not math.isfinite(self.eps_principal_max) or self.eps_principal_max < 0:
            raise ValueError("eps_principal_max must be finite and nonnegative")
        if not math.isfinite(self.cond_max) or self.cond_max <= 0:
            raise ValueError("cond_max must be finite and positive")
        if self.atom_limit <= 0:
            raise ValueError("atom_limit must be positive")
        if self.workers <= 0:
            raise ValueError("workers must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "fixture_ids": list(self.fixture_ids),
            "k_max_override": self.k_max_override,
            "eps_principal_max": self.eps_principal_max,
            "cond_max": self.cond_max,
            "atom_limit": self.atom_limit,
            "workers": self.workers,
            "pair_symmetry_policy": "full",
            "correspondence_orientation": "proper",
            "identify_material_exchange": False,
            "correspondence_entry_limit": None,
        }


def select_extension_fixtures(
    config: ExtensionStabilityConfig,
) -> tuple[tuple[DifferentialFixture, int], ...]:
    by_id = {
        fixture.fixture_id: fixture for fixture in default_differential_fixtures()
    }
    available = {fixture_id: by_id[fixture_id] for fixture_id in _SELECTED_FIXTURE_IDS}
    if config.fixture_ids:
        unknown = sorted(set(config.fixture_ids) - set(available))
        if unknown:
            raise ValueError(f"unknown extension fixtures: {unknown}")
        fixture_ids = tuple(dict.fromkeys(config.fixture_ids))
    else:
        fixture_ids = _SELECTED_FIXTURE_IDS
    profile_limits = _SMOKE_MAX_K if config.profile == "smoke" else _STANDARD_MAX_K
    return tuple(
        (
            available[fixture_id],
            int(config.k_max_override or profile_limits[fixture_id]),
        )
        for fixture_id in fixture_ids
    )


def _run_snapshot(
    fixture: DifferentialFixture,
    *,
    k_max: int,
    config: ExtensionStabilityConfig,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    from calm.interface.matching._orchestrator import (
        enumerate_coupled_match_classes_core,
    )
    from calm.interface.matching.audit import CoupledMatchEnumerationAudit

    group_a = enumerate_metric_point_group(fixture.metric_a)
    group_b = enumerate_metric_point_group(fixture.metric_b)
    audit = CoupledMatchEnumerationAudit.empty(k_max)
    started = time.perf_counter()
    classes = tuple(
        enumerate_coupled_match_classes_core(
            slab_from_basis(fixture.basis_a),
            slab_from_basis(fixture.basis_b),
            k_max=int(k_max),
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
                np.asarray(operation, dtype=int).reshape(2, 2)
                for operation in group_a
            ),
            point_group_B=tuple(
                np.asarray(operation, dtype=int).reshape(2, 2)
                for operation in group_b
            ),
            audit=audit,
        )
    )
    elapsed = time.perf_counter() - started
    inventory = _class_inventory(classes)
    keys = [row["pair_key"] for row in inventory]
    identities = [row["identity"] for row in inventory]
    oracle_violations = (
        _square_oracle_violations(inventory, k_max=k_max)
        if fixture.fixture_id == "square_standard"
        else ()
    )
    snapshot = SearchExtensionSnapshot(
        fixture_id=fixture.fixture_id,
        k_max=int(k_max),
        implementation=str(audit.implementation),
        key_digest=_digest_payload(keys),
        identity_digest=_digest_payload(identities),
        inventory=inventory,
        audit_totals=_audit_totals(audit),
        oracle_status=(
            "pass"
            if fixture.fixture_id == "square_standard" and not oracle_violations
            else (
                "fail"
                if fixture.fixture_id == "square_standard"
                else "not_applicable"
            )
        ),
        elapsed_seconds=elapsed,
    ).to_dict()
    snapshot.update(
        {
            "fixture_family": fixture.family,
            "fixture_sha256": fixture.sha256(),
            "point_group_A_order": len(group_a),
            "point_group_B_order": len(group_b),
            "oracle_violations": list(oracle_violations),
        }
    )
    return snapshot, oracle_violations


def compare_extension_snapshots(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> SearchExtensionTransition:
    """Compare adjacent cumulative snapshots using exact identity/provenance rules."""

    fixture_id = str(previous["fixture_id"])
    if str(current["fixture_id"]) != fixture_id:
        raise ValueError("snapshots must belong to the same fixture")
    previous_k = int(previous["k_max"])
    current_k = int(current["k_max"])
    if current_k != previous_k + 1:
        raise ValueError("snapshots must compare adjacent cumulative bounds")

    previous_by_key = {
        str(row["pair_key_text"]): row for row in previous["inventory"]
    }
    current_by_key = {
        str(row["pair_key_text"]): row for row in current["inventory"]
    }
    previous_keys = set(previous_by_key)
    current_keys = set(current_by_key)
    disappeared = tuple(sorted(previous_keys - current_keys))
    new_keys = tuple(sorted(current_keys - previous_keys))
    violations: list[str] = []

    identity_stable = True
    source_count_nondecreasing = True
    source_pairs_monotone = True
    repeat_indices_monotone = True
    first_discovery_stable = True
    for key in sorted(previous_keys & current_keys):
        before = previous_by_key[key]
        after = current_by_key[key]
        if before["identity_sha256"] != after["identity_sha256"]:
            identity_stable = False
            violations.append(f"{key}: identity payload changed")
        if int(after["source_count"]) < int(before["source_count"]):
            source_count_nondecreasing = False
            violations.append(
                f"{key}: source_count decreased from {before['source_count']} "
                f"to {after['source_count']}"
            )
        before_pairs = {tuple(pair) for pair in before["source_index_pairs"]}
        after_pairs = {tuple(pair) for pair in after["source_index_pairs"]}
        if not before_pairs <= after_pairs:
            source_pairs_monotone = False
            violations.append(f"{key}: source_index_pairs lost prior members")
        before_repeats = {int(value) for value in before["repeat_indices"]}
        after_repeats = {int(value) for value in after["repeat_indices"]}
        if not before_repeats <= after_repeats:
            repeat_indices_monotone = False
            violations.append(f"{key}: repeat_indices lost prior members")
        if int(before["first_discovery_index"]) != int(
            after["first_discovery_index"]
        ):
            first_discovery_stable = False
            violations.append(f"{key}: first_discovery_index changed")

    new_discovery_consistent = True
    for key in new_keys:
        first_discovery = int(current_by_key[key]["first_discovery_index"])
        if first_discovery != current_k:
            new_discovery_consistent = False
            violations.append(
                f"{key}: first appeared at K={current_k} but reports "
                f"first_discovery_index={first_discovery}"
            )

    audit_nondecreasing = True
    previous_audit = {str(k): int(v) for k, v in previous["audit_totals"].items()}
    current_audit = {str(k): int(v) for k, v in current["audit_totals"].items()}
    if set(previous_audit) != set(current_audit):
        audit_nondecreasing = False
        violations.append("audit total field set changed")
    else:
        for name in sorted(previous_audit):
            if current_audit[name] < previous_audit[name]:
                audit_nondecreasing = False
                violations.append(
                    f"audit {name} decreased from {previous_audit[name]} "
                    f"to {current_audit[name]}"
                )

    checks = {
        "inventory_monotone": not disappeared,
        "identity_payload_stable": identity_stable,
        "source_count_nondecreasing": source_count_nondecreasing,
        "source_index_pairs_monotone": source_pairs_monotone,
        "repeat_indices_monotone": repeat_indices_monotone,
        "first_discovery_stable": first_discovery_stable,
        "new_class_discovery_consistent": new_discovery_consistent,
        "audit_totals_nondecreasing": audit_nondecreasing,
        "implementation_stable": (
            str(previous["implementation"]) == str(current["implementation"])
            == IMPLEMENTATION
        ),
    }
    if not checks["inventory_monotone"]:
        violations.append(f"classes disappeared: {list(disappeared)}")
    if not checks["implementation_stable"]:
        violations.append(
            "implementation identifier changed or was not primitive_coupled_pair_v2"
        )
    passed = all(checks.values())
    return SearchExtensionTransition(
        fixture_id=fixture_id,
        previous_k_max=previous_k,
        current_k_max=current_k,
        passed=passed,
        checks=checks,
        new_keys=new_keys,
        disappeared_keys=disappeared,
        violations=tuple(violations),
    )


def evaluate_extension_fixture(
    fixture: DifferentialFixture,
    *,
    max_k: int,
    config: ExtensionStabilityConfig,
) -> dict[str, Any]:
    """Rerun one fixture at every cumulative bound and compare all transitions."""

    snapshots: list[dict[str, Any]] = []
    oracle_violations: list[str] = []
    bounds = tuple(range(1, int(max_k) + 1))
    if config.workers == 1 or len(bounds) == 1:
        results = tuple(
            _run_snapshot(fixture, k_max=k_max, config=config)
            for k_max in bounds
        )
    else:
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=min(config.workers, len(bounds))
        ) as executor:
            future_by_k = {
                k_max: executor.submit(
                    _run_snapshot,
                    fixture,
                    k_max=k_max,
                    config=config,
                )
                for k_max in bounds
            }
            results = tuple(future_by_k[k_max].result() for k_max in bounds)
    for k_max, (snapshot, violations) in zip(bounds, results):
        snapshots.append(snapshot)
        oracle_violations.extend(f"K={k_max}: {item}" for item in violations)

    transitions = tuple(
        compare_extension_snapshots(previous, current).to_dict()
        for previous, current in zip(snapshots, snapshots[1:])
    )
    introduction_by_key: dict[str, int] = {}
    for snapshot in snapshots:
        k_max = int(snapshot["k_max"])
        for row in snapshot["inventory"]:
            introduction_by_key.setdefault(str(row["pair_key_text"]), k_max)
    final_by_key = {
        str(row["pair_key_text"]): row for row in snapshots[-1]["inventory"]
    }
    introduction_violations = tuple(
        f"{key}: observed introduction K={introduced}, final first-discovery="
        f"{final_by_key[key]['first_discovery_index']}"
        for key, introduced in sorted(introduction_by_key.items())
        if introduced != int(final_by_key[key]["first_discovery_index"])
    )
    all_transition_passed = all(bool(row["passed"]) for row in transitions)
    fixture_passed = (
        all_transition_passed
        and not oracle_violations
        and not introduction_violations
        and all(snapshot["implementation"] == IMPLEMENTATION for snapshot in snapshots)
    )
    return {
        "schema": SEARCH_EXTENSION_FIXTURE_RESULT_SCHEMA,
        "fixture": fixture.to_dict(),
        "fixture_sha256": fixture.sha256(),
        "max_k": int(max_k),
        "snapshot_count": len(snapshots),
        "transition_count": len(transitions),
        "passed": fixture_passed,
        "transition_failure_count": sum(not bool(row["passed"]) for row in transitions),
        "oracle_violations": oracle_violations,
        "introduction_violations": list(introduction_violations),
        "introduction_by_key": introduction_by_key,
        "final_class_count": int(snapshots[-1]["class_count"]),
        "final_key_digest": snapshots[-1]["key_digest"],
        "final_identity_digest": snapshots[-1]["identity_digest"],
        "elapsed_seconds_total": sum(
            float(snapshot["elapsed_seconds"]) for snapshot in snapshots
        ),
        "snapshots": snapshots,
        "transitions": list(transitions),
    }


@dataclass(frozen=True)
class ExtensionStabilityArtifacts:
    manifest: Path
    claim_result: Path
    summary: Path
    summary_csv: Path
    snapshots: Path
    transitions: Path
    fixture_results: Path
    result: ClaimResult

    @property
    def evidence_paths(self) -> tuple[Path, ...]:
        return (
            self.summary,
            self.summary_csv,
            self.snapshots,
            self.transitions,
            self.fixture_results,
        )


def run_extension_stability_qualification(
    *,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    config: ExtensionStabilityConfig,
) -> ExtensionStabilityArtifacts:
    """Execute C5 over cumulative exact-lattice production searches."""

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    selected = select_extension_fixtures(config)
    fixture_results = tuple(
        evaluate_extension_fixture(fixture, max_k=max_k, config=config)
        for fixture, max_k in selected
    )
    snapshot_rows = tuple(
        snapshot
        for fixture_result in fixture_results
        for snapshot in fixture_result["snapshots"]
    )
    transition_rows = tuple(
        transition
        for fixture_result in fixture_results
        for transition in fixture_result["transitions"]
    )
    summary_rows = tuple(
        {
            "schema": SEARCH_EXTENSION_SUMMARY_SCHEMA,
            "fixture_id": result["fixture"]["fixture_id"],
            "family": result["fixture"]["family"],
            "max_k": result["max_k"],
            "snapshot_count": result["snapshot_count"],
            "transition_count": result["transition_count"],
            "final_class_count": result["final_class_count"],
            "introduction_indices": json.dumps(
                sorted(set(result["introduction_by_key"].values())),
                separators=(",", ":"),
            ),
            "transition_failure_count": result["transition_failure_count"],
            "oracle_violation_count": len(result["oracle_violations"]),
            "introduction_violation_count": len(result["introduction_violations"]),
            "elapsed_seconds_total": result["elapsed_seconds_total"],
            "passed": result["passed"],
        }
        for result in fixture_results
    )

    snapshots_path = write_jsonl_atomic(
        root / "search_extension_snapshots.jsonl",
        snapshot_rows,
    )
    transitions_path = write_jsonl_atomic(
        root / "search_extension_transitions.jsonl",
        transition_rows,
    )
    fixture_results_path = write_jsonl_atomic(
        root / "search_extension_fixture_results.jsonl",
        fixture_results,
    )
    summary_csv_path = write_csv_atomic(
        root / "search_extension_summary.csv",
        summary_rows,
    )

    all_passed = all(bool(result["passed"]) for result in fixture_results)
    square_result = next(
        (
            result
            for result in fixture_results
            if result["fixture"]["fixture_id"] == "square_standard"
        ),
        None,
    )
    result = ClaimResult(
        claim_id=ClaimId.C5_EXTENSION_STABILITY,
        status=ClaimStatus.PASS if all_passed else ClaimStatus.FAIL,
        summary=(
            "All cumulative searches preserved prior primitive identities, "
            "first-discovery indices, and nondecreasing source provenance."
            if all_passed
            else "One or more cumulative searches violated inventory, identity, "
            "discovery, source-provenance, audit, or frozen-oracle stability."
        ),
        evidence_files=(
            "search_extension_summary.json",
            "search_extension_summary.csv",
            "search_extension_snapshots.jsonl",
            "search_extension_transitions.jsonl",
            "search_extension_fixture_results.jsonl",
        ),
        metrics={
            "fixture_count": len(fixture_results),
            "snapshot_count": len(snapshot_rows),
            "transition_count": len(transition_rows),
            "passed_fixture_count": sum(
                bool(item["passed"]) for item in fixture_results
            ),
            "failed_fixture_count": sum(
                not bool(item["passed"]) for item in fixture_results
            ),
            "square_max_k": None if square_result is None else square_result["max_k"],
            "square_final_class_count": (
                None if square_result is None else square_result["final_class_count"]
            ),
        },
        notes=(
            "Every selected fixture is rerun independently at each adjacent "
            "cumulative K bound; inventories are not reconstructed from one final run.",
            "The standard square profile checks the frozen full-D4 inventory and "
            "first-discovery oracle at every K through 30.",
            "Rectangular, hexagonal, and generic oblique exact-lattice fixtures "
            "provide smaller cross-family extension checks.",
        ),
    )
    claim_result_path = write_json_atomic(
        root / "claim_result.json",
        result.to_dict(),
    )
    summary_payload = {
        "schema": SEARCH_EXTENSION_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "implementation": IMPLEMENTATION,
        "config": config.to_dict(),
        "claim_result": result.to_dict(),
        "all_passed": all_passed,
        "fixture_count": len(fixture_results),
        "snapshot_count": len(snapshot_rows),
        "transition_count": len(transition_rows),
        "pass_criteria": {
            "inventory": "keys(K) must be a subset of keys(K+1)",
            "identity": "complete policy-qualified identity payloads remain stable",
            "source_count": "nondecreasing for every retained key",
            "source_index_pairs": "set inclusion across adjacent bounds",
            "repeat_indices": "set inclusion across adjacent bounds",
            "first_discovery": "stable and equal to the actual introduction bound",
            "audit": "all cumulative enumeration counts are nondecreasing",
            "square_oracle": "frozen full-D4 inventory through K=30",
        },
        "fixtures": list(summary_rows),
        "legacy_suite_modified": False,
    }
    summary_path = write_json_atomic(
        root / "search_extension_summary.json",
        summary_payload,
    )

    artifacts = (
        artifact_record(summary_path, relative_to=root, media_type="application/json"),
        artifact_record(summary_csv_path, relative_to=root, media_type="text/csv"),
        artifact_record(
            snapshots_path,
            relative_to=root,
            media_type="application/x-ndjson",
        ),
        artifact_record(
            transitions_path,
            relative_to=root,
            media_type="application/x-ndjson",
        ),
        artifact_record(
            fixture_results_path,
            relative_to=root,
            media_type="application/x-ndjson",
        ),
        artifact_record(
            claim_result_path,
            relative_to=root,
            media_type="application/json",
        ),
    )
    fixture_hashes = {
        fixture.fixture_id: sha256_bytes(
            canonical_json_bytes(
                {
                    "fixture_sha256": fixture.sha256(),
                    "max_k": max_k,
                    "config": config.to_dict(),
                }
            )
        )
        for fixture, max_k in selected
    }
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C5_EXTENSION_STABILITY,),
        artifacts=artifacts,
        fixture_hashes=fixture_hashes,
        policy_settings={
            "implementation": IMPLEMENTATION,
            **config.to_dict(),
            "cumulative_rerun_per_bound": True,
            "legacy_suite_modified": False,
        },
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return ExtensionStabilityArtifacts(
        manifest=manifest_path,
        claim_result=claim_result_path,
        summary=summary_path,
        summary_csv=summary_csv_path,
        snapshots=snapshots_path,
        transitions=transitions_path,
        fixture_results=fixture_results_path,
        result=result,
    )


__all__ = [
    "DEFAULT_PROFILE",
    "DEFAULT_WORKERS",
    "ExtensionStabilityArtifacts",
    "ExtensionStabilityConfig",
    "IMPLEMENTATION",
    "SEARCH_EXTENSION_FIXTURE_RESULT_SCHEMA",
    "SEARCH_EXTENSION_SUMMARY_SCHEMA",
    "SUPPORTED_PROFILES",
    "compare_extension_snapshots",
    "evaluate_extension_fixture",
    "run_extension_stability_qualification",
    "select_extension_fixtures",
]
