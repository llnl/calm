#!/usr/bin/env bash
# Create a fresh, job-local Python 3.11 environment for LC Jacamar jobs.
# This file is sourced from .gitlab-ci.yml so exported variables remain visible.

set -eo pipefail

repo_root="${CI_PROJECT_DIR:-$PWD}"
cd "$repo_root"
# shellcheck disable=SC1091
source engineering/ci/runtime_paths.sh
mkdir -p build/ci
bootstrap_diagnostics="build/ci/bootstrap-python.txt"
: > "$bootstrap_diagnostics"

log() {
    printf '%s\n' "$*" | tee -a "$bootstrap_diagnostics"
}

record_command() {
    "$@" 2>&1 | tee -a "$bootstrap_diagnostics" || true
}

log "Bootstrap host: $(hostname)"
log "Project directory: $repo_root"
log "Home directory: ${HOME:-<unset>}"
record_command quota -v
record_command df -h "${HOME:-$repo_root}" "${CALM_CI_RUNTIME_BASE:-/var/tmp}"

# Jacamar shell jobs do not always initialize the modules function in the same
# way as an interactive login shell. Try the standard LC/Lmod initialization
# paths before considering the documented /usr/tce Python path fallback.
if ! type module >/dev/null 2>&1; then
    for init_script in \
        /etc/profile.d/00-modulepath.sh \
        /etc/profile.d/modules.sh \
        /usr/share/lmod/lmod/init/bash
    do
        if [ -r "$init_script" ]; then
            # shellcheck disable=SC1090
            source "$init_script"
        fi
        if type module >/dev/null 2>&1; then
            break
        fi
    done
fi

is_python_311() {
    "$1" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)
PY
}

selected_module=""
system_python=""

if type module >/dev/null 2>&1; then
    log "Available LC Python modules:"
    record_command module -t avail python

    # LC currently publishes the Python 3.11 module as python/3.11.5. The
    # generic python/3 module points at the site default (currently 3.13), so it
    # must not be used as a fallback for CALM's Python 3.11 qualification job.
    requested_module="${CALM_CI_PYTHON_MODULE:-python/3.11.5}"
    candidates=("$requested_module" python/3.11.5 python/3.11)
    attempted_modules=""

    for candidate in "${candidates[@]}"; do
        case " $attempted_modules " in
            *" $candidate "*) continue ;;
        esac
        attempted_modules="$attempted_modules $candidate"
        log "Trying LC module: $candidate"

        # Remove any previously loaded Python-family module before selecting the
        # requested version. Lmod may auto-swap, but an explicit unload makes
        # the resulting interpreter deterministic in non-interactive jobs.
        module unload python >/dev/null 2>&1 || true
        hash -r

        if module load "$candidate" >/dev/null 2>&1; then
            hash -r
            candidate_python="$(command -v python3 || true)"
            if [ -n "$candidate_python" ] && is_python_311 "$candidate_python"; then
                selected_module="$candidate"
                system_python="$candidate_python"
                break
            fi
            log "Rejected $candidate because it did not provide Python 3.11"
            if [ -n "$candidate_python" ]; then
                record_command "$candidate_python" --version
            fi
        else
            log "Module load failed: $candidate"
        fi
    done
else
    log "The environment-modules command is unavailable; trying LC Python paths"
fi

# The LC Python documentation identifies /usr/tce/packages/python as the stable
# convenience path. This fallback also permits an explicit project/group CI
# variable when module initialization differs on a runner.
if [ -z "$system_python" ]; then
    requested_python="${CALM_CI_SYSTEM_PYTHON:-}"
    python_paths=(
        "$requested_python"
        /usr/tce/packages/python/python-3.11.5/bin/python3
    )
    attempted_paths=""

    for candidate_python in "${python_paths[@]}"; do
        [ -n "$candidate_python" ] || continue
        case " $attempted_paths " in
            *" $candidate_python "*) continue ;;
        esac
        attempted_paths="$attempted_paths $candidate_python"
        log "Trying LC Python executable: $candidate_python"
        if [ -x "$candidate_python" ] && is_python_311 "$candidate_python"; then
            system_python="$candidate_python"
            break
        fi
    done
fi

if [ -z "$system_python" ]; then
    log "ERROR: no LC Python 3.11 interpreter was found"
    log "Set CALM_CI_PYTHON_MODULE or CALM_CI_SYSTEM_PYTHON if this runner uses a nonstandard installation."
    record_command command -v python3
    record_command python3 --version
    exit 2
fi

# Jacamar stores project workspaces under ~/.jacamar-ci on LC. A scientific
# Python environment per concurrent job can exhaust the relatively small home
# quota before Jacamar can generate its own cleanup script. Remove any legacy
# checkout-local environment, then create this job's environment on ephemeral
# storage instead.
rm -rf -- "$repo_root/.venv"
runtime_dir="$(calm_ci_runtime_dir)"
rm -rf -- "$runtime_dir"
umask 077
mkdir -p "$runtime_dir/tmp" "$runtime_dir/cache" "$runtime_dir/matplotlib"
"$system_python" -m venv "$runtime_dir/venv"

export CALM_CI_RUNTIME_DIR="$runtime_dir"
export CALM_CI_PYTHON="$runtime_dir/venv/bin/python"
export TMPDIR="$runtime_dir/tmp"
export XDG_CACHE_HOME="$runtime_dir/cache"
export MPLCONFIGDIR="$runtime_dir/matplotlib"
export PYTHONNOUSERSITE=1
export PYTHONPATH=""
unset PYTHONHOME || true
hash -r

"$CALM_CI_PYTHON" - <<'PY' | tee -a "$bootstrap_diagnostics"
import pathlib
import platform
import sys

expected = (3, 11)
observed = sys.version_info[:2]
if observed != expected:
    raise SystemExit(
        f"CI requires Python {expected[0]}.{expected[1]}, observed "
        f"{observed[0]}.{observed[1]} at {sys.executable}"
    )

print(f"Python executable: {pathlib.Path(sys.executable).resolve()}")
print(f"Python version: {platform.python_version()}")
print(f"Platform: {platform.platform()}")
PY
"$CALM_CI_PYTHON" -m pip --version 2>&1 | tee -a "$bootstrap_diagnostics"
log "Loaded module: ${selected_module:-<direct executable>}"
log "System Python: $system_python"
log "Runtime directory: $runtime_dir"
log "Temporary directory: $TMPDIR"
log "Pip cache: ${PIP_CACHE_DIR:-<unset>}"
