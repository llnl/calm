"""Dataset export helpers for public CALM selections."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from calm.project.domain.contracts.dataset import (
    canonical_dataset_schema,
    dataset_content_fingerprint,
    dataset_schema_contract,
    dataset_split_contract,
    validate_dataset_item_values,
    validate_learning_dataset_collection,
)

from calm.public.records.dataset_learning import (
    DatasetMLReadinessError as DatasetMLReadinessError,
    DatasetMLReadinessIssue as DatasetMLReadinessIssue,
    DatasetMLReadinessReport as DatasetMLReadinessReport,
)


# -----------------------------------------------------------------------------
# Phase 7 authoritative dataset lifecycle
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetValidationIssue:
    """Describe one structured dataset validation issue.

    ``code`` is the stable machine-readable category, ``message`` is the
    human-readable explanation, and the optional item UID and dataset index locate
    the affected membership record. ``severity`` distinguishes errors from
    non-blocking warnings.
    """

    code: str
    message: str
    item_uid_full: str | None = None
    dataset_index: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "item_uid_full": self.item_uid_full,
            "dataset_index": self.dataset_index,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class DatasetValidationReport:
    """Summarize validation of one authoritative dataset.

    The report records item counts, structured issues, schema version, and the
    content fingerprint calculated for the validated membership. ``ok`` is
    false whenever at least one issue has ``severity='error'``.
    """

    dataset_uid_full: str
    schema_version: str
    n_items: int
    n_valid: int
    issues: tuple[DatasetValidationIssue, ...] = ()
    content_fingerprint: str | None = None

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_uid_full": self.dataset_uid_full,
            "schema_version": self.schema_version,
            "n_items": self.n_items,
            "n_valid": self.n_valid,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "content_fingerprint": self.content_fingerprint,
        }

    def summary(self) -> str:
        """Return a stable user-facing validation summary."""
        n_errors = sum(issue.severity == "error" for issue in self.issues)
        n_warnings = sum(issue.severity == "warning" for issue in self.issues)
        status = "valid" if self.ok else "invalid"
        return "\n".join(
            [
                f"Dataset validation: {status}",
                f"  schema: {self.schema_version}",
                f"  items: {self.n_items}",
                f"  valid items: {self.n_valid}",
                f"  errors: {n_errors}",
                f"  warnings: {n_warnings}",
            ]
        )

    def raise_for_errors(self) -> None:
        """Raise ``DatasetValidationError`` when validation failed."""
        if not self.ok:
            raise DatasetValidationError(self)


@dataclass(frozen=True)
class DatasetExportResult:
    """Describe the result of an atomic dataset-bundle export.

    The result identifies the authoritative dataset, destination, manifest,
    exported files, checksums, item count, and optional content fingerprint. Paths
    refer to the completed bundle after the atomic export succeeds.
    """

    dataset_uid_full: str
    destination: Path
    manifest_path: Path
    n_items: int
    files: tuple[Path, ...] = ()
    checksums: Mapping[str, str] = field(default_factory=dict)
    content_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_uid_full": self.dataset_uid_full,
            "destination": str(self.destination),
            "manifest_path": str(self.manifest_path),
            "n_items": self.n_items,
            "files": [str(path) for path in self.files],
            "checksums": dict(self.checksums),
            "content_fingerprint": self.content_fingerprint,
        }

    def summary(self) -> str:
        """Return a stable user-facing export summary."""
        return "\n".join(
            [
                "Dataset export: complete",
                f"  destination: {self.destination}",
                f"  manifest: {self.manifest_path}",
                f"  items: {self.n_items}",
                f"  files: {len(self.files)}",
                f"  checksums: {len(self.checksums)}",
            ]
        )


class DatasetValidationError(ValueError):
    """Signal that an authoritative dataset failed validation.

    The original structured ``DatasetValidationReport`` is retained on the
    exception as ``report`` so callers can inspect individual issues.
    """

    def __init__(self, report: DatasetValidationReport):
        self.report = report
        details = "; ".join(issue.message for issue in report.issues[:5])
        super().__init__(
            f"Dataset validation failed with {len(report.issues)} issue(s)"
            + (f": {details}" if details else "")
        )


def _failure_value(record: Any) -> Any:
    failure = getattr(record, "failure", None)
    if failure is not None:
        return failure.to_dict() if hasattr(failure, "to_dict") else failure
    if isinstance(record, Mapping):
        return record.get("failure") or record.get("error")
    return None


def _record_status(record: Any) -> str | None:
    if isinstance(record, Mapping):
        value = record.get("status")
    else:
        value = getattr(record, "status", None)
    return str(value) if value is not None else None


def _artifact_refs(record: Any) -> list[Any]:
    if isinstance(record, Mapping):
        refs = record.get("artifact_refs") or []
    else:
        refs = getattr(record, "artifact_refs", ()) or ()
    return list(refs)


def normalize_authoritative_dataset_source(
    project: Any,
    item: Any,
    *,
    settings: Any,
) -> dict[str, Any] | None:
    """Normalize one authoritative project record into a schema item row."""

    from calm.public.records.persistence import (
        ProjectEnergyResult,
        ProjectInterface,
        ProjectThermodynamicResult,
    )

    schema = canonical_dataset_schema(settings.schema_version)
    source_kind = dataset_schema_contract(schema)["source_kind"]

    if source_kind == "joined_interface_record":
        from calm.public.records.dataset_learning import build_joined_learning_row

        canonical = build_joined_learning_row(
            project,
            item,
            settings=settings,
        )
        if canonical is None:
            return None
        authoritative = True
    elif source_kind == "interface":
        record = (
            item
            if isinstance(item, ProjectInterface)
            else (
                project.interface(item)
                if isinstance(item, str)
                else ProjectInterface.from_item(item)
            )
        )
        row = record.to_dict()
        canonical = {
            "schema_version": schema,
            "source_kind": source_kind,
            "source_uid_full": record.uid_full,
            "source_id_short": record.id_short,
            "interface_uid_full": record.uid_full,
            "interface_id_short": record.id_short,
            "prototype_uid_full": record.prototype_uid_full,
            "stage": record.stage,
            "label": record.label,
            "search_name": row.get("search_name"),
            "status": row.get("status") or "completed",
            "failure": _failure_value(record),
            "artifact_refs": _artifact_refs(row),
        }
        authoritative = record.is_authoritative
    elif source_kind == "raw_energy":
        record = (
            item
            if isinstance(item, ProjectEnergyResult)
            else (
                project.energy_result(item)
                if isinstance(item, str)
                else ProjectEnergyResult.from_item(item)
            )
        )
        canonical = {
            "schema_version": schema,
            "source_kind": source_kind,
            "source_uid_full": record.uid_full,
            "source_id_short": record.id_short,
            "run_uid_full": record.run_uid_full,
            "run_id_short": record.run_id_short,
            "interface_uid_full": record.target_uid_full,
            "prototype_uid_full": record.prototype_uid_full,
            "quantity": record.quantity,
            "energy_eV": record.energy_eV,
            "units": record.units,
            "backend": record.backend,
            "backend_identity": dict(record.backend_identity),
            "settings": dict(record.settings),
            "status": record.status,
            "failure": _failure_value(record),
            "artifact_refs": list(record.artifact_refs),
        }
        authoritative = record.is_authoritative
    else:
        record = (
            item
            if isinstance(item, ProjectThermodynamicResult)
            else (
                project.thermodynamic_result(item)
                if isinstance(item, str)
                else ProjectThermodynamicResult.from_item(item)
            )
        )
        raw = None
        if record.raw_energy_followup_uid:
            raw = project.energy_result(record.raw_energy_followup_uid)
        canonical = {
            "schema_version": schema,
            "source_kind": source_kind,
            "source_uid_full": record.uid_full,
            "source_id_short": record.id_short,
            "run_uid_full": record.run_uid_full,
            "run_id_short": record.run_id_short,
            "interface_uid_full": getattr(raw, "target_uid_full", None),
            "prototype_uid_full": record.prototype_uid_full,
            "raw_energy_followup_uid": record.raw_energy_followup_uid,
            "quantity": record.quantity,
            "formula_id": record.formula_id,
            "value_eV_per_A2": record.value_eV_per_A2,
            "value_J_per_m2": record.value_J_per_m2,
            "normalization_area_A2": record.normalization_area_A2,
            "n_interfaces": record.n_interfaces,
            "convention": dict(record.convention),
            "references": dict(record.references),
            "components": dict(record.components),
            "units": dict(record.units),
            "status": record.status,
            "failure": _failure_value(record),
            "artifact_refs": list(getattr(raw, "artifact_refs", ()) or ()),
        }
        authoritative = record.is_authoritative

    if settings.require_complete_provenance and not authoritative:
        raise ValueError("Dataset items must be authoritative project records.")

    failed = bool(canonical.get("failure")) or canonical.get("status") in {
        "failed",
        "error",
        "skipped",
    }
    if failed:
        if settings.failure_policy == "error":
            raise ValueError(
                f"Dataset source {canonical.get('source_uid_full')!r} is failed."
            )
        if settings.failure_policy == "exclude":
            return None

    messages = validate_dataset_item_values(
        canonical,
        schema=schema,
        allow_failed=settings.failure_policy == "include",
        settings=settings.to_dict(),
    )
    if messages and settings.require_complete_provenance:
        raise ValueError(
            f"Dataset source {canonical.get('source_uid_full')!r} is incomplete: "
            + "; ".join(messages)
        )
    return canonical


def validate_persisted_dataset(project: Any, dataset: Any) -> DatasetValidationReport:
    from calm.public.inputs.settings import DatasetSettings

    uid = str(dataset.uid_full or "")
    settings = DatasetSettings(**dict(dataset.settings or {}))
    settings.validate()
    schema = settings.schema
    items = list(dataset.items())
    issues: list[DatasetValidationIssue] = []
    valid = 0
    seen_sources: set[str] = set()
    seen_indices: set[int] = set()
    settings_payload = settings.to_dict()
    rows: list[dict[str, Any]] = []

    for item in items:
        row = item.to_dict()
        rows.append(row)
        source_uid = str(row.get("source_uid_full") or "")
        index = row.get("dataset_index")
        if index is None:
            index = row.get("index")
        try:
            index_int = int(index) if index is not None else None
        except (TypeError, ValueError):
            index_int = None

        item_issues = validate_dataset_item_values(
            row,
            schema=schema,
            allow_failed=settings.failure_policy == "include",
            settings=settings_payload,
        )
        for message in item_issues:
            issues.append(
                DatasetValidationIssue(
                    code="invalid_item",
                    message=message,
                    item_uid_full=item.uid_full,
                    dataset_index=index_int,
                )
            )

        if source_uid in seen_sources:
            issues.append(
                DatasetValidationIssue(
                    code="duplicate_source",
                    message=f"source {source_uid!r} occurs more than once",
                    item_uid_full=item.uid_full,
                    dataset_index=index_int,
                )
            )
        seen_sources.add(source_uid)

        if index_int is None:
            issues.append(
                DatasetValidationIssue(
                    code="missing_index",
                    message="dataset item has no integer dataset_index",
                    item_uid_full=item.uid_full,
                )
            )
        elif index_int in seen_indices:
            issues.append(
                DatasetValidationIssue(
                    code="duplicate_index",
                    message=f"dataset_index {index_int} occurs more than once",
                    item_uid_full=item.uid_full,
                    dataset_index=index_int,
                )
            )
        else:
            seen_indices.add(index_int)

        if settings.require_complete_provenance and source_uid:
            try:
                project._repo.resolve_identifier(source_uid)
            except (KeyError, ValueError) as exc:
                issues.append(
                    DatasetValidationIssue(
                        code="missing_source",
                        message=(
                            f"authoritative source {source_uid!r} cannot be "
                            f"resolved: {exc}"
                        ),
                        item_uid_full=item.uid_full,
                        dataset_index=index_int,
                    )
                )
            except Exception as exc:
                issues.append(
                    DatasetValidationIssue(
                        code="source_resolution_failed",
                        message=(
                            "authoritative source resolution failed with "
                            f"{type(exc).__name__}: {exc}"
                        ),
                        item_uid_full=item.uid_full,
                        dataset_index=index_int,
                    )
                )
            if item.uid_full:
                edges = project._repo.list_edges(
                    src=item.uid_full,
                    dst=source_uid,
                    kind="dataset_item_from_source",
                    limit=10,
                )
                if not edges:
                    issues.append(
                        DatasetValidationIssue(
                            code="missing_provenance_edge",
                            message="dataset item has no authoritative source edge",
                            item_uid_full=item.uid_full,
                            dataset_index=index_int,
                        )
                    )
                provenance = row.get("provenance")
                if isinstance(provenance, Mapping):
                    component_uids = {
                        str(value)
                        for key, value in provenance.items()
                        if key.endswith("_uid_full") or key.endswith("_followup_uid")
                        if value and str(value) != source_uid
                    }
                    for component_uid in sorted(component_uids):
                        component_edges = project._repo.list_edges(
                            src=item.uid_full,
                            dst=component_uid,
                            kind="dataset_item_from_component",
                            limit=10,
                        )
                        if not component_edges:
                            issues.append(
                                DatasetValidationIssue(
                                    code="missing_component_edge",
                                    message=(
                                        "joined dataset item has no component edge to "
                                        f"{component_uid!r}"
                                    ),
                                    item_uid_full=item.uid_full,
                                    dataset_index=index_int,
                                )
                            )

        failed = bool(row.get("failure")) or row.get("status") in {
            "failed",
            "error",
            "skipped",
        }
        if failed and settings.failure_policy == "error":
            issues.append(
                DatasetValidationIssue(
                    code="failed_source",
                    message="failed source is forbidden by dataset failure policy",
                    item_uid_full=item.uid_full,
                    dataset_index=index_int,
                )
            )

        if not any(
            issue.item_uid_full == item.uid_full and issue.severity == "error"
            for issue in issues
        ):
            valid += 1

    expected_indices = set(range(len(items)))
    if seen_indices != expected_indices:
        issues.append(
            DatasetValidationIssue(
                code="noncontiguous_indices",
                message=(
                    "dataset indices must be contiguous from 0; "
                    f"found {sorted(seen_indices)}"
                ),
            )
        )

    if settings.is_learning_dataset:
        for message in validate_learning_dataset_collection(rows):
            issues.append(
                DatasetValidationIssue(
                    code="learning_collection_invariant",
                    message=message,
                )
            )

    content_fingerprint = dataset_content_fingerprint(
        schema=schema,
        settings=settings_payload,
        rows=rows,
    )

    return DatasetValidationReport(
        dataset_uid_full=uid,
        schema_version=schema,
        n_items=len(items),
        n_valid=valid,
        issues=tuple(issues),
        content_fingerprint=content_fingerprint,
    )


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_persisted_dataset(
    project: Any,
    dataset: Any,
    destination: str | Path,
    *,
    manifest_format: str = "json",
    include_structures: bool = True,
    structure_format: str = "extxyz",
    overwrite: bool = False,
) -> DatasetExportResult:
    manifest_format = str(manifest_format).lower()
    if manifest_format not in {"json", "jsonl"}:
        raise ValueError("manifest_format must be 'json' or 'jsonl'.")
    if not isinstance(include_structures, bool):
        raise TypeError("include_structures must be a bool.")
    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be a bool.")

    report = validate_persisted_dataset(project, dataset)
    if not report.ok:
        raise DatasetValidationError(report)

    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise FileExistsError(
            f"Dataset export destination already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.bak-{uuid.uuid4().hex}"
    temporary.mkdir(parents=False, exist_ok=False)

    files: list[Path] = []
    rows = sorted(
        [item.to_dict() for item in dataset.items()],
        key=lambda row: int(row.get("dataset_index", row.get("index", 0)) or 0),
    )
    structure_export = {
        "requested": include_structures,
        "format": structure_format if include_structures else None,
        "n_exported": 0,
        "n_unavailable": 0,
    }
    try:
        if include_structures:
            structures = temporary / "structures"
            structures.mkdir()
            for row in rows:
                interface_uid = row.get("interface_uid_full")
                if not interface_uid:
                    row["structure_status"] = "unavailable"
                    row["structure_error"] = (
                        "Dataset item has no interface_uid_full for structure export."
                    )
                    structure_export["n_unavailable"] += 1
                    continue
                try:
                    atoms = project._structure_queries.get_interface_atoms(
                        str(interface_uid)
                    )
                except KeyError as exc:
                    row["structure_status"] = "unavailable"
                    row["structure_error"] = str(exc)
                    structure_export["n_unavailable"] += 1
                    continue
                if atoms is None:
                    row["structure_status"] = "unavailable"
                    row["structure_error"] = (
                        f"No atomistic structure is available for {interface_uid!r}."
                    )
                    structure_export["n_unavailable"] += 1
                    continue
                index = int(row.get("dataset_index", row.get("index", 0)) or 0)
                suffix = (
                    "xyz" if structure_format in {"extxyz", "xyz"} else structure_format
                )
                filename = f"{index:06d}_{_safe_filename(str(interface_uid))}.{suffix}"
                path = structures / filename
                atoms.write(path, format=structure_format)
                row["structure_status"] = "exported"
                row["structure_file"] = str(Path("structures") / filename)
                structure_export["n_exported"] += 1
                files.append(path)

        split_summary: dict[str, int] = {}
        for row in rows:
            split_name = row.get("split")
            if split_name:
                key = str(split_name)
                split_summary[key] = split_summary.get(key, 0) + 1
        settings_payload = dict(dataset.settings)
        split_settings_payload = settings_payload.get("split")
        if split_settings_payload is not None and not isinstance(
            split_settings_payload, Mapping
        ):
            raise TypeError("Dataset split settings must be a mapping or None.")
        dataset_payload = {
            "schema_version": dataset.schema_version,
            "dataset_uid_full": dataset.uid_full,
            "dataset_id_short": dataset.id_short,
            "name": dataset.name,
            "description": dataset.description,
            "settings": settings_payload,
            "feature_declarations": list(settings_payload.get("features") or []),
            "target_declarations": list(settings_payload.get("targets") or []),
            "group_by": list(settings_payload.get("group_by") or []),
            "split_settings": split_settings_payload,
            "split_contract": (
                dataset_split_contract() if split_settings_payload is not None else None
            ),
            "split_summary": split_summary,
            "content_fingerprint": report.content_fingerprint,
            "n_items": len(rows),
            "structure_export": structure_export,
            "items": rows,
        }
        if manifest_format == "json":
            manifest = temporary / "manifest.json"
            manifest.write_text(
                json.dumps(dataset_payload, indent=2, sort_keys=True, default=str)
                + "\n",
                encoding="utf-8",
            )
        else:
            manifest = temporary / "manifest.jsonl"
            with manifest.open("w", encoding="utf-8") as handle:
                header = {
                    key: value
                    for key, value in dataset_payload.items()
                    if key != "items"
                }
                handle.write(
                    json.dumps(
                        {"record_type": "dataset", **header},
                        sort_keys=True,
                        default=str,
                    )
                    + "\n"
                )
                for row in rows:
                    handle.write(
                        json.dumps(
                            {"record_type": "item", **row}, sort_keys=True, default=str
                        )
                        + "\n"
                    )
        files.append(manifest)

        checksums = {
            str(path.relative_to(temporary)): _sha256(path) for path in sorted(files)
        }
        checksum_path = temporary / "checksums.sha256"
        checksum_path.write_text(
            "".join(
                f"{digest}  {name}\n" for name, digest in sorted(checksums.items())
            ),
            encoding="utf-8",
        )
        files.append(checksum_path)

        moved_backup = False
        if destination.exists():
            os.replace(destination, backup)
            moved_backup = True
        try:
            os.replace(temporary, destination)
        except Exception:
            if moved_backup and backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)

        final_files = tuple(destination / path.relative_to(temporary) for path in files)
        return DatasetExportResult(
            dataset_uid_full=str(dataset.uid_full),
            destination=destination,
            manifest_path=destination / manifest.name,
            n_items=len(rows),
            files=final_files,
            checksums=checksums,
            content_fingerprint=report.content_fingerprint,
        )
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        raise
