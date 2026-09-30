"""Validate the coupled-matching performance matrix and runner contract."""

from __future__ import annotations

from typing import Any

from .common import unique_string_fields, workload_mapping

EXPECTED_SCHEMA = "calm.compute_performance_matrix/v1"
EXPECTED_EQUAL_SQUARE = {
    "coupled_equal_square_k5": 5,
    "coupled_equal_square_k10": 10,
    "coupled_equal_square_k20": 20,
    "coupled_equal_square_k30": 30,
}
EXPECTED_GEOMETRY = {
    "coupled_rectangular_k5": "rect_small_mismatch",
    "coupled_hexagonal_k5": "hex_near_degenerate",
    "coupled_oblique_k5": "oblique_tradeoff",
}
REQUIRED_CORRECTNESS_FIELDS = {
    "implementation",
    "oracle_status",
    "pair_key_version",
    "pair_key_sha256",
    "pair_identity_sha256",
    "class_count",
    "source_count_total",
    "correspondence_column_pairs_tested",
    "unimodular_correspondences_tested",
    "strain_admissible_correspondences",
    "primitive_classes_created",
    "sources_aggregated_by_pair_key",
}
_FORBIDDEN_THRESHOLD_KEYS = {
    "maximum_seconds",
    "minimum_speedup",
    "absolute_time_limit",
    "pass_seconds",
}


def validate_coupled_matrix(
    matrix: dict[str, Any],
    *,
    runner_text: str,
    errors: list[str],
) -> dict[str, Any]:
    if matrix.get("schema") != EXPECTED_SCHEMA:
        errors.append(
            "performance matrix schema must be "
            f"{EXPECTED_SCHEMA!r}, observed {matrix.get('schema')!r}"
        )
    if matrix.get("roadmap_series") != "0337" or matrix.get("update") != "0337a":
        errors.append(
            "performance matrix must identify roadmap series 0337 update 0337a"
        )

    repeats = matrix.get("default_repeats")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 3:
        errors.append(
            "default_repeats must be an integer greater than or equal to three"
        )
    memory_repeats = matrix.get("default_memory_repeats")
    if (
        isinstance(memory_repeats, bool)
        or not isinstance(memory_repeats, int)
        or memory_repeats < 1
    ):
        errors.append("default_memory_repeats must be a positive integer")
    warmups = matrix.get("default_warmup_runs")
    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 1:
        errors.append("default_warmup_runs must be a positive integer")

    correctness = unique_string_fields(
        matrix.get("correctness_fields"),
        label="correctness_fields",
        errors=errors,
    )
    missing = sorted(REQUIRED_CORRECTNESS_FIELDS - correctness)
    if missing:
        errors.append(
            "performance matrix is missing correctness fields: " + ", ".join(missing)
        )

    by_id = workload_mapping(matrix.get("workloads"), label="", errors=errors)
    expected_ids = set(EXPECTED_EQUAL_SQUARE) | set(EXPECTED_GEOMETRY)
    if set(by_id) != expected_ids:
        errors.append(
            "performance workload ids must match the reviewed 0337a set: "
            f"expected={sorted(expected_ids)}, observed={sorted(by_id)}"
        )
    for identifier, k_max in EXPECTED_EQUAL_SQUARE.items():
        workload = by_id.get(identifier, {})
        if workload.get("case") != "equal_square" or workload.get("k_max") != k_max:
            errors.append(f"{identifier} must own equal_square at K={k_max}")
        if workload.get("modes") != ["cold_process", "warm_process"]:
            errors.append(f"{identifier} must measure cold_process and warm_process")
    for identifier, case in EXPECTED_GEOMETRY.items():
        workload = by_id.get(identifier, {})
        if workload.get("case") != case or workload.get("k_max") != 5:
            errors.append(f"{identifier} must own {case} at K=5")
        if workload.get("modes") != ["cold_process", "warm_process"]:
            errors.append(f"{identifier} must measure cold_process and warm_process")

    profiles = [
        identifier
        for identifier, workload in by_id.items()
        if workload.get("profile") is True
    ]
    if profiles != ["coupled_equal_square_k20"]:
        errors.append(
            "the primary cumulative-time profile workload must be exactly "
            "coupled_equal_square_k20"
        )

    if _FORBIDDEN_THRESHOLD_KEYS & set(matrix):
        errors.append(
            "performance matrix must not define machine-independent timing thresholds"
        )
    for identifier, workload in by_id.items():
        forbidden = _FORBIDDEN_THRESHOLD_KEYS & set(workload)
        if forbidden:
            errors.append(
                f"workload {identifier!r} defines forbidden timing thresholds: "
                f"{sorted(forbidden)}"
            )

    required_runner_fragments = (
        'PERFORMANCE_SCHEMA = "calm.compute_performance_qualification/v2"',
        "run_cold_process_measurements",
        "run_warm_process_measurements",
        "validate_measurement_equivalence",
        "profile_workload",
        "peak_process_bytes",
        "process_memory_comparison_mode",
        "timing_thresholds",
    )
    for fragment in required_runner_fragments:
        if fragment not in runner_text:
            errors.append(f"performance runner is missing contract owner {fragment!r}")

    return {
        "schema": matrix.get("schema"),
        "workload_count": len(by_id),
        "profile_workloads": profiles,
        "correctness_field_count": len(correctness),
    }
