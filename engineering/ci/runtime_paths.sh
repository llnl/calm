#!/usr/bin/env bash
# Compute deterministic, job-local runtime paths outside the Jacamar checkout.

calm_ci_runtime_dir() {
    local base uid job_id

    base="${CALM_CI_RUNTIME_BASE:-/var/tmp}"
    case "$base" in
        ""|/)
            printf 'ERROR: unsafe CALM_CI_RUNTIME_BASE: %q\n' "$base" >&2
            return 2
            ;;
    esac

    uid="$(id -u)"
    job_id="${CI_JOB_ID:-local-$$}"
    case "$job_id" in
        *[!A-Za-z0-9._-]*)
            printf 'ERROR: unsafe CI job identifier: %q\n' "$job_id" >&2
            return 2
            ;;
    esac

    printf '%s/calm-ci-%s/%s\n' "${base%/}" "$uid" "$job_id"
}

calm_ci_runtime_python() {
    printf '%s/venv/bin/python\n' "$(calm_ci_runtime_dir)"
}
