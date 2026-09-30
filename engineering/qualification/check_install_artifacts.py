#!/usr/bin/env python3
"""Build and qualify CALM wheel and sdist installations in isolated venvs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import venv
from importlib import metadata
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "engineering" / "qualification" / "check_installed_package.py"
DISTRIBUTION_CHECKER = (
    REPO_ROOT
    / "engineering"
    / "qualification"
    / "check_python_distribution_artifacts.py"
)
MINIMUM_CONSTRAINTS = (
    REPO_ROOT
    / "engineering"
    / "qualification"
    / "constraints"
    / "minimum-py310-py312.txt"
)
CURRENT_TARGETS = ("base", "science", "dataframe", "plot", "viz")
MINIMUM_TARGETS = ("base", "science")


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        raise RuntimeError(
            f"command failed with exit code {completed.returncode}: "
            + " ".join(command)
        )
    return completed


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(*args: str) -> str | None:
    if shutil.which("git") is None:
        return None
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _source_identity() -> dict[str, object]:
    commit = _git_value("rev-parse", "HEAD")
    status = _git_value("status", "--porcelain")
    return {
        "git_commit": commit,
        "git_dirty": None if status is None else bool(status),
    }


def _work_root_policy_error(
    work_root: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> str | None:
    """Return an admission error before any work-root mutation occurs."""

    root = repo_root.resolve()
    candidate = work_root.expanduser().resolve()
    if candidate == root or candidate in root.parents:
        return (
            "--work-root must not be the repository root or one of its "
            "ancestors"
        )

    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return None

    if shutil.which("git") is None:
        return (
            "--work-root is inside the repository, but Git is unavailable "
            "to verify that the path is ignored"
        )
    completed = subprocess.run(
        [
            "git",
            "check-ignore",
            "--quiet",
            "--no-index",
            "--",
            relative.as_posix(),
        ],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode == 0:
        return None
    if completed.returncode == 1:
        return (
            "--work-root inside the repository must be beneath a Git-ignored "
            "generated-output directory; use build/qualification/... or a "
            "path outside the checkout"
        )
    return "unable to verify the repository-local --work-root ignore policy"


def _artifact_requirement(artifact: Path, target: str) -> str:
    uri = artifact.resolve().as_uri()
    if target == "base":
        return f"calm @ {uri}"
    return f"calm[{target}] @ {uri}"


def _install_smoke(
    *,
    artifact: Path,
    target: str,
    environment: Path,
    work_root: Path,
    expected_version: str,
    constraints: Path | None,
    pip_arguments: tuple[str, ...],
) -> dict[str, object]:
    venv.EnvBuilder(with_pip=True, clear=True).create(environment)
    python = _venv_python(environment)
    install = [str(python), "-m", "pip", "install", "--disable-pip-version-check"]
    if constraints is not None:
        install.extend(("--constraint", str(constraints)))
    install.extend(pip_arguments)
    install.append(_artifact_requirement(artifact, target))
    clean_env = {
        **os.environ,
        "PYTHONPATH": "",
        "PYTHONNOUSERSITE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    _run(install, cwd=work_root, env=clean_env)
    _run(
        [str(python), "-m", "pip", "check"],
        cwd=work_root,
        env=clean_env,
    )

    result_path = work_root / "smoke-results" / f"{artifact.name}-{target}.json"
    _run(
        [
            str(python),
            str(SMOKE),
            "--mode",
            target,
            "--expected-version",
            expected_version,
            "--forbidden-source-root",
            str(REPO_ROOT),
            "--output",
            str(result_path),
        ],
        cwd=work_root,
        env=clean_env,
    )
    freeze = _run(
        [str(python), "-m", "pip", "freeze", "--all"],
        cwd=work_root,
        env=clean_env,
    ).stdout.splitlines()
    return {
        "artifact": artifact.name,
        "target": target,
        "environment": environment.name,
        "smoke_result": str(result_path.relative_to(work_root)),
        "smoke": json.loads(result_path.read_text(encoding="utf-8")),
        "installed_distributions": sorted(line for line in freeze if line.strip()),
    }


def _distribution_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _artifact_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    marker = 'version = "'
    line = next(line for line in text.splitlines() if line.startswith(marker))
    return line[len(marker) : -1]


def _write_report(work_root: Path, report: dict[str, object]) -> None:
    report_path = work_root / "install-artifacts.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote artifact qualification report: {report_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-root",
        type=Path,
        required=True,
        help=(
            "scratch directory outside the checkout or beneath a Git-ignored "
            "generated-output directory such as build/qualification"
        ),
    )
    parser.add_argument(
        "--dependency-track",
        choices=("current", "minimum"),
        default="current",
    )
    parser.add_argument(
        "--pip-argument",
        action="append",
        default=[],
        help="additional argument forwarded to isolated pip install commands",
    )
    args = parser.parse_args(argv)
    work_root = args.work_root.expanduser().resolve()
    work_root_error = _work_root_policy_error(work_root)
    if work_root_error is not None:
        parser.error(work_root_error)
    if work_root.exists():
        shutil.rmtree(work_root)
    dist = work_root / "dist"
    dist.mkdir(parents=True)

    report: dict[str, object] = {
        "schema": "calm.install_artifact_qualification.v3",
        "status": "running",
        "dependency_track": args.dependency_track,
        "constraints": (
            str(MINIMUM_CONSTRAINTS)
            if args.dependency_track == "minimum"
            else None
        ),
        "source": _source_identity(),
        "build_environment": {
            "python": sys.version.split()[0],
            "pip": _distribution_version("pip"),
            "setuptools": _distribution_version("setuptools"),
            "wheel": _distribution_version("wheel"),
            "build": _distribution_version("build"),
            "twine": _distribution_version("twine"),
        },
        "artifacts": [],
        "distribution_artifacts": None,
        "installations": [],
    }
    if not (sys.version_info >= (3, 10) and sys.version_info < (3, 13)):
        report.update(
            status="failed",
            error_type="PythonVersionError",
            error=(
                "artifact qualification requires Python 3.10, 3.11, or 3.12"
            ),
        )
        _write_report(work_root, report)
        print(str(report["error"]), file=sys.stderr)
        return 1

    source = report["source"]
    if not source["git_commit"] or source["git_dirty"] is not False:
        report.update(
            status="failed",
            error_type="SourcePolicyError",
            error=(
                "artifact qualification requires a clean source tree at a "
                "resolvable Git commit"
            ),
        )
        _write_report(work_root, report)
        print(str(report["error"]), file=sys.stderr)
        return 1

    missing_prerequisites = [
        name for name in ("build", "twine") if _distribution_version(name) is None
    ]
    if missing_prerequisites:
        report.update(
            status="failed",
            error_type="PrerequisiteError",
            error=(
                "artifact qualification requires installed distributions: "
                + ", ".join(missing_prerequisites)
            ),
        )
        _write_report(work_root, report)
        print(str(report["error"]), file=sys.stderr)
        return 1

    try:
        _run([sys.executable, "-m", "build", "--outdir", str(dist)], cwd=REPO_ROOT)
        artifacts = sorted(path for path in dist.iterdir() if path.is_file())
        wheels = [path for path in artifacts if path.suffix == ".whl"]
        sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
        if len(wheels) != 1 or len(sdists) != 1:
            raise RuntimeError(
                "expected one wheel and one sdist, found "
                f"wheels={wheels}, sdists={sdists}"
            )
        distribution_report = work_root / "python-distribution-artifacts.json"
        _run(
            [
                sys.executable,
                str(DISTRIBUTION_CHECKER),
                "--wheel",
                str(wheels[0]),
                "--sdist",
                str(sdists[0]),
                "--output",
                str(distribution_report),
            ],
            cwd=REPO_ROOT,
        )
        report["distribution_artifacts"] = json.loads(
            distribution_report.read_text(encoding="utf-8")
        )
        _run(
            [sys.executable, "-m", "twine", "check", *map(str, artifacts)],
            cwd=REPO_ROOT,
        )

        report["artifacts"] = [
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in artifacts
        ]
        constraints = (
            MINIMUM_CONSTRAINTS
            if args.dependency_track == "minimum"
            else None
        )
        targets = MINIMUM_TARGETS if constraints is not None else CURRENT_TARGETS
        expected_version = _artifact_version()
        results: list[dict[str, object]] = []
        report["installations"] = results
        for artifact in artifacts:
            artifact_targets = targets
            if artifact in sdists and args.dependency_track == "current":
                artifact_targets = ("base", "science")
            for target in artifact_targets:
                env_name = f"{artifact.name.replace('.', '_')}-{target}-venv"
                results.append(
                    _install_smoke(
                        artifact=artifact,
                        target=target,
                        environment=work_root / env_name,
                        work_root=work_root,
                        expected_version=expected_version,
                        constraints=constraints,
                        pip_arguments=tuple(args.pip_argument),
                    )
                )
        final_source = _source_identity()
        report["source_after"] = final_source
        if (
            final_source.get("git_commit") != source.get("git_commit")
            or final_source.get("git_dirty") is not False
        ):
            raise RuntimeError(
                "source identity changed or became dirty during artifact qualification"
            )
        report["status"] = "passed"
    except Exception as exc:
        report.update(
            status="failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        _write_report(work_root, report)
        raise

    _write_report(work_root, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
