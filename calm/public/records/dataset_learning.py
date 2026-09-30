"""Joined interface-learning dataset construction and readiness validation.

This module intentionally joins already authoritative workflow records. It does
not calculate scientific descriptors or infer new physical labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from calm.project.domain.contracts.dataset import (
    DATASET_SPLIT_COMPLETE_STATUS,
    dataset_group_uid,
    dataset_split_decision,
    dataset_split_provenance_status,
    validate_dataset_item_values,
    validate_learning_dataset_collection,
)

from calm.serialization.json import canonical_json

from calm.public.records.persistence import (
    ProjectEnergyResult,
    ProjectFollowupResult,
    ProjectInterface,
    ProjectRelaxationResult,
    ProjectThermodynamicResult,
)


def _path_value(context: Mapping[str, Any], path: str) -> Any:
    value: Any = context
    for part in str(path).split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        else:
            return None
    return value


def _coerce_declared_value(value: Any, *, dtype: str, name: str) -> Any:
    if value is None:
        return None
    if dtype == "float":
        if isinstance(value, bool):
            raise ValueError(f"Declared field {name!r} must be a float, not bool.")
        result = float(value)
        if not isfinite(result):
            raise ValueError(f"Declared field {name!r} must be finite.")
        return result
    if dtype == "int":
        if isinstance(value, bool):
            raise ValueError(f"Declared field {name!r} must be an int, not bool.")
        result = int(value)
        if float(value) != float(result):
            raise ValueError(f"Declared field {name!r} must be an integer.")
        return result
    if dtype == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"Declared field {name!r} must be a bool.")
        return value
    if dtype == "str":
        return str(value)
    raise ValueError(f"Unsupported declared dtype {dtype!r}.")


def _raw_energy_for_thermodynamic(
    project: Any,
    thermodynamic: ProjectThermodynamicResult,
) -> ProjectEnergyResult:
    uid = thermodynamic.raw_energy_followup_uid
    if not uid:
        raise ValueError("Thermodynamic result has no authoritative raw-energy source.")
    return project.energy_result(str(uid))


def _resolve_terminal_source(
    project: Any,
    item: Any,
) -> tuple[ProjectThermodynamicResult | None, ProjectEnergyResult]:
    if isinstance(item, ProjectThermodynamicResult):
        return item, _raw_energy_for_thermodynamic(project, item)
    if isinstance(item, ProjectEnergyResult):
        return None, item
    if isinstance(item, str):
        item = project.followup(item)
    if isinstance(item, ProjectFollowupResult):
        if item.kind == "thermodynamic_quantity":
            thermodynamic = ProjectThermodynamicResult.from_item(item)
            return thermodynamic, _raw_energy_for_thermodynamic(
                project,
                thermodynamic,
            )
        if item.kind == "energy_stage":
            return None, ProjectEnergyResult.from_item(item)
        raise ValueError(
            "Joined interface-learning datasets require an authoritative raw-energy "
            "or thermodynamic result source."
        )
    if isinstance(item, Mapping):
        kind = item.get("kind") or item.get("source_kind")
        if kind in {"thermodynamic_quantity", "thermodynamic"}:
            thermodynamic = ProjectThermodynamicResult.from_item(item)
            return thermodynamic, _raw_energy_for_thermodynamic(
                project,
                thermodynamic,
            )
        if kind in {"energy_stage", "raw_energy"}:
            return None, ProjectEnergyResult.from_item(item)
    raise TypeError(
        "Joined interface-learning datasets require raw-energy or "
        "thermodynamic result records or identifiers."
    )


def _resolve_relaxation(
    project: Any,
    interface: ProjectInterface,
) -> ProjectRelaxationResult:
    source_uid = interface.metadata.get("source_followup_uid")
    if source_uid:
        try:
            result = project.relaxation_result(str(source_uid))
        except (KeyError, ValueError):
            result = None
        if result is not None and result.relaxed_interface_uid == interface.uid_full:
            return result

    candidates: list[ProjectRelaxationResult] = []
    edges = project.edges(
        dst=str(interface.uid_full),
        kind="followup_to_interface",
        limit=100,
    )
    for edge in edges:
        uid = getattr(edge, "src_uid_full", None)
        if not uid:
            continue
        try:
            result = project.relaxation_result(str(uid))
        except (KeyError, ValueError):
            continue
        if result.relaxed_interface_uid == interface.uid_full:
            candidates.append(result)

    if not candidates:
        for result in project.relaxation_results(status="completed", limit=None):
            if result.relaxed_interface_uid == interface.uid_full:
                candidates.append(result)

    unique = {result.uid_full: result for result in candidates}
    if not unique:
        raise ValueError(
            "No authoritative relaxation result produces interface "
            f"{interface.uid_full!r}."
        )
    if len(unique) > 1:
        raise ValueError(
            "Joined dataset lineage is ambiguous: multiple relaxation results "
            f"produce interface {interface.uid_full!r}."
        )
    return next(iter(unique.values()))


def _scientific_authority(identity: Mapping[str, Any]) -> str:
    return str(identity.get("scientific_authority") or "").strip().lower()


def _validate_raw_lineage(
    interface: ProjectInterface,
    raw: ProjectEnergyResult,
) -> None:
    if not raw.succeeded:
        raise ValueError("Joined datasets require a completed raw-energy result.")
    if raw.energy_eV is None or not isfinite(float(raw.energy_eV)):
        raise ValueError("Joined dataset raw-energy values must be finite.")
    if _scientific_authority(raw.backend_identity) != "calculator_backed":
        raise ValueError("Joined dataset raw-energy sources must be calculator-backed.")
    if str(raw.target_kind or "") != "interface":
        raise ValueError("Joined dataset raw energy must target an interface.")
    if str(raw.target_uid_full or "") != str(interface.uid_full or ""):
        raise ValueError(
            "Joined dataset raw-energy target does not match the relaxed interface."
        )


def _validate_relaxation_lineage(
    interface: ProjectInterface,
    relaxation: ProjectRelaxationResult,
) -> None:
    if not relaxation.is_authoritative:
        raise ValueError("Joined dataset relaxation sources must be authoritative.")
    if not relaxation.succeeded or relaxation.converged is not True:
        raise ValueError(
            "Joined datasets require a completed, converged relaxation result."
        )
    if relaxation.residual_satisfied is not True:
        raise ValueError(
            "Joined datasets require a relaxation convergence certificate with "
            "residual_satisfied=True."
        )
    if _scientific_authority(relaxation.backend_identity) != "calculator_backed":
        raise ValueError("Joined dataset relaxation sources must be calculator-backed.")
    if str(relaxation.relaxed_interface_uid or "") != str(interface.uid_full or ""):
        raise ValueError(
            "Joined dataset relaxation output does not match the relaxed interface."
        )


def _joined_prototype_uid(
    interface: ProjectInterface,
    relaxation: ProjectRelaxationResult,
    raw: ProjectEnergyResult,
    thermodynamic: ProjectThermodynamicResult | None,
) -> str:
    values = [
        interface.prototype_uid_full,
        relaxation.prototype_uid_full,
        raw.prototype_uid_full,
    ]
    if thermodynamic is not None:
        values.append(thermodynamic.prototype_uid_full)
    if any(not value for value in values):
        raise ValueError("Joined dataset lineage has incomplete prototype identity.")
    prototype_uids = {str(value) for value in values}
    if len(prototype_uids) != 1:
        raise ValueError(
            "Joined dataset lineage has inconsistent or missing prototype identity."
        )
    return next(iter(prototype_uids))


def _validate_thermodynamic_lineage(
    interface: ProjectInterface,
    raw: ProjectEnergyResult,
    thermodynamic: ProjectThermodynamicResult | None,
) -> None:
    if thermodynamic is None:
        return
    if not thermodynamic.succeeded:
        raise ValueError("Joined datasets require a completed thermodynamic result.")
    if str(thermodynamic.target_uid_full or "") != str(interface.uid_full or ""):
        raise ValueError("Thermodynamic target does not match the relaxed interface.")
    if str(thermodynamic.raw_energy_followup_uid or "") != str(raw.uid_full or ""):
        raise ValueError(
            "Thermodynamic lineage does not match the selected raw-energy result."
        )
    if thermodynamic.calculator_compatibility.get("status") != "verified":
        raise ValueError(
            "Joined thermodynamic targets require calculator-verified references; "
            "manual or legacy-unverified references are not eligible."
        )


def _validate_joined_lineage(
    *,
    interface: ProjectInterface,
    relaxation: ProjectRelaxationResult,
    raw: ProjectEnergyResult,
    thermodynamic: ProjectThermodynamicResult | None,
) -> str:
    """Validate the exact authoritative lineage used by one learning row."""

    _validate_raw_lineage(interface, raw)
    _validate_relaxation_lineage(interface, relaxation)
    prototype_uid = _joined_prototype_uid(
        interface,
        relaxation,
        raw,
        thermodynamic,
    )
    _validate_thermodynamic_lineage(interface, raw, thermodynamic)
    return prototype_uid


def _joined_context(
    interface: ProjectInterface,
    relaxation: ProjectRelaxationResult,
    raw: ProjectEnergyResult,
    thermodynamic: ProjectThermodynamicResult | None,
    *,
    lineage: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the stable public field surface used by declarations."""

    interface_metadata = dict(interface.metadata or {})
    interface_values = {
        "label": interface.label,
        "stage": interface.stage,
        "search_name": interface_metadata.get("search_name"),
        "area_A2": interface_metadata.get("area_A2"),
        "strain_target_metric": interface_metadata.get("strain_target_metric"),
        "registry_settings": interface_metadata.get("registry_settings"),
        "relaxation_backend": interface_metadata.get("relaxation_backend"),
        "relaxation_settings": interface_metadata.get("relaxation_settings"),
    }
    relaxation_values = {
        "status": relaxation.status,
        "final_energy_eV": relaxation.final_energy_eV,
        "n_steps": relaxation.n_steps,
        "converged": relaxation.converged,
        "optimizer_reported_converged": relaxation.optimizer_reported_converged,
        "residual_satisfied": relaxation.residual_satisfied,
        "max_force_eV_per_A": relaxation.max_force_eV_per_A,
        "max_optimizer_residual": relaxation.max_optimizer_residual,
        "termination_reason": relaxation.termination_reason,
        "backend": relaxation.backend,
        "backend_identity": dict(relaxation.backend_identity),
        "settings": dict(relaxation.settings),
    }
    raw_values = {
        "status": raw.status,
        "quantity": raw.quantity,
        "energy_eV": raw.energy_eV,
        "backend": raw.backend,
        "backend_identity": dict(raw.backend_identity),
        "settings": dict(raw.settings),
    }
    thermodynamic_values: dict[str, Any] = {}
    if thermodynamic is not None:
        thermodynamic_values = {
            "status": thermodynamic.status,
            "quantity": thermodynamic.quantity,
            "formula_id": thermodynamic.formula_id,
            "value_eV_per_A2": thermodynamic.value_eV_per_A2,
            "value_J_per_m2": thermodynamic.value_J_per_m2,
            "normalization_area_A2": thermodynamic.normalization_area_A2,
            "n_interfaces": thermodynamic.n_interfaces,
            "convention": dict(thermodynamic.convention),
            "references": dict(thermodynamic.references),
            "reference_source": dict(thermodynamic.reference_source),
            "components": dict(thermodynamic.components),
            "units": dict(thermodynamic.units),
            "calculator_compatibility": dict(thermodynamic.calculator_compatibility),
        }
    return {
        "interface": interface_values,
        "relaxation": relaxation_values,
        "raw_energy": raw_values,
        "thermodynamic": thermodynamic_values,
        "lineage": dict(lineage),
    }


def build_joined_learning_row(
    project: Any,
    item: Any,
    *,
    settings: Any,
) -> dict[str, Any] | None:
    """Join one terminal energy record to its exact persisted workflow lineage."""

    thermodynamic, raw = _resolve_terminal_source(project, item)
    terminal = thermodynamic if thermodynamic is not None else raw
    failed = bool(getattr(terminal, "failure", None)) or terminal.status in {
        "failed",
        "error",
        "skipped",
    }
    if failed:
        if settings.failure_policy == "exclude":
            return None
        raise ValueError(f"Dataset source {terminal.uid_full!r} is failed.")
    if not raw.is_authoritative:
        raise ValueError("Joined dataset raw-energy sources must be authoritative.")
    if thermodynamic is not None and not thermodynamic.is_authoritative:
        raise ValueError("Joined dataset thermodynamic sources must be authoritative.")
    if not raw.target_uid_full:
        raise ValueError("Raw-energy result has no authoritative interface target.")

    interface = project.interface(str(raw.target_uid_full))
    if not interface.is_authoritative or interface.stage != "relaxed":
        raise ValueError(
            "Joined datasets require an authoritative relaxed-interface target."
        )
    relaxation = _resolve_relaxation(project, interface)
    prototype_uid = _validate_joined_lineage(
        interface=interface,
        relaxation=relaxation,
        raw=raw,
        thermodynamic=thermodynamic,
    )

    terminal_kind = (
        "thermodynamic_quantity" if thermodynamic is not None else "raw_energy"
    )
    provenance = {
        "prototype_uid_full": prototype_uid,
        "relaxed_interface_uid_full": interface.uid_full,
        "relaxation_run_uid_full": relaxation.run_uid_full,
        "relaxation_followup_uid": relaxation.uid_full,
        "raw_energy_run_uid_full": raw.run_uid_full,
        "raw_energy_followup_uid": raw.uid_full,
        "thermodynamic_run_uid_full": (
            thermodynamic.run_uid_full if thermodynamic is not None else None
        ),
        "thermodynamic_followup_uid": (
            thermodynamic.uid_full if thermodynamic is not None else None
        ),
        "terminal_source_kind": terminal_kind,
        "terminal_source_uid_full": terminal.uid_full,
        "relaxation": {
            "backend": relaxation.backend,
            "backend_identity": dict(relaxation.backend_identity),
            "scientific_authority": _scientific_authority(relaxation.backend_identity),
            "settings": dict(relaxation.settings),
            "converged": relaxation.converged,
            "optimizer_reported_converged": (relaxation.optimizer_reported_converged),
            "residual_satisfied": relaxation.residual_satisfied,
            "max_force_eV_per_A": relaxation.max_force_eV_per_A,
            "max_optimizer_residual": relaxation.max_optimizer_residual,
            "termination_reason": relaxation.termination_reason,
        },
        "raw_energy": {
            "quantity": raw.quantity,
            "energy_eV": raw.energy_eV,
            "units": raw.units,
            "backend": raw.backend,
            "backend_identity": dict(raw.backend_identity),
            "scientific_authority": _scientific_authority(raw.backend_identity),
            "settings": dict(raw.settings),
        },
        "thermodynamic": (
            {
                "quantity": thermodynamic.quantity,
                "formula_id": thermodynamic.formula_id,
                "normalization_area_A2": thermodynamic.normalization_area_A2,
                "n_interfaces": thermodynamic.n_interfaces,
                "convention": dict(thermodynamic.convention),
                "references": dict(thermodynamic.references),
                "reference_source": dict(thermodynamic.reference_source),
                "calculator_compatibility": dict(
                    thermodynamic.calculator_compatibility
                ),
                "verification_status": thermodynamic.calculator_compatibility.get(
                    "status"
                ),
                "components": dict(thermodynamic.components),
                "units": dict(thermodynamic.units),
            }
            if thermodynamic is not None
            else None
        ),
    }
    lineage_context = {
        "prototype": provenance["prototype_uid_full"],
        "relaxed_interface": provenance["relaxed_interface_uid_full"],
        "relaxation_result": provenance["relaxation_followup_uid"],
        "raw_energy_result": provenance["raw_energy_followup_uid"],
        "thermodynamic_result": provenance["thermodynamic_followup_uid"],
        "terminal_source": provenance["terminal_source_uid_full"],
    }
    context = _joined_context(
        interface,
        relaxation,
        raw,
        thermodynamic,
        lineage=lineage_context,
    )

    def materialize(declarations: Any) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for declaration in declarations:
            value = _path_value(context, declaration.source)
            if value is None and declaration.required:
                raise ValueError(
                    f"Required declared field {declaration.name!r} is unavailable "
                    f"at {declaration.source!r}."
                )
            values[declaration.name] = _coerce_declared_value(
                value,
                dtype=declaration.dtype,
                name=declaration.name,
            )
        return values

    features = materialize(settings.features)
    targets = materialize(settings.targets)

    group_values = {path: _path_value(context, path) for path in settings.group_by}
    missing_groups = [path for path, value in group_values.items() if value is None]
    if missing_groups:
        raise ValueError(
            "Dataset grouping fields are unavailable: " + ", ".join(missing_groups)
        )
    group_id = dataset_group_uid(group_values)
    split_settings = settings.split.to_dict()
    split_decision = dataset_split_decision(
        group_id=group_id,
        split=split_settings,
    )

    refs: list[Any] = []
    for record in (relaxation, raw):
        refs.extend(list(getattr(record, "artifact_refs", ()) or ()))
    refs = list(dict.fromkeys(str(value) for value in refs))

    return {
        "schema_version": settings.schema,
        "source_kind": "joined_interface_record",
        "source_uid_full": terminal.uid_full,
        "source_id_short": terminal.id_short,
        "terminal_source_kind": terminal_kind,
        "interface_uid_full": interface.uid_full,
        "interface_id_short": interface.id_short,
        "prototype_uid_full": prototype_uid,
        "interface_label": interface.label,
        "search_name": interface.metadata.get("search_name"),
        "interface_stage": interface.stage,
        "relaxation_run_uid_full": relaxation.run_uid_full,
        "relaxation_followup_uid": relaxation.uid_full,
        "raw_energy_run_uid_full": raw.run_uid_full,
        "raw_energy_followup_uid": raw.uid_full,
        "thermodynamic_run_uid_full": (
            thermodynamic.run_uid_full if thermodynamic is not None else None
        ),
        "thermodynamic_followup_uid": (
            thermodynamic.uid_full if thermodynamic is not None else None
        ),
        "features": features,
        "targets": targets,
        "group_by": group_values,
        "group_id": group_id,
        "split": split_decision.split_name,
        "split_contract_status": DATASET_SPLIT_COMPLETE_STATUS,
        "split_provenance": split_decision.to_dict(),
        "provenance": provenance,
        "status": terminal.status,
        "failure": (
            terminal.failure.to_dict() if getattr(terminal, "failure", None) else None
        ),
        "artifact_refs": refs,
    }


@dataclass(frozen=True)
class DatasetMLReadinessIssue:
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
class DatasetMLReadinessReport:
    dataset_uid_full: str
    n_items: int
    n_ready: int
    n_groups: int
    n_features: int
    n_targets: int
    split_counts: Mapping[str, int]
    issues: tuple[DatasetMLReadinessIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_uid_full": self.dataset_uid_full,
            "n_items": self.n_items,
            "n_ready": self.n_ready,
            "n_groups": self.n_groups,
            "n_features": self.n_features,
            "n_targets": self.n_targets,
            "split_counts": dict(self.split_counts),
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def summary(self) -> str:
        n_errors = sum(issue.severity == "error" for issue in self.issues)
        n_warnings = sum(issue.severity == "warning" for issue in self.issues)
        splits = ", ".join(
            f"{name}={count}" for name, count in sorted(self.split_counts.items())
        )
        return "\n".join(
            [
                f"ML readiness: {'ready' if self.ok else 'not ready'}",
                f"  items: {self.n_ready}/{self.n_items}",
                f"  groups: {self.n_groups}",
                f"  features: {self.n_features}",
                f"  targets: {self.n_targets}",
                f"  splits: {splits or 'none'}",
                f"  errors: {n_errors}",
                f"  warnings: {n_warnings}",
            ]
        )

    def raise_for_errors(self) -> None:
        if not self.ok:
            raise DatasetMLReadinessError(self)


class DatasetMLReadinessError(ValueError):
    def __init__(self, report: DatasetMLReadinessReport):
        self.report = report
        details = "; ".join(issue.message for issue in report.issues[:5])
        super().__init__(
            f"Dataset is not ML-ready with {len(report.issues)} issue(s)"
            + (f": {details}" if details else "")
        )


def _value_valid(value: Any, dtype: str) -> bool:
    if value is None:
        return False
    try:
        _coerce_declared_value(value, dtype=dtype, name="validation")
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def validate_ml_readiness(
    project: Any,
    dataset: Any,
    *,
    check_structures: bool = True,
) -> DatasetMLReadinessReport:
    """Validate declarations, lineage, leakage-safe splits, and structures."""

    from calm.public.inputs.settings import DatasetSettings

    settings = DatasetSettings(**dict(dataset.settings or {}))
    settings.validate()
    if not settings.is_learning_dataset:
        raise ValueError("ML readiness validation requires calm.interface_learning.v1.")

    items = list(dataset.items())
    issues: list[DatasetMLReadinessIssue] = []
    group_splits: dict[str, str] = {}
    split_counts = {"train": 0, "validation": 0, "test": 0}
    target_values: dict[str, list[Any]] = {
        target.name: [] for target in settings.targets
    }
    ready = 0
    settings_payload = settings.to_dict()
    rows: list[dict[str, Any]] = []

    for item in items:
        row = item.to_dict()
        rows.append(row)
        index = row.get("dataset_index", row.get("index"))
        try:
            index_int = int(index) if index is not None else None
        except (TypeError, ValueError):
            index_int = None
        before = len(issues)
        for message in validate_dataset_item_values(
            row,
            schema=settings.schema,
            settings=settings_payload,
        ):
            issues.append(
                DatasetMLReadinessIssue(
                    "invalid_dataset_contract",
                    message,
                    item.uid_full,
                    index_int,
                )
            )
        features = row.get("features")
        targets = row.get("targets")
        if not isinstance(features, Mapping):
            issues.append(
                DatasetMLReadinessIssue(
                    "invalid_features",
                    "features must be a mapping",
                    item.uid_full,
                    index_int,
                )
            )
            features = {}
        if not isinstance(targets, Mapping):
            issues.append(
                DatasetMLReadinessIssue(
                    "invalid_targets",
                    "targets must be a mapping",
                    item.uid_full,
                    index_int,
                )
            )
            targets = {}

        declared_values = (
            (settings.features, features, "feature"),
            (settings.targets, targets, "target"),
        )
        for declarations, values, kind in declared_values:
            for declaration in declarations:
                field_value = values.get(declaration.name)
                if field_value is None and not declaration.required:
                    continue
                if not _value_valid(field_value, declaration.dtype):
                    issues.append(
                        DatasetMLReadinessIssue(
                            f"invalid_{kind}",
                            (
                                f"{kind} {declaration.name!r} is missing or not "
                                f"{declaration.dtype}"
                            ),
                            item.uid_full,
                            index_int,
                        )
                    )
                elif kind == "target":
                    target_values[declaration.name].append(field_value)

        group_id = row.get("group_id")
        split_name = row.get("split")
        if not group_id:
            issues.append(
                DatasetMLReadinessIssue(
                    "missing_group",
                    "group_id is missing",
                    item.uid_full,
                    index_int,
                )
            )
        if split_name not in split_counts:
            issues.append(
                DatasetMLReadinessIssue(
                    "invalid_split",
                    f"split must be train, validation, or test; got {split_name!r}",
                    item.uid_full,
                    index_int,
                )
            )
        else:
            split_counts[str(split_name)] += 1
        if group_id and split_name in split_counts:
            previous = group_splits.setdefault(str(group_id), str(split_name))
            if previous != split_name:
                issues.append(
                    DatasetMLReadinessIssue(
                        "group_leakage",
                        (
                            f"group {group_id!r} occurs in both {previous!r} "
                            f"and {split_name!r}"
                        ),
                        item.uid_full,
                        index_int,
                    )
                )

        if group_id:
            split_status = dataset_split_provenance_status(
                row.get("split_provenance"),
                group_id=str(group_id),
                split=settings.split.to_dict(),
            )
            if split_status != DATASET_SPLIT_COMPLETE_STATUS:
                issues.append(
                    DatasetMLReadinessIssue(
                        "invalid_split_contract",
                        (
                            "split provenance does not match the current "
                            "reconstructible version-2 contract"
                        ),
                        item.uid_full,
                        index_int,
                    )
                )

        provenance = row.get("provenance")
        if not isinstance(provenance, Mapping) or not all(
            provenance.get(key)
            for key in (
                "relaxed_interface_uid_full",
                "relaxation_followup_uid",
                "raw_energy_followup_uid",
                "terminal_source_uid_full",
            )
        ):
            issues.append(
                DatasetMLReadinessIssue(
                    "incomplete_joined_provenance",
                    "joined structure-relaxation-energy provenance is incomplete",
                    item.uid_full,
                    index_int,
                )
            )

        if check_structures and row.get("interface_uid_full"):
            try:
                atoms = project._structure_queries.get_interface_atoms(
                    str(row["interface_uid_full"])
                )
            except KeyError as exc:
                issues.append(
                    DatasetMLReadinessIssue(
                        "structure_unavailable",
                        str(exc),
                        item.uid_full,
                        index_int,
                    )
                )
            else:
                if atoms is None:
                    issues.append(
                        DatasetMLReadinessIssue(
                            "structure_unavailable",
                            "authoritative relaxed structure is unavailable",
                            item.uid_full,
                            index_int,
                        )
                    )

        item_errors = [issue for issue in issues[before:] if issue.severity == "error"]
        if not item_errors:
            ready += 1

    for name, count in split_counts.items():
        if count == 0:
            issues.append(
                DatasetMLReadinessIssue(
                    "empty_split",
                    f"configured split {name!r} contains no items",
                    severity="warning",
                )
            )
    if len(group_splits) < 2:
        issues.append(
            DatasetMLReadinessIssue(
                "insufficient_groups",
                "fewer than two independent groups are available",
                severity="warning",
            )
        )
    for name, values in target_values.items():
        if len(values) > 1 and len({canonical_json(value) for value in values}) == 1:
            issues.append(
                DatasetMLReadinessIssue(
                    "constant_target",
                    f"target {name!r} is constant across all ready values",
                    severity="warning",
                )
            )

    for message in validate_learning_dataset_collection(rows):
        issues.append(
            DatasetMLReadinessIssue(
                "learning_collection_invariant",
                message,
            )
        )

    return DatasetMLReadinessReport(
        dataset_uid_full=str(dataset.uid_full or ""),
        n_items=len(items),
        n_ready=ready,
        n_groups=len(group_splits),
        n_features=len(settings.features),
        n_targets=len(settings.targets),
        split_counts=split_counts,
        issues=tuple(issues),
    )


def learning_row_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten one persisted joined record for CSV/DataFrame workflows."""

    out = {
        "dataset_index": row.get("dataset_index", row.get("index")),
        "source_id": row.get("source_id_short"),
        "source_kind": row.get("terminal_source_kind"),
        "interface_id": row.get("interface_id_short"),
        "interface_label": row.get("interface_label"),
        "search_name": row.get("search_name"),
        "group_id": row.get("group_id"),
        "split": row.get("split"),
    }
    for prefix, values in (
        ("feature", row.get("features")),
        ("target", row.get("targets")),
    ):
        if isinstance(values, Mapping):
            for name, value in values.items():
                out[f"{prefix}_{name}"] = value
    return out
