"""Validate the registry performance matrix and runner contract."""

from __future__ import annotations

from typing import Any

from .common import unique_string_fields, workload_mapping

EXPECTED_SCHEMA = "calm.registry_performance_matrix/v2"
EXPECTED_WORKLOADS = {
    "registry_small_64_atoms_80_steps": (32, 80),
    "registry_medium_600_atoms_400_steps": (300, 400),
    "registry_large_2400_atoms_200_steps": (1200, 200),
}
REQUIRED_FIELDS = {
    "proposal_count",
    "trajectory_sha256",
    "score_trace_sha256",
    "best_translation_hex",
    "best_score_quantized",
    "n_steps",
    "n_accepted",
    "objective_evaluations",
    "atom_count",
}
REQUIRED_DIAGNOSTIC_FIELDS = {"observed_proposal_trace_sha256"}


def validate_registry_matrix(
    matrix: dict[str, Any],
    *,
    runner_text: str,
    errors: list[str],
) -> dict[str, Any]:
    if matrix.get("schema") != EXPECTED_SCHEMA:
        errors.append(
            "registry performance matrix schema must be "
            f"{EXPECTED_SCHEMA!r}, observed {matrix.get('schema')!r}"
        )
    if matrix.get("roadmap_series") != "0337" or matrix.get("update") != "0337e":
        errors.append(
            "registry performance matrix must identify roadmap series 0337 update 0337e"
        )
    fields = unique_string_fields(
        matrix.get("correctness_fields"),
        label="registry correctness_fields",
        errors=errors,
    )
    missing = sorted(REQUIRED_FIELDS - fields)
    if missing:
        errors.append(
            "registry performance matrix is missing correctness fields: "
            + ", ".join(missing)
        )
    diagnostics = unique_string_fields(
        matrix.get("diagnostic_fields"),
        label="registry diagnostic_fields",
        errors=errors,
    )
    missing_diagnostics = sorted(REQUIRED_DIAGNOSTIC_FIELDS - diagnostics)
    if missing_diagnostics:
        errors.append(
            "registry performance matrix is missing diagnostic fields: "
            + ", ".join(missing_diagnostics)
        )
    overlap = sorted(fields & diagnostics)
    if overlap:
        errors.append(
            "registry correctness and diagnostic fields must be disjoint: "
            + ", ".join(overlap)
        )
    by_id = workload_mapping(matrix.get("workloads"), label="registry", errors=errors)
    if set(by_id) != set(EXPECTED_WORKLOADS):
        errors.append(
            "registry workload ids must match the reviewed 0337e set: "
            f"expected={sorted(EXPECTED_WORKLOADS)}, observed={sorted(by_id)}"
        )
    for identifier, (atoms_per_slab, n_steps) in EXPECTED_WORKLOADS.items():
        workload = by_id.get(identifier, {})
        if workload.get("atoms_per_slab") != atoms_per_slab:
            errors.append(f"{identifier} must own atoms_per_slab={atoms_per_slab}")
        if workload.get("n_steps") != n_steps:
            errors.append(f"{identifier} must own n_steps={n_steps}")
        expected = workload.get("expected")
        if not isinstance(expected, dict) or set(expected) != REQUIRED_FIELDS:
            errors.append(f"{identifier} must freeze the complete registry signature")
    profiles = sorted(
        identifier
        for identifier, workload in by_id.items()
        if workload.get("profile") is True
    )
    if profiles != [
        "registry_large_2400_atoms_200_steps",
        "registry_medium_600_atoms_400_steps",
    ]:
        errors.append("the medium and large registry workloads must own profiles")

    required_runner_fragments = (
        'REPORT_SCHEMA = "calm.registry_performance_qualification/v2"',
        "rebuild_each_evaluation",
        "prepared_once",
        "observed_proposal_trace_sha256",
        "same_host_diagnostic_only",
        "trajectory_sha256",
        "geometry_preparations",
        "speedup_rebuild_over_prepared",
    )
    for fragment in required_runner_fragments:
        if fragment not in runner_text:
            errors.append(
                "registry performance runner is missing contract owner "
                f"{fragment!r}"
            )
    return {
        "schema": matrix.get("schema"),
        "workload_count": len(by_id),
        "profile_workloads": profiles,
    }
