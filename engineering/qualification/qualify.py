#!/usr/bin/env python3
"""Execute CALM core or provider qualification profiles and emit evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_MATRIX = HERE / "qualification-matrix.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "build" / "qualification"
KNOWN_PLACEHOLDERS = {"python", "repo", "report_dir"}
SUPPORTED_MATRIX_SCHEMAS = {
    "calm.qualification_matrix.v2": "core",
    "calm.qualification_matrix.v3": "core",
    "calm.provider_qualification_matrix.v1": "provider",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _platform_name() -> str:
    value = platform.system().lower()
    return {"darwin": "macos", "windows": "windows"}.get(value, value)


def _architecture() -> str:
    value = platform.machine().lower()
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "aarch64": "arm64",
    }.get(value, value)


def _python_minor() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _distribution_snapshot(names: list[str]) -> dict[str, str | None]:
    snapshot: dict[str, str | None] = {}
    for name in names:
        try:
            snapshot[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            snapshot[name] = None
    return snapshot


def environment_snapshot(
    *, distributions: list[str] | None = None
) -> dict[str, Any]:
    git_status = _git_value("status", "--porcelain")
    return {
        "platform": _platform_name(),
        "platform_release": platform.release(),
        "architecture": _architecture(),
        "python": _python_minor(),
        "python_full": platform.python_version(),
        "python_executable": sys.executable,
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_branch": _git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": None if git_status is None else bool(git_status),
        "installed_distributions": _distribution_snapshot(distributions or []),
    }


def _source_policy_violations(
    matrix: dict[str, Any], environment: dict[str, Any]
) -> list[str]:
    policy = matrix.get("source_policy", {})
    violations: list[str] = []
    if policy.get("require_git_commit") and not environment.get("git_commit"):
        violations.append("source tree has no resolvable Git commit")
    if policy.get("require_clean_git"):
        dirty = environment.get("git_dirty")
        if dirty is None:
            violations.append("source tree Git status is unavailable")
        elif dirty:
            violations.append("source tree contains uncommitted changes")
    return violations


def _source_stability_violations(
    initial: dict[str, Any], final: dict[str, Any]
) -> list[str]:
    violations: list[str] = []
    if initial.get("git_commit") != final.get("git_commit"):
        violations.append("source Git commit changed during qualification")
    return violations


def load_matrix(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_matrix(payload)
    return payload


def validate_matrix(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_MATRIX_SCHEMAS:
        raise ValueError("unsupported qualification matrix schema")
    report_schema = payload.get("report_schema_version")
    if not isinstance(report_schema, str) or not report_schema:
        raise ValueError("qualification matrix must define report_schema_version")
    source_policy = payload.get("source_policy")
    if schema_version == "calm.qualification_matrix.v3" and not isinstance(
        source_policy, dict
    ):
        raise ValueError("v3 qualification matrix must define source_policy")
    if source_policy is not None:
        if not isinstance(source_policy, dict):
            raise ValueError("source_policy must be a mapping")
        for field in ("require_git_commit", "require_clean_git"):
            if not isinstance(source_policy.get(field), bool):
                raise ValueError(
                    f"source_policy must define Boolean {field!r}"
                )

    evidence = payload.get("evidence_distributions")
    if schema_version == "calm.qualification_matrix.v3" and evidence is None:
        raise ValueError(
            "v3 qualification matrix must define evidence_distributions"
        )
    if evidence is not None and (
        not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, str) and item for item in evidence)
    ):
        raise ValueError("evidence_distributions must be a non-empty string list")
    if schema_version == "calm.provider_qualification_matrix.v1":
        contract = payload.get("provider_contract")
        if not isinstance(contract, dict):
            raise ValueError(
                "provider qualification matrix must define provider_contract"
            )
        for field in ("family", "model", "device"):
            if not isinstance(contract.get(field), str) or not contract[field]:
                raise ValueError(
                    f"provider_contract must define a non-empty {field!r}"
                )
        required_evidence = contract.get("required_evidence")
        if not isinstance(required_evidence, list) or not required_evidence:
            raise ValueError(
                "provider_contract must define non-empty required_evidence"
            )
    profiles = payload.get("profiles")
    cells = payload.get("cells")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("qualification matrix must define profiles")
    if not isinstance(cells, list) or not cells:
        raise ValueError("qualification matrix must define cells")

    check_ids: set[str] = set()
    for profile_name, profile in profiles.items():
        checks = profile.get("checks") if isinstance(profile, dict) else None
        if not isinstance(checks, list) or not checks:
            raise ValueError(f"profile {profile_name!r} must define checks")
        for check in checks:
            check_id = check.get("id")
            command = check.get("command")
            if not isinstance(check_id, str) or not check_id:
                raise ValueError(
                    f"profile {profile_name!r} contains an invalid check id"
                )
            if check_id in check_ids:
                raise ValueError(f"duplicate qualification check id: {check_id}")
            check_ids.add(check_id)
            if not isinstance(command, list) or not command or not all(
                isinstance(part, str) and part for part in command
            ):
                raise ValueError(f"check {check_id!r} must define a command list")
            for field in (
                "requires_commands",
                "requires_modules",
                "requires_distributions",
            ):
                values = check.get(field, ())
                if not isinstance(values, (list, tuple)) or not all(
                    isinstance(item, str) and item for item in values
                ):
                    raise ValueError(
                        f"check {check_id!r} has an invalid {field!r} list"
                    )
            for part in command:
                for placeholder in _placeholders(part):
                    if placeholder not in KNOWN_PLACEHOLDERS:
                        raise ValueError(
                            "check "
                            f"{check_id!r} uses unknown placeholder {placeholder!r}"
                        )

    cell_ids: set[str] = set()
    primary_cells = 0
    for cell in cells:
        cell_id = cell.get("id")
        if not isinstance(cell_id, str) or not cell_id or cell_id in cell_ids:
            raise ValueError(f"invalid or duplicate qualification cell id: {cell_id!r}")
        cell_ids.add(cell_id)
        tier = cell.get("tier")
        if tier not in {"primary", "secondary"}:
            raise ValueError(
                f"qualification cell {cell_id!r} must declare primary or secondary tier"
            )
        if tier == "primary":
            primary_cells += 1
        unknown = set(cell.get("profiles", ())) - set(profiles)
        if unknown:
            raise ValueError(
                f"cell {cell_id!r} uses unknown profiles: {sorted(unknown)}"
            )
    if primary_cells == 0:
        raise ValueError("qualification matrix must define at least one primary cell")


def _qualification_kind(matrix: dict[str, Any]) -> str:
    return SUPPORTED_MATRIX_SCHEMAS[str(matrix["schema_version"])]


def _qualification_flag(matrix: dict[str, Any]) -> str:
    return (
        "provider_qualified"
        if _qualification_kind(matrix) == "provider"
        else "cell_qualified"
    )


def _placeholders(value: str) -> set[str]:
    found: set[str] = set()
    for name in KNOWN_PLACEHOLDERS:
        if "{" + name + "}" in value:
            found.add(name)
    remainder = value
    for name in found:
        remainder = remainder.replace("{" + name + "}", "")
    if "{" in remainder or "}" in remainder:
        found.add("<unknown>")
    return found


def _select_profiles(
    matrix: dict[str, Any],
    *,
    cell_id: str | None,
    requested: list[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    cell = None
    if cell_id is not None:
        cell = next((item for item in matrix["cells"] if item["id"] == cell_id), None)
        if cell is None:
            raise ValueError(f"unknown qualification cell: {cell_id}")
    profiles = requested or (list(cell["profiles"]) if cell is not None else [])
    if not profiles:
        raise ValueError("select at least one --profile or provide --cell")
    unknown = set(profiles) - set(matrix["profiles"])
    if unknown:
        raise ValueError(f"unknown qualification profiles: {sorted(unknown)}")
    return cell, list(dict.fromkeys(profiles))


def _current_cell(
    matrix: dict[str, Any], environment: dict[str, Any]
) -> dict[str, Any]:
    matches = [
        cell
        for cell in matrix["cells"]
        if not _cell_mismatches(cell, environment)
    ]
    if not matches:
        raise ValueError(
            "no qualification cell matches the current environment "
            f"({environment['platform']}, {environment['architecture']}, "
            f"Python {environment['python']})"
        )
    if len(matches) > 1:
        identifiers = ", ".join(sorted(str(cell["id"]) for cell in matches))
        raise ValueError(
            "multiple qualification cells match the current environment: "
            f"{identifiers}"
        )
    return matches[0]


def _cell_mismatches(cell: dict[str, Any], environment: dict[str, Any]) -> list[str]:
    mismatches = []
    for key in ("platform", "architecture", "python"):
        expected = str(cell[key])
        actual = str(environment[key])
        if expected != actual:
            mismatches.append(f"{key}: expected {expected}, observed {actual}")
    return mismatches


def _missing_prerequisites(check: dict[str, Any]) -> list[str]:
    missing = []
    for command in check.get("requires_commands", ()):
        if shutil.which(command) is None:
            missing.append(f"command:{command}")
    for module in check.get("requires_modules", ()):
        if importlib.util.find_spec(module) is None:
            missing.append(f"module:{module}")
    for distribution in check.get("requires_distributions", ()):
        try:
            metadata.version(distribution)
        except metadata.PackageNotFoundError:
            missing.append(f"distribution:{distribution}")
    return missing


def _expand_command(command: list[str], report_dir: Path) -> list[str]:
    values = {
        "python": sys.executable,
        "repo": str(REPO_ROOT),
        "report_dir": str(report_dir),
    }
    return [part.format(**values) for part in command]


def _safe_log_name(check_id: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in check_id
    )


def _run_check(
    check: dict[str, Any],
    *,
    profile: str,
    report_dir: Path,
    dry_run: bool,
) -> dict[str, Any]:
    check_id = str(check["id"])
    command = _expand_command(list(check["command"]), report_dir)
    result: dict[str, Any] = {
        "id": check_id,
        "profile": profile,
        "required": bool(check.get("required", True)),
        "command": command,
        "started_at": _utc_now(),
    }
    missing = _missing_prerequisites(check)
    if dry_run:
        result.update(
            status="planned",
            missing_prerequisites=missing,
            finished_at=_utc_now(),
            duration_seconds=0.0,
        )
        return result
    if missing:
        result.update(
            status="blocked" if result["required"] else "skipped",
            missing_prerequisites=missing,
            finished_at=_utc_now(),
            duration_seconds=0.0,
        )
        return result

    logs = report_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    name = _safe_log_name(check_id)
    stdout_path = logs / f"{name}.stdout.log"
    stderr_path = logs / f"{name}.stderr.log"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env={
                **os.environ,
                **{str(k): str(v) for k, v in check.get("env", {}).items()},
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(check.get("timeout_seconds", 1800)),
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode: int | None = completed.returncode
        failure_type = None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        stderr += f"\nqualification check timed out: {check_id}\n"
        returncode = None
        failure_type = "timeout"
    except OSError as exc:
        stdout = ""
        stderr = f"qualification check could not start: {exc}\n"
        returncode = None
        failure_type = "execution_error"

    duration = time.monotonic() - started
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    passed = returncode == 0 and failure_type is None
    result.update(
        status="passed" if passed else "failed",
        returncode=returncode,
        failure_type=failure_type,
        finished_at=_utc_now(),
        duration_seconds=round(duration, 6),
        stdout_log=str(stdout_path.relative_to(report_dir)),
        stderr_log=str(stderr_path.relative_to(report_dir)),
        stdout_sha256=_sha256_bytes(stdout.encode("utf-8")),
        stderr_sha256=_sha256_bytes(stderr.encode("utf-8")),
        stdout_size_bytes=len(stdout.encode("utf-8")),
        stderr_size_bytes=len(stderr.encode("utf-8")),
    )
    return result


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _default_output(cell: dict[str, Any] | None) -> Path:
    name = str(cell["id"]) if cell is not None else "qualification-report"
    return DEFAULT_OUTPUT_DIR / f"{name}.json"


def _named_output_cell(
    output: Path,
    cells: list[dict[str, Any]],
) -> str | None:
    """Return the matrix cell named by an output stem, when recognizable."""

    stem = output.stem
    for cell in cells:
        cell_id = str(cell["id"])
        aliases = {cell_id}
        if cell_id.endswith("-core"):
            aliases.add(cell_id.removesuffix("-core"))
        if any(alias in stem for alias in aliases):
            return cell_id
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--cell")
    selection.add_argument(
        "--current-cell",
        action="store_true",
        help="select the matrix cell matching this OS, architecture, and Python",
    )
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "report path; defaults to build/qualification/<selected-cell>.json "
            "when a cell is selected"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_matrix")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    matrix_path = args.matrix.resolve()
    matrix = load_matrix(matrix_path)
    environment = environment_snapshot(
        distributions=list(matrix.get("evidence_distributions", ()))
    )
    if args.list_matrix:
        print(
            "Current environment: "
            f"{environment['platform']}-{environment['architecture']} "
            f"Python {environment['python']}"
        )
        print("Profiles:")
        for name, profile in matrix["profiles"].items():
            print(f"  {name}: {profile['description']}")
        print("Cells:")
        for cell in matrix["cells"]:
            marker = "required" if cell.get("required", False) else "optional"
            tier = str(cell.get("tier", "secondary"))
            current = " current" if not _cell_mismatches(cell, environment) else ""
            print(
                f"  {cell['id']} ({tier}, {marker}{current}): "
                f"{', '.join(cell['profiles'])}"
            )
        return 0

    try:
        selected_cell = args.cell
        if args.current_cell:
            selected_cell = str(_current_cell(matrix, environment)["id"])
        cell, profiles = _select_profiles(
            matrix,
            cell_id=selected_cell,
            requested=args.profile,
        )
    except ValueError as exc:
        print(f"qualification selection error: {exc}", file=sys.stderr)
        return 2

    output = (args.output or _default_output(cell)).resolve()
    if cell is not None and args.output is not None:
        named_cell = _named_output_cell(output, list(matrix["cells"]))
        selected_cell = str(cell["id"])
        if named_cell is not None and named_cell != selected_cell:
            print(
                "qualification output name identifies a different cell: "
                f"{named_cell}; selected cell is {selected_cell}. "
                "Omit --output to use the interpreter-derived filename.",
                file=sys.stderr,
            )
            return 2
    report_dir = output.parent / f"{output.stem}.d"
    complete_cell = bool(
        cell is not None and set(profiles) == set(cell.get("profiles", ()))
    )
    qualification_kind = _qualification_kind(matrix)
    qualification_flag = _qualification_flag(matrix)
    report: dict[str, Any] = {
        "schema_version": matrix["report_schema_version"],
        "qualification_kind": qualification_kind,
        "matrix_schema_version": matrix["schema_version"],
        "matrix_path": str(matrix_path),
        "matrix_sha256": _sha256_path(matrix_path),
        "source_policy": matrix.get("source_policy", {}),
        "source_policy_violations": _source_policy_violations(matrix, environment),
        "started_at": _utc_now(),
        "environment": environment,
        "selection": {
            "cell": cell["id"] if cell is not None else None,
            "cell_tier": cell.get("tier") if cell is not None else None,
            "selected_from_current_environment": bool(args.current_cell),
            "profiles": profiles,
            "cell_profiles": list(cell.get("profiles", ())) if cell is not None else [],
            "complete_cell": complete_cell,
            "dry_run": bool(args.dry_run),
        },
        "checks": [],
    }
    if qualification_kind == "provider":
        report["provider_contract"] = matrix["provider_contract"]

    if cell is not None:
        mismatches = _cell_mismatches(cell, environment)
        if mismatches:
            report.update(
                status="failed",
                cell_mismatches=mismatches,
                finished_at=_utc_now(),
            )
            report[qualification_flag] = False
            _write_report(output, report)
            for mismatch in mismatches:
                print(f"cell mismatch: {mismatch}", file=sys.stderr)
            print(f"Wrote qualification report: {output}")
            return 2

    source_violations = list(report["source_policy_violations"])
    if complete_cell and source_violations and not args.dry_run:
        report.update(
            status="failed",
            finished_at=_utc_now(),
        )
        report[qualification_flag] = False
        _write_report(output, report)
        for violation in source_violations:
            print(f"source policy violation: {violation}", file=sys.stderr)
        print(f"Wrote qualification report: {output}")
        return 2

    required_failed = False
    for profile_name in profiles:
        for check in matrix["profiles"][profile_name]["checks"]:
            result = _run_check(
                check,
                profile=profile_name,
                report_dir=report_dir,
                dry_run=bool(args.dry_run),
            )
            report["checks"].append(result)
            print(f"[{result['status'].upper()}] {profile_name}/{result['id']}")
            if result["required"] and result["status"] in {"failed", "blocked"}:
                required_failed = True
                if args.fail_fast:
                    break
        if required_failed and args.fail_fast:
            break

    final_environment = environment_snapshot(
        distributions=list(matrix.get("evidence_distributions", ()))
    )
    final_source_violations = _source_policy_violations(matrix, final_environment)
    final_source_violations.extend(
        _source_stability_violations(environment, final_environment)
    )
    report["source_after"] = {
        key: final_environment[key]
        for key in ("git_commit", "git_branch", "git_dirty")
    }
    report["source_policy_violations_after"] = final_source_violations
    if complete_cell and final_source_violations and not args.dry_run:
        required_failed = True

    if args.dry_run:
        status = "planned"
    else:
        status = "failed" if required_failed else "passed"
    report.update(
        status=status,
        finished_at=_utc_now(),
    )
    report[qualification_flag] = bool(
        complete_cell and status == "passed" and not args.dry_run
    )
    _write_report(output, report)
    print(f"Wrote qualification report: {output}")
    return 1 if required_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
