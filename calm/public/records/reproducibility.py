"""Typed project reproducibility manifests for the public Project workflow."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from calm._version import __version__
from calm.project.reproducibility import (
    DEFAULT_MANIFEST_FILENAME as DEFAULT_MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    collect_backend_identities,
    collect_seed_policy,
    environment_snapshot,
    followup_sources,
    hardware_snapshot,
    jsonable,
    redact_sensitive,
    sha256_value,
    run_inventory,
    snapshot_id,
    source_control_snapshot,
    utc_now,
    write_json_atomic,
)

from calm.public.errors import ProjectReproducibilityError


@dataclass(frozen=True)
class ReproducibilityIssue:
    """One manifest verification error or warning."""

    severity: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class ReproducibilityVerificationReport:
    """Typed comparison between a recorded manifest and current project state."""

    manifest_path: Path
    recorded_snapshot_id: str
    current_snapshot_id: str
    issues: tuple[ReproducibilityIssue, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def warnings(self) -> tuple[ReproducibilityIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def errors(self) -> tuple[ReproducibilityIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    def raise_for_errors(self) -> None:
        if self.errors:
            rendered = "; ".join(issue.message for issue in self.errors)
            raise ProjectReproducibilityError(rendered)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_path": str(self.manifest_path),
            "recorded_snapshot_id": self.recorded_snapshot_id,
            "current_snapshot_id": self.current_snapshot_id,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def summary(self) -> str:
        lines = [
            "CALM reproducibility verification",
            f"  manifest: {self.manifest_path}",
            f"  recorded snapshot: {self.recorded_snapshot_id}",
            f"  current snapshot: {self.current_snapshot_id}",
            f"  errors: {len(self.errors)}",
            f"  warnings: {len(self.warnings)}",
            f"  status: {'verified' if self.ok else 'mismatch'}",
        ]
        for issue in self.issues:
            lines.append(f"  [{issue.severity}] {issue.code}: {issue.message}")
        return "\n".join(lines)


@dataclass(frozen=True)
class ProjectReproducibilityManifest:
    """Immutable, JSON-serializable snapshot of one CALM project and runtime."""

    payload: Mapping[str, Any]

    @property
    def schema_version(self) -> str:
        return str(self.payload.get("schema_version") or "")

    @property
    def snapshot_id(self) -> str:
        return str(self.payload.get("snapshot_id") or "")

    @property
    def generated_at_utc(self) -> str:
        return str(self.payload.get("generated_at_utc") or "")

    @property
    def files(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.payload.get("files") or ())

    @property
    def backends(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.payload.get("backends") or ())

    @property
    def seeds(self) -> Mapping[str, Any]:
        return dict(self.payload.get("seeds") or {})

    def to_dict(self) -> dict[str, Any]:
        return dict(jsonable(self.payload))

    def write(self, path: str | Path, *, overwrite: bool = False) -> Path:
        destination = Path(path)
        write_json_atomic(destination, self.to_dict(), overwrite=overwrite)
        return destination.expanduser().resolve()

    def summary(self) -> str:
        project = dict(self.payload.get("project") or {})
        environment = dict(self.payload.get("environment") or {})
        packages = dict(environment.get("packages") or {})
        runs = list(self.payload.get("runs") or ())
        seeds = dict(self.payload.get("seeds") or {})
        counts = dict(seeds.get("counts") or {})
        return "\n".join(
            [
                "CALM project reproducibility manifest",
                f"  schema: {self.schema_version}",
                f"  snapshot: {self.snapshot_id}",
                f"  generated: {self.generated_at_utc}",
                f"  project: {project.get('path')}",
                f"  project schema: {project.get('database_schema_version')}",
                f"  files: {len(self.files)}",
                f"  runs: {len(runs)}",
                f"  backends: {len(self.backends)}",
                f"  seed observations: {sum(int(value) for value in counts.values())}",
                f"  packages: {len(packages)}",
            ]
        )

    @classmethod
    def read(cls, path: str | Path) -> "ProjectReproducibilityManifest":
        source = Path(path).expanduser().resolve()
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ProjectReproducibilityError(
                f"Cannot read reproducibility manifest {source}: {exc}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise ProjectReproducibilityError(
                f"Reproducibility manifest {source} must contain a JSON object."
            )
        schema = str(payload.get("schema_version") or "")
        if schema != MANIFEST_SCHEMA_VERSION:
            raise ProjectReproducibilityError(
                f"Unsupported reproducibility manifest schema {schema!r}; "
                f"expected {MANIFEST_SCHEMA_VERSION!r}."
            )
        expected = snapshot_id(payload)
        recorded = str(payload.get("snapshot_id") or "")
        if recorded != expected:
            raise ProjectReproducibilityError(
                f"Reproducibility manifest {source} has an invalid snapshot_id."
            )
        return cls(payload=dict(payload))


def _records(collection: Any) -> list[Any]:
    if collection is None:
        return []
    records = getattr(collection, "records", None)
    if callable(records):
        return list(records())
    return list(collection)


def _project_configuration(project: Any) -> dict[str, Any]:
    """Return the authoritative database-backed project configuration."""

    from calm.public.inputs.project_config import load_configuration

    return load_configuration(project)


def _build_reproducibility_manifest(
    project: Any,
    *,
    exclude_paths: tuple[Path, ...] = (),
) -> ProjectReproducibilityManifest:
    path = getattr(project, "path", None)
    if path is None:
        raise ProjectReproducibilityError(
            "Reproducibility manifests require a directory-backed Project."
        )
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise ProjectReproducibilityError(f"Project path does not exist: {root}")

    try:
        runs = _records(project.runs(limit=1_000_000))
        followups = _records(project.followups(limit=1_000_000))
    except Exception as exc:
        raise ProjectReproducibilityError(
            f"Cannot collect authoritative project run provenance: {exc}"
        ) from exc

    run_rows, provenance_sources = run_inventory(runs)
    provenance_sources.extend(followup_sources(followups))
    configuration = _project_configuration(project)
    provenance_sources.append(("project.configuration", configuration))

    by_type = Counter(row["run_type"] for row in run_rows)
    by_status = Counter(row["status"] for row in run_rows)
    import calm as calm_package
    from calm.project.bootstrap import reproducibility_file_inventory
    from calm.project.domain.schema import CURRENT_SCHEMA_VERSION

    source_path = Path(calm_package.__file__).resolve().parent
    payload: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "snapshot_id": "",
        "generated_at_utc": utc_now(),
        "project": {
            "path": str(root),
            "database_schema_version": CURRENT_SCHEMA_VERSION,
            "current_schema_version": CURRENT_SCHEMA_VERSION,
        },
        "software": {
            "calm_version": __version__,
            "source_control": source_control_snapshot(source_path),
        },
        "environment": environment_snapshot(),
        "hardware": hardware_snapshot(),
        "configuration": {
            "fingerprint": sha256_value(configuration),
            "payload": redact_sensitive(configuration),
        },
        "runs": run_rows,
        "run_summary": {
            "total": len(run_rows),
            "by_type": dict(sorted(by_type.items())),
            "by_status": dict(sorted(by_status.items())),
        },
        "backends": collect_backend_identities(provenance_sources),
        "seeds": collect_seed_policy(provenance_sources),
        "files": reproducibility_file_inventory(
            root,
            exclude_paths=exclude_paths,
        ),
        "file_scope": {
            "included": (
                "deterministic logical calm.sqlite snapshot and regular files below the project root"
            ),
            "excluded": (
                "reproducibility manifests, retired calm-public-records.json files, "
                "SQLite WAL/SHM/journal files, temporary editor files, symlinks, "
                ".git, and Python/test caches"
            ),
        },
    }
    payload["snapshot_id"] = snapshot_id(payload)
    return ProjectReproducibilityManifest(payload=payload)


def _verify_reproducibility_manifest(
    project: Any,
    path: str | Path,
) -> ReproducibilityVerificationReport:
    source = Path(path).expanduser().resolve()
    recorded = ProjectReproducibilityManifest.read(source)
    current = _build_reproducibility_manifest(project, exclude_paths=(source,))
    issues: list[ReproducibilityIssue] = []

    def file_signature(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            str(key): jsonable(value)
            for key, value in row.items()
            if str(key) != "path"
        }

    recorded_files = {
        str(row.get("path")): file_signature(row) for row in recorded.files
    }
    current_files = {
        str(row.get("path")): file_signature(row) for row in current.files
    }
    for missing in sorted(set(recorded_files) - set(current_files)):
        issues.append(
            ReproducibilityIssue(
                "error", "file_missing", f"Recorded file is missing: {missing}"
            )
        )
    for added in sorted(set(current_files) - set(recorded_files)):
        issues.append(
            ReproducibilityIssue(
                "error", "file_added", f"Unrecorded project file exists: {added}"
            )
        )
    for common in sorted(set(recorded_files) & set(current_files)):
        if recorded_files[common] != current_files[common]:
            issues.append(
                ReproducibilityIssue(
                    "error", "file_changed", f"Project file changed: {common}"
                )
            )

    recorded_project = dict(recorded.payload.get("project") or {})
    current_project = dict(current.payload.get("project") or {})
    recorded_project.pop("path", None)
    current_project.pop("path", None)
    if recorded_project != current_project:
        issues.append(
            ReproducibilityIssue(
                "error",
                "project_schema_changed",
                "Project database schema state differs",
            )
        )

    comparisons = (
        ("software", "software_changed", "CALM source or version state differs"),
        ("environment", "environment_changed", "Python package environment differs"),
        ("hardware", "hardware_changed", "Hardware or operating-system state differs"),
        ("configuration", "configuration_changed", "Project configuration differs"),
        ("runs", "runs_changed", "Persisted run inventory differs"),
        ("backends", "backends_changed", "Backend/model identity differs"),
        ("seeds", "seeds_changed", "Recorded seed policy differs"),
    )
    for key, code, message in comparisons:
        if jsonable(recorded.payload.get(key)) != jsonable(current.payload.get(key)):
            severity = (
                "warning" if key in {"environment", "hardware", "software"} else "error"
            )
            issues.append(ReproducibilityIssue(severity, code, message))

    return ReproducibilityVerificationReport(
        manifest_path=source,
        recorded_snapshot_id=recorded.snapshot_id,
        current_snapshot_id=current.snapshot_id,
        issues=tuple(issues),
    )


__all__ = [
    "ProjectReproducibilityManifest",
    "ReproducibilityIssue",
    "ReproducibilityVerificationReport",
]
