"""Apply metric and coupled projections to retained ZSL source evidence."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from calm.interface.matching._types import PairIdentityPolicy2D

from .._support import write_canonical_jsonl_atomic
from ..claim_ids import ClaimId
from ..manifest import (
    artifact_record,
    build_manifest,
    sha256_file,
    write_json_atomic,
)
from ..schemas import ProjectedMatch
from .coupled_projection import identity_point_group, project_zsl_coupled_pair
from .metric_projection import project_zsl_metric_pair, source_match_id


ZSL_PROJECTION_SUMMARY_SCHEMA = "calm.zsl_projection_summary/v1"
POINT_GROUP_FILE_SCHEMA = "calm.zsl_projection_point_groups/v1"


@dataclass(frozen=True)
class ZSLProjectionArtifacts:
    """Paths produced by one projection invocation."""

    manifest: Path
    metric_projections: Path
    coupled_projections: Path
    summary: Path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"{path}:{line_number} must contain a JSON object"
                )
            records.append(value)
    return records


def _source_id_from_projection(record: Mapping[str, Any]) -> str:
    value = record.get("source_match_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("projection record is missing source_match_id")
    return value


def _matrix_group(value: Any, *, name: str) -> tuple[np.ndarray, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a nonempty list of 2x2 matrices")
    return tuple(np.asarray(operation) for operation in value)


def load_point_group_file(
    path: str | Path | None,
) -> dict[str, tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]]:
    """Load optional fixture-specific A/B surface groups.

    Without a file, every fixture uses the explicit identity-only relation.
    """

    if path is None:
        return {}
    source = Path(path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != POINT_GROUP_FILE_SCHEMA
    ):
        raise ValueError(
            f"point-group file must use schema {POINT_GROUP_FILE_SCHEMA!r}"
        )
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, dict):
        raise ValueError("point-group file must contain a fixtures mapping")
    result: dict[str, tuple[tuple[np.ndarray, ...], tuple[np.ndarray, ...]]] = {}
    for fixture, value in fixtures.items():
        if not isinstance(fixture, str) or not fixture.strip():
            raise ValueError("point-group fixture identifiers must be nonempty")
        if not isinstance(value, dict):
            raise ValueError(f"point-group fixture {fixture!r} must be a mapping")
        result[fixture] = (
            _matrix_group(value.get("A"), name=f"fixtures[{fixture!r}].A"),
            _matrix_group(value.get("B"), name=f"fixtures[{fixture!r}].B"),
        )
    return result


def _fixture_from_raw(record: Mapping[str, Any]) -> str:
    value = record.get("fixture_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("raw match is missing fixture_id")
    return value


def _identity_key(record: ProjectedMatch, name: str) -> Any:
    return record.identity.get(name) if record.status == "projected" else None


def _multiplicity(counter: Counter[Any], *, key_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, count in sorted(counter.items(), key=lambda item: repr(item[0])):
        serialized = list(key) if isinstance(key, tuple) else key
        rows.append({key_name: serialized, "count": int(count)})
    return rows


def project_captured_zsl_sources(
    *,
    capture_root: str | Path,
    output_root: str | Path,
    repository_root: str | Path,
    command: Sequence[str],
    pair_symmetry_policy: str = "full",
    correspondence_orientation: str = "proper",
    identify_material_exchange: bool = False,
    pair_key_version: int = 1,
    metric_signature_tolerance: float = 1.0e-12,
    metric_signature_scale: float = 1.0e10,
    surface_metric_tolerance: float = 1.0e-8,
    point_groups_by_fixture: Mapping[
        str,
        tuple[Sequence[np.ndarray], Sequence[np.ndarray]],
    ] | None = None,
) -> ZSLProjectionArtifacts:
    """Apply both projections while retaining one output per raw ZSL match."""

    capture = Path(capture_root).expanduser().resolve()
    raw_path = capture / "raw_zsl_matches.jsonl"
    reconstruction_path = capture / "zsl_source_reconstruction.jsonl"
    if not raw_path.is_file() or not reconstruction_path.is_file():
        raise FileNotFoundError(
            "capture_root must contain raw_zsl_matches.jsonl and "
            "zsl_source_reconstruction.jsonl"
        )

    raw_records = _read_jsonl(raw_path)
    reconstruction_records = _read_jsonl(reconstruction_path)
    raw_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_records:
        match_id = source_match_id(raw)
        if match_id in raw_by_id:
            raise ValueError(f"duplicate raw source_match_id {match_id!r}")
        raw_by_id[match_id] = raw
    reconstruction_by_id: dict[str, dict[str, Any]] = {}
    for reconstruction in reconstruction_records:
        match_id = _source_id_from_projection(reconstruction)
        if match_id in reconstruction_by_id:
            raise ValueError(f"duplicate reconstruction source_match_id {match_id!r}")
        reconstruction_by_id[match_id] = reconstruction
    if set(raw_by_id) != set(reconstruction_by_id):
        missing_reconstruction = sorted(set(raw_by_id) - set(reconstruction_by_id))
        missing_raw = sorted(set(reconstruction_by_id) - set(raw_by_id))
        raise ValueError(
            "raw and reconstruction source identifiers differ: "
            f"missing_reconstruction={missing_reconstruction}, "
            f"missing_raw={missing_raw}"
        )

    policy = PairIdentityPolicy2D(
        pair_symmetry=pair_symmetry_policy,  # type: ignore[arg-type]
        correspondence_orientation=correspondence_orientation,  # type: ignore[arg-type]
        identify_material_exchange=identify_material_exchange,
        key_version=pair_key_version,
    )
    group_mapping = dict(point_groups_by_fixture or {})
    metric_records: list[ProjectedMatch] = []
    coupled_records: list[ProjectedMatch] = []
    fixture_group_modes: dict[str, str] = {}

    for match_id in sorted(raw_by_id):
        raw = raw_by_id[match_id]
        fixture = _fixture_from_raw(raw)
        metric_records.append(
            project_zsl_metric_pair(
                raw,
                signature_tolerance=metric_signature_tolerance,
                signature_scale=metric_signature_scale,
            )
        )
        groups = group_mapping.get(fixture)
        if groups is None:
            group_a = identity_point_group()
            group_b = identity_point_group()
            fixture_group_modes.setdefault(fixture, "identity_only")
        else:
            group_a, group_b = groups
            fixture_group_modes.setdefault(fixture, "explicit")
        coupled_records.append(
            project_zsl_coupled_pair(
                raw,
                reconstruction_by_id[match_id],
                policy=policy,
                point_group_A=group_a,
                point_group_B=group_b,
                surface_metric_tolerance=surface_metric_tolerance,
            )
        )

    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    metric_path = write_canonical_jsonl_atomic(
        root / "zsl_metric_projection.jsonl",
        (record.to_dict() for record in metric_records),
    )
    coupled_path = write_canonical_jsonl_atomic(
        root / "zsl_coupled_projection.jsonl",
        (record.to_dict() for record in coupled_records),
    )

    metric_statuses = Counter(record.status for record in metric_records)
    coupled_statuses = Counter(record.status for record in coupled_records)
    metric_signatures = Counter(
        value
        for record in metric_records
        if (value := _identity_key(record, "metric_pair_signature")) is not None
    )
    source_pairs = Counter(
        value
        for record in coupled_records
        if (value := record.identity.get("source_pair_sha256")) is not None
    )
    primitive_keys = Counter(
        tuple(value)
        for record in coupled_records
        if (value := _identity_key(record, "primitive_pair_key")) is not None
    )
    summary_payload = {
        "schema": ZSL_PROJECTION_SUMMARY_SCHEMA,
        "suite_version": "claims_v1",
        "claim_id": ClaimId.C7_ZSL_COMPARISON.value,
        "scientific_claim_evaluated": False,
        "source_capture": {
            "root": str(capture),
            "raw_matches_sha256": sha256_file(raw_path),
            "reconstructions_sha256": sha256_file(reconstruction_path),
        },
        "raw_match_count": len(raw_records),
        "metric_projection_count": len(metric_records),
        "coupled_projection_count": len(coupled_records),
        "all_raw_matches_retained": (
            len(raw_records) == len(metric_records) == len(coupled_records)
        ),
        "metric_status_counts": dict(sorted(metric_statuses.items())),
        "coupled_status_counts": dict(sorted(coupled_statuses.items())),
        "unique_metric_pair_signature_count": len(metric_signatures),
        "unique_source_pair_count": len(source_pairs),
        "unique_primitive_coupled_pair_key_count": len(primitive_keys),
        "metric_pair_multiplicity": _multiplicity(
            metric_signatures,
            key_name="metric_pair_signature",
        ),
        "source_pair_multiplicity": _multiplicity(
            source_pairs,
            key_name="source_pair_sha256",
        ),
        "primitive_pair_multiplicity": _multiplicity(
            primitive_keys,
            key_name="primitive_pair_key",
        ),
        "identity_policy": {
            "key_version": policy.key_version,
            "pair_symmetry_policy": policy.pair_symmetry,
            "correspondence_orientation": policy.correspondence_orientation,
            "material_exchange_identified": policy.identify_material_exchange,
        },
        "surface_group_modes": dict(sorted(fixture_group_modes.items())),
        "metric_projection_semantics": (
            "Independent one-sided metric canonicalization; not a coupled identity."
        ),
        "coupled_projection_semantics": (
            "External ZSL source pairs classified under CALM's primitive "
            "coupled-pair equivalence relation."
        ),
        "note": (
            "Projection only; controlled CALM-versus-ZSL overlap and claim C7 "
            "evaluation are later roadmap stages."
        ),
    }
    summary_path = write_json_atomic(
        root / "projection_summary.json",
        summary_payload,
    )

    artifacts = (
        artifact_record(
            metric_path,
            relative_to=root,
            media_type="application/x-ndjson",
        ),
        artifact_record(
            coupled_path,
            relative_to=root,
            media_type="application/x-ndjson",
        ),
        artifact_record(summary_path, relative_to=root, media_type="application/json"),
    )
    manifest = build_manifest(
        repository_root=repository_root,
        output_root=root,
        command=command,
        selected_claims=(ClaimId.C7_ZSL_COMPARISON,),
        artifacts=artifacts,
        policy_settings={
            "stage": "zsl_metric_and_coupled_projection",
            "source_capture": {
                "raw_matches_sha256": sha256_file(raw_path),
                "reconstructions_sha256": sha256_file(reconstruction_path),
            },
            "metric_signature": {
                "tolerance": float(metric_signature_tolerance),
                "scale": float(metric_signature_scale),
            },
            "identity_policy": summary_payload["identity_policy"],
            "surface_metric_tolerance": float(surface_metric_tolerance),
            "surface_group_modes": summary_payload["surface_group_modes"],
        },
    )
    manifest_path = write_json_atomic(
        root / "benchmark_manifest.json",
        manifest.to_dict(),
    )
    return ZSLProjectionArtifacts(
        manifest=manifest_path,
        metric_projections=metric_path,
        coupled_projections=coupled_path,
        summary=summary_path,
    )


__all__ = [
    "POINT_GROUP_FILE_SCHEMA",
    "ZSLProjectionArtifacts",
    "ZSL_PROJECTION_SUMMARY_SCHEMA",
    "load_point_group_file",
    "project_captured_zsl_sources",
]
