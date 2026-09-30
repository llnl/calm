"""Repository contracts for the LC Jacamar Python bootstrap."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GITLAB_CI = ROOT / ".gitlab-ci.yml"
BOOTSTRAP = ROOT / "engineering" / "ci" / "bootstrap_python.sh"
INSTALL = ROOT / "engineering" / "ci" / "install_requirements.sh"
CAPTURE = ROOT / "engineering" / "ci" / "capture_environment.sh"
RUNTIME_PATHS = ROOT / "engineering" / "ci" / "runtime_paths.sh"


def _job_body(text: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}:\n(?P<body>.*?)(?=^[^ #\n][^\n]*:\n|\Z)",
        text,
    )
    assert match is not None, name
    return match.group("body")


def test_gitlab_ci_does_not_depend_on_mutable_runner_caches() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")
    global_preamble = text.split("# -----------------", maxsplit=1)[0]

    assert "PIP_NO_CACHE_DIR" in global_preamble
    assert "PIP_CACHE_DIR" not in global_preamble
    assert "\ncache:" not in global_preamble
    assert ".venv/" not in global_preamble
    assert "CI_JOB_NAME}" not in global_preamble


def test_preflight_gates_the_test_fanout() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")
    body = _job_body(text, "ci:py311-preflight")

    assert "stage: preflight" in body
    assert "source engineering/ci/bootstrap_python.sh" in body
    assert "requirements-preflight-py311.txt" in body
    assert "engineering/ci/install_requirements.sh" in body
    assert "build/ci/" in body
    assert text.index("- preflight") < text.index("- test")


def test_every_python_job_uses_the_fresh_environment_bootstrap() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")
    jobs = (
        "ci:py311-preflight",
        "ruff:typing-modernization",
        "pytest:py311",
        "coverage:py311",
        "qualification:linux-py311-contract",
        "docs:mkdocs",
        "build:dist",
        "pages",
        "dist:release",
    )

    for job in jobs:
        body = _job_body(text, job)
        assert "source engineering/ci/bootstrap_python.sh" in body
        assert "engineering/ci/capture_environment.sh" in body
        assert "build/ci/" in body

    assert "source .venv/bin/activate" not in text
    assert "module load python/3" not in text


def test_typing_modernization_inputs_are_checked_before_ruff() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")
    body = _job_body(text, "ruff:typing-modernization")

    checker = (
        "$CALM_CI_PYTHON "
        "engineering/qualification/check_typing_modernization_contract.py"
    )
    ruff = (
        "$CALM_CI_PYTHON -m ruff check --config "
        "engineering/qualification/ruff-typing-modernization.toml "
        "@engineering/qualification/typing-modernization-files.txt"
    )
    assert checker in body
    assert ruff in body
    assert body.index(checker) < body.index(ruff)


def test_python_tools_run_through_the_verified_interpreter() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")

    assert (
        "$CALM_CI_PYTHON "
        "engineering/qualification/check_typing_modernization_contract.py"
        in text
    )
    assert "$CALM_CI_PYTHON engineering/ci/run_pytest_shard.py" in text
    assert "$CALM_CI_PYTHON -m ruff" in text
    assert "$CALM_CI_PYTHON -m mkdocs" in text
    assert "$CALM_CI_PYTHON -m build" in text
    assert (
        "$CALM_CI_PYTHON engineering/qualification/"
        "check_python_distribution_artifacts.py"
        in text
    )
    assert "$CALM_CI_PYTHON -m twine" in text


def test_bootstrap_requires_python_311_and_uses_ephemeral_runtime() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")

    assert 'rm -rf -- "$repo_root/.venv"' in text
    assert '"$system_python" -m venv "$runtime_dir/venv"' in text
    assert 'export CALM_CI_PYTHON="$runtime_dir/venv/bin/python"' in text
    assert 'export TMPDIR="$runtime_dir/tmp"' in text
    assert 'export XDG_CACHE_HOME="$runtime_dir/cache"' in text
    assert 'export MPLCONFIGDIR="$runtime_dir/matplotlib"' in text
    assert "quota -v" in text
    assert "sys.version_info[:2] == (3, 11)" in text
    assert "python/3.11.5" in text
    assert "CALM_CI_PYTHON_MODULE" in text
    assert "CALM_CI_SYSTEM_PYTHON" in text
    assert "python_paths=(" in text
    assert "/usr/tce/packages/python/python-3.11.5/bin/python3" in text
    assert "module unload python" in text
    assert "python/3 module" in text
    assert "bootstrap-python.txt" in text
    assert "hash -r" in text
    assert 'export PYTHONPATH=""' in text
    assert "unset PYTHONHOME" in text
    assert BOOTSTRAP.stat().st_mode & 0o111


def test_runtime_path_is_job_local_and_outside_the_checkout() -> None:
    text = RUNTIME_PATHS.read_text(encoding="utf-8")
    ci = GITLAB_CI.read_text(encoding="utf-8")

    assert "CALM_CI_RUNTIME_BASE" in text
    assert "CI_JOB_ID" in text
    assert "calm-ci-%s/%s" in text
    assert 'CALM_CI_RUNTIME_BASE: "/var/tmp"' in ci
    assert RUNTIME_PATHS.stat().st_mode & 0o111


def test_dependency_installs_preserve_resolver_evidence() -> None:
    text = INSTALL.read_text(encoding="utf-8")

    assert "--no-cache-dir" in text
    assert "--report" in text
    assert "pip config debug" in text
    assert "pip debug --verbose" in text
    assert "pip check" in text
    assert "pip freeze --all" in text
    assert "PIPESTATUS[0]" in text
    assert "CI_JOB_NAME_SLUG" in text
    assert "CI_NODE_INDEX" in text
    assert "redact_stream" in text
    assert "redact_file_in_place" in text
    assert "sed -n '1,160p'" in text
    assert INSTALL.stat().st_mode & 0o111


def test_failure_diagnostics_capture_resolved_packages_and_pip_config() -> None:
    text = CAPTURE.read_text(encoding="utf-8")

    assert "pip config debug" in text
    assert "pip check" in text
    assert "pip freeze --all" in text
    assert "git status --short" in text
    assert "module -t list" in text
    assert "PIP_NO_CACHE_DIR" in text
    assert "redact_stream" in text
    assert "redact_value" in text
    assert "CI_NODE_INDEX" in text
    assert "runtime_usage_begin" in text
    assert 'rm -rf -- "$runtime_dir"' in text
    assert CAPTURE.stat().st_mode & 0o111


def test_ci_jobs_install_only_their_dependency_domain() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")

    assert ".[dev]" not in text
    expected = {
        "ci:py311-preflight": "requirements-preflight-py311.txt",
        "ruff:typing-modernization": "requirements-ruff.txt",
        "pytest:py311": "requirements-test-py311.txt",
        "coverage:py311": "requirements-coverage-py311.txt",
        "qualification:linux-py311-contract": "requirements-test-py311.txt",
        "docs:mkdocs": "requirements-docs-py311.txt",
        "pages": "requirements-docs-py311.txt",
        "build:dist": "requirements-build-py311.txt",
        "dist:release": "requirements-build-py311.txt",
    }
    for job, requirements in expected.items():
        body = _job_body(text, job)
        assert "engineering/ci/install_requirements.sh" in body
        assert requirements in body

    assert "$CALM_CI_PYTHON -m pip install" not in text


def test_test_requirements_exclude_unrelated_interactive_and_docs_tools() -> None:
    text = (
        ROOT / "engineering" / "ci" / "requirements-test-py311.txt"
    ).read_text(encoding="utf-8")
    requirements = [
        line.strip().lower()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert "-e .[science,dataframe,plot]" in requirements
    assert any(line.startswith("pytest>=") for line in requirements)
    assert "ruff==0.15.22" in requirements
    for excluded in ("jupyter", "notebook", "mkdocs", "twine", "build>="):
        assert not any(excluded in line for line in requirements)


def test_pytest_is_sharded_and_coverage_is_combined() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")
    pytest_job = _job_body(text, "pytest:py311")
    coverage_job = _job_body(text, "coverage:py311")

    assert "parallel: 3" in pytest_job
    assert "CI_NODE_INDEX" in pytest_job
    assert "CI_NODE_TOTAL" in pytest_job
    assert "run_pytest_shard.py" in pytest_job
    assert '-m "not real_backend"' in pytest_job
    assert "--cov-report=" in pytest_job
    assert ".coverage.*" in pytest_job

    assert "needs:" in coverage_job
    assert "job: pytest:py311" in coverage_job
    assert "$CALM_CI_PYTHON -m coverage combine" in coverage_job
    assert "coverage.xml" in coverage_job
