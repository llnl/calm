#!/usr/bin/env bash
# Install one CI dependency domain while preserving resolver diagnostics.

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: $0 REQUIREMENTS_FILE" >&2
    exit 2
fi

repo_root="${CI_PROJECT_DIR:-$PWD}"
cd "$repo_root"
# shellcheck disable=SC1091
source engineering/ci/runtime_paths.sh

requirements_file="$1"
if [ ! -f "$requirements_file" ]; then
    echo "ERROR: requirements file not found: $requirements_file" >&2
    exit 2
fi

python_bin="${CALM_CI_PYTHON:-$(calm_ci_runtime_python)}"
if [ ! -x "$python_bin" ]; then
    echo "ERROR: verified CI Python is unavailable: $python_bin" >&2
    exit 2
fi

mkdir -p build/ci

redact_stream() {
    # Artifacts are not protected by GitLab's console masking. Remove URL
    # userinfo before either logging or retaining pip diagnostics.
    sed -E 's#(https?://)[^/@[:space:]]+@#\1<redacted>@#g'
}

redact_file_in_place() {
    local path="$1"
    [ -f "$path" ] || return 0
    "$python_bin" - "$path" <<'PY_REDACT'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="replace")
text = re.sub(r"(https?://)[^/@\s]+@", r"\1<redacted>@", text)
path.write_text(text, encoding="utf-8")
PY_REDACT
}

job_slug="${CI_JOB_NAME_SLUG:-local}"
node_suffix=""
if [ -n "${CI_NODE_INDEX:-}" ]; then
    node_suffix="-${CI_NODE_INDEX}"
fi
prefix="build/ci/${job_slug}${node_suffix}"
resolver_log="${prefix}-pip-install.log"
resolver_report="${prefix}-pip-report.json"
pip_debug="${prefix}-pip-debug.txt"
pip_check="${prefix}-pip-check.txt"
pip_freeze="${prefix}-pip-freeze.txt"

{
    printf 'requirements_file=%s\n' "$requirements_file"
    printf 'python=%s\n' "$python_bin"
    printf 'ci_job_name=%s\n' "${CI_JOB_NAME:-local}"
    printf 'ci_job_name_slug=%s\n' "$job_slug"
    printf 'ci_node_index=%s\n' "${CI_NODE_INDEX:-<unset>}"
    printf 'ci_node_total=%s\n' "${CI_NODE_TOTAL:-<unset>}"
    printf 'pip_no_cache_dir=%s\n' "${PIP_NO_CACHE_DIR:-<unset>}"
    printf 'pip_config_debug_begin\n'
    "$python_bin" -m pip config debug 2>&1 | redact_stream || true
    printf 'pip_config_debug_end\n'
    printf 'pip_debug_begin\n'
    "$python_bin" -m pip debug --verbose 2>&1 | redact_stream || true
    printf 'pip_debug_end\n'
} > "$pip_debug"
printf 'Saved pip diagnostics to %s\n' "$pip_debug"
sed -n '1,160p' "$pip_debug"

set +e
"$python_bin" -m pip install \
    --no-cache-dir \
    --prefer-binary \
    --report "$resolver_report" \
    -r "$requirements_file" 2>&1 | redact_stream | tee "$resolver_log"
install_status=${PIPESTATUS[0]}
set -e

redact_file_in_place "$resolver_report"

if [ "$install_status" -ne 0 ]; then
    printf 'pip_install_status=%s\n' "$install_status" | tee -a "$resolver_log"
    exit "$install_status"
fi

"$python_bin" -m pip check 2>&1 | tee "$pip_check"
"$python_bin" -m pip freeze --all 2>&1 | LC_ALL=C sort | tee "$pip_freeze"
