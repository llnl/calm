#!/usr/bin/env bash
# Preserve enough environment evidence to diagnose failed Jacamar jobs.

set -eo pipefail

repo_root="${CI_PROJECT_DIR:-$PWD}"
cd "$repo_root"
# shellcheck disable=SC1091
source engineering/ci/runtime_paths.sh
mkdir -p build/ci

job_slug="${CI_JOB_NAME_SLUG:-local}"
node_suffix=""
if [ -n "${CI_NODE_INDEX:-}" ]; then
    node_suffix="-${CI_NODE_INDEX}"
fi
output="build/ci/${job_slug}${node_suffix}-environment.txt"
runtime_dir="${CALM_CI_RUNTIME_DIR:-$(calm_ci_runtime_dir)}"
python_bin="${CALM_CI_PYTHON:-$runtime_dir/venv/bin/python}"

redact_stream() {
    sed -E 's#(https?://)[^/@[:space:]]+@#\1<redacted>@#g'
}

redact_value() {
    printf '%s' "$1" | redact_stream
}

{
    printf 'captured_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'job=%s\n' "${CI_JOB_NAME:-local}"
    printf 'runner=%s\n' "${CI_RUNNER_DESCRIPTION:-unknown}"
    printf 'host=%s\n' "$(hostname)"
    printf 'project_dir=%s\n' "$repo_root"
    printf 'runtime_dir=%s\n' "$runtime_dir"
    printf 'runtime_usage_begin\n'
    du -sh "$runtime_dir" 2>/dev/null || true
    printf 'runtime_usage_end\n'
    printf 'git_commit=%s\n' "$(git rev-parse HEAD 2>/dev/null || printf unavailable)"
    printf 'git_status_begin\n'
    git status --short 2>/dev/null || true
    printf 'git_status_end\n'
    printf 'pip_no_cache_dir=%s\n' "${PIP_NO_CACHE_DIR:-<unset>}"
    printf 'pip_index_url=%s\n' "$(redact_value "${PIP_INDEX_URL:-<unset>}")"
    printf 'pip_extra_index_url=%s\n' "$(redact_value "${PIP_EXTRA_INDEX_URL:-<unset>}")"

    if type module >/dev/null 2>&1; then
        printf 'module_list_begin\n'
        module -t list 2>&1 || true
        printf 'module_list_end\n'
    fi

    if [ -x "$python_bin" ]; then
        "$python_bin" - <<'PY'
import platform
import sys
print(f"python_executable={sys.executable}")
print(f"python_version={platform.python_version()}")
print(f"platform={platform.platform()}")
PY
        "$python_bin" -m pip --version || true
        printf 'pip_config_debug_begin\n'
        "$python_bin" -m pip config debug 2>&1 | redact_stream || true
        printf 'pip_config_debug_end\n'
        "$python_bin" -m pip check || true
        printf 'pip_freeze_begin\n'
        "$python_bin" -m pip freeze --all 2>/dev/null | LC_ALL=C sort || true
        printf 'pip_freeze_end\n'
    else
        printf 'python_environment=unavailable\n'
    fi
} > "$output"

cat "$output"

# after_script runs in a fresh shell, so reconstruct the deterministic runtime
# path from CI_JOB_ID and remove it only after package evidence has been saved.
if [ -n "${CI_JOB_ID:-}" ] && [ -d "$runtime_dir" ]; then
    rm -rf -- "$runtime_dir"
fi
