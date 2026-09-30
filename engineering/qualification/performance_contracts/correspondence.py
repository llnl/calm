"""Validate the direct-correspondence performance matrix and runner contract."""

from __future__ import annotations

from typing import Any

from .common import unique_string_fields, workload_mapping

EXPECTED_SCHEMA = "calm.correspondence_performance_matrix/v2"
EXPECTED_WORKLOADS = {
    "correspondence_small_skew_all": 48,
    "correspondence_isotropic_annulus_proper": 1_597_696,
    "correspondence_anisotropic_skew_all": 667_000,
}
REQUIRED_FIELDS = {
    "implementation",
    "transform_key_sha256",
    "reference_record_sha256",
    "correspondence_count",
    "required_entry_bound",
    "first_column_candidates",
    "second_column_candidates",
    "column_pairs_tested",
    "unimodular_states_tested",
    "strain_admissible_states",
}


def validate_correspondence_matrix(
    matrix: dict[str, Any],
    *,
    runner_text: str,
    errors: list[str],
) -> dict[str, Any]:
    if matrix.get("schema") != EXPECTED_SCHEMA:
        errors.append(
            "correspondence performance matrix schema must be "
            f"{EXPECTED_SCHEMA!r}, observed {matrix.get('schema')!r}"
        )
    if matrix.get("roadmap_series") != "0337" or matrix.get("update") != "0337d":
        errors.append(
            "correspondence performance matrix must identify roadmap series "
            "0337 update 0337d"
        )
    fields = unique_string_fields(
        matrix.get("correctness_fields"),
        label="correspondence correctness_fields",
        errors=errors,
    )
    missing = sorted(REQUIRED_FIELDS - fields)
    if missing:
        errors.append(
            "correspondence performance matrix is missing correctness fields: "
            + ", ".join(missing)
        )
    by_id = workload_mapping(
        matrix.get("workloads"),
        label="correspondence",
        errors=errors,
    )
    if set(by_id) != set(EXPECTED_WORKLOADS):
        errors.append(
            "correspondence workload ids must match the reviewed 0337d set: "
            f"expected={sorted(EXPECTED_WORKLOADS)}, observed={sorted(by_id)}"
        )
    for identifier, pair_count in EXPECTED_WORKLOADS.items():
        workload = by_id.get(identifier, {})
        expected = workload.get("expected")
        if not isinstance(expected, dict) or expected.get("column_pairs_tested") != pair_count:
            errors.append(f"{identifier} must freeze column_pairs_tested={pair_count}")
        atol = workload.get("strain_reference_atol")
        if (
            isinstance(atol, bool)
            or not isinstance(atol, (int, float))
            or float(atol) != 1e-10
        ):
            errors.append(f"{identifier} must define strain_reference_atol=1e-10")
        if (
            not isinstance(expected, dict)
            or not isinstance(expected.get("reference_record_sha256"), str)
            or len(expected["reference_record_sha256"]) != 64
        ):
            errors.append(f"{identifier} must freeze one reference_record_sha256")
    profiles = sorted(
        identifier
        for identifier, workload in by_id.items()
        if workload.get("profile") is True
    )
    if profiles != [
        "correspondence_anisotropic_skew_all",
        "correspondence_isotropic_annulus_proper",
    ]:
        errors.append("the two high-workload correspondence families must own profiles")

    required_runner_fragments = (
        'REPORT_SCHEMA = "calm.correspondence_performance_qualification/v2"',
        "run_workload_trial",
        "cold_cache",
        "warm_cache",
        "determinant_chunks",
        "transform_key_sha256",
        "reference_record_sha256",
        "observed_record_sha256",
        "max_abs_strain_reference_error",
        "_reference_generalized_eigenvalues",
    )
    for fragment in required_runner_fragments:
        if fragment not in runner_text:
            errors.append(
                "correspondence performance runner is missing contract owner "
                f"{fragment!r}"
            )
    return {
        "schema": matrix.get("schema"),
        "workload_count": len(by_id),
        "profile_workloads": profiles,
    }
