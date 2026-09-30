"""Typed public records for persisted project state.

The project database is authoritative. Public immutable records normalize
database entities and reproducible result projections while preserving explicit
authority metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence, TextIO

from calm.public.records.dataset_views import DATASET_ITEM_VIEW_SPECS


class RecordAuthority(str, Enum):
    """Origin of a public project record."""

    AUTHORITATIVE = "authoritative"
    PROJECTION = "projection"


_MISSING = object()


def _mapping(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)

    to_dict = getattr(item, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if not isinstance(value, Mapping):
            raise TypeError(f"{type(item).__name__}.to_dict() must return a mapping.")
        return dict(value)

    try:
        values = vars(item)
    except TypeError as exc:
        raise TypeError(
            f"Cannot project {type(item).__name__} as a public project record."
        ) from exc
    return {key: value for key, value in values.items() if not key.startswith("_")}


def _get(item: Any, *names: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        for name in names:
            if name in item:
                return item[name]
    for name in names:
        value = getattr(item, name, _MISSING)
        if value is not _MISSING and value is not None:
            return value
    return default


def record_authority(
    item: Any, *, authoritative_keys: tuple[str, ...] = ()
) -> RecordAuthority:
    """Infer whether *item* is backed by an authoritative project record."""

    explicit = _get(item, "authority", "_authority")
    if explicit is not None:
        return RecordAuthority(str(getattr(explicit, "value", explicit)))

    if not isinstance(item, Mapping) and _get(item, "uid_full"):
        return RecordAuthority.AUTHORITATIVE

    row = _mapping(item)
    if row.get("_object") is not None and _get(row.get("_object"), "uid_full"):
        return RecordAuthority.AUTHORITATIVE
    for key in ("uid_full", *authoritative_keys):
        if row.get(key):
            return RecordAuthority.AUTHORITATIVE
    return RecordAuthority.PROJECTION


class _MappingRecord:
    """Small mapping-compatible mixin used by public immutable records."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    @property
    def is_authoritative(self) -> bool:
        return self.authority is RecordAuthority.AUTHORITATIVE  # type: ignore[attr-defined]


@dataclass(frozen=True)
class FailureRecord(_MappingRecord):
    """Structured failure attached to a run or follow-up result."""

    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Any) -> "FailureRecord | None":
        if value in (None, "", {}):
            return None
        if isinstance(value, Mapping):
            details = dict(value)
            message = str(
                details.get("message")
                or details.get("error")
                or details.get("reason")
                or "Project operation failed"
            )
            return cls(message=message, details=details)
        return cls(message=str(value), details={"error": str(value)})

    def to_dict(self) -> dict[str, Any]:
        return {"message": self.message, "details": dict(self.details)}


@dataclass(frozen=True)
class ProjectRun(_MappingRecord):
    """Represent one authoritative persisted workflow run.

    The record preserves run identity, type, status, identity-bearing
    specification, progress, failure information, and timestamps. It is immutable
    and mapping-compatible through ``to_dict()``.
    """

    uid_full: str
    id_short: str
    run_type: str
    status: str
    spec: Mapping[str, Any] = field(default_factory=dict)
    progress: Mapping[str, Any] | None = None
    failure: FailureRecord | None = None
    created_at: str | None = None
    updated_at: str | None = None
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectRun":
        uid = _get(item, "uid_full", "run_uid", default="")
        sid = _get(item, "id_short", "run_id", default="")
        error = _get(item, "error")
        return cls(
            uid_full=str(uid or ""),
            id_short=str(sid or ""),
            run_type=str(_get(item, "run_type", "kind", default="") or ""),
            status=str(_get(item, "status", default="") or ""),
            spec=dict(_get(item, "spec", default={}) or {}),
            progress=(dict(_get(item, "progress") or {}) or None),
            failure=FailureRecord.from_value(error),
            created_at=_get(item, "created_at"),
            updated_at=_get(item, "updated_at"),
            authority=record_authority(item),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "id_short": self.id_short,
            "run_type": self.run_type,
            "status": self.status,
            "spec": dict(self.spec),
            "progress": dict(self.progress) if self.progress is not None else None,
            "failure": self.failure.to_dict() if self.failure else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class ProjectSearch(_MappingRecord):
    """Represent a persisted interface-search record.

    Authoritative rows retain the unique public name, deterministic scientific
    identity, content-addressed run identity, and current run state. Reporting
    projections do not create persisted searches.
    """

    name: str
    uid_full: str | None = None
    id_short: str | None = None
    run_uid_full: str | None = None
    run_id_short: str | None = None
    search_identity: str | None = None
    status: str | None = None
    n_candidates: int | None = None
    settings: Mapping[str, Any] = field(default_factory=dict)
    spec: Mapping[str, Any] = field(default_factory=dict)
    progress: Mapping[str, Any] | None = None
    failure: FailureRecord | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    authority: RecordAuthority = RecordAuthority.PROJECTION

    @classmethod
    def from_item(cls, item: Any) -> "ProjectSearch":
        row = _mapping(item)
        spec = dict(_get(item, "spec", default={}) or {})
        name = (
            row.get("name")
            or row.get("search_name")
            or row.get("search_id")
            or _get(item, "id_short")
            or _get(item, "uid_full")
            or ""
        )
        known = {
            "uid_full",
            "id_short",
            "run_type",
            "status",
            "spec",
            "settings",
            "search_identity",
            "run_uid_full",
            "run_id_short",
            "error",
            "failure",
            "created_at",
            "updated_at",
            "name",
            "search_name",
            "search_id",
            "n_candidates",
            "progress",
        }
        return cls(
            name=str(name),
            uid_full=_get(item, "uid_full", "run_uid_full"),
            id_short=_get(item, "id_short", "run_id_short"),
            run_uid_full=_get(item, "run_uid_full", "uid_full"),
            run_id_short=_get(item, "run_id_short", "id_short"),
            search_identity=(row.get("search_identity") or spec.get("search_identity")),
            status=_get(item, "status"),
            n_candidates=(
                int(row["n_candidates"])
                if row.get("n_candidates") is not None
                else None
            ),
            settings=dict(row.get("settings") or spec.get("settings") or {}),
            spec=spec,
            progress=(dict(_get(item, "progress") or {}) or None),
            failure=FailureRecord.from_value(row.get("error") or _get(item, "error")),
            metadata={
                k: v for k, v in row.items() if k not in known and not k.startswith("_")
            },
            created_at=_get(item, "created_at"),
            updated_at=_get(item, "updated_at"),
            authority=record_authority(item),
        )

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "search_id": self.name,
                "search_name": self.name,
                "name": self.name,
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "run_uid_full": self.run_uid_full,
                "run_id_short": self.run_id_short,
                "search_identity": self.search_identity,
                "status": self.status,
                "n_candidates": self.n_candidates,
                "settings": dict(self.settings),
                "spec": dict(self.spec),
                "progress": (
                    dict(self.progress) if self.progress is not None else None
                ),
                "failure": self.failure.to_dict() if self.failure else None,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "authority": self.authority.value,
            }
        )
        return row


@dataclass(frozen=True)
class ProjectFollowupResult(_MappingRecord):
    """Represent an authoritative follow-up result, including failures.

    Follow-up records connect a run to a prototype or interface target and retain
    kind-specific scalar summaries, the complete payload, and structured failure
    information. The payload remains the source for details not promoted to typed
    fields.
    """

    uid_full: str
    id_short: str
    kind: str
    status: str
    run_uid_full: str | None = None
    run_id_short: str | None = None
    prototype_uid_full: str | None = None
    prototype_id_short: str | None = None
    target_uid_full: str | None = None
    target_id_short: str | None = None
    target_kind: str | None = None
    best_energy: float | None = None
    param1: float | None = None
    param2: float | None = None
    n_points: int | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    failure: FailureRecord | None = None
    created_at: str | None = None
    updated_at: str | None = None
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectFollowupResult":
        payload = dict(_get(item, "payload", default={}) or {})
        failure = FailureRecord.from_value(
            payload.get("error") or payload.get("failure") or payload.get("reason")
        )
        status = str(_get(item, "status", default="done") or "done")
        if failure is not None and status == "done":
            status = "failed"
        return cls(
            uid_full=str(_get(item, "uid_full", default="") or ""),
            id_short=str(_get(item, "id_short", default="") or ""),
            kind=str(_get(item, "kind", default="") or ""),
            status=status,
            run_uid_full=_get(item, "run_uid_full"),
            run_id_short=_get(item, "run_id_short"),
            prototype_uid_full=_get(item, "prototype_uid_full"),
            prototype_id_short=_get(item, "prototype_id_short"),
            target_uid_full=_get(item, "target_uid_full"),
            target_id_short=_get(item, "target_id_short"),
            target_kind=_get(item, "target_kind"),
            best_energy=_get(item, "best_energy"),
            param1=_get(item, "param1"),
            param2=_get(item, "param2"),
            n_points=_get(item, "n_points"),
            payload=payload,
            failure=failure,
            created_at=_get(item, "created_at"),
            updated_at=_get(item, "updated_at"),
            authority=record_authority(item),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "id_short": self.id_short,
            "kind": self.kind,
            "status": self.status,
            "run_uid_full": self.run_uid_full,
            "run_id_short": self.run_id_short,
            "prototype_uid_full": self.prototype_uid_full,
            "prototype_id_short": self.prototype_id_short,
            "target_uid_full": self.target_uid_full,
            "target_id_short": self.target_id_short,
            "target_kind": self.target_kind,
            "best_energy": self.best_energy,
            "param1": self.param1,
            "param2": self.param2,
            "n_points": self.n_points,
            "payload": dict(self.payload),
            "failure": self.failure.to_dict() if self.failure else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class ProjectRelaxationResult(_MappingRecord):
    """Typed authoritative result for one structural-relaxation target."""

    uid_full: str
    id_short: str
    status: str
    run_uid_full: str | None
    run_id_short: str | None
    prototype_uid_full: str | None
    target_uid_full: str | None
    target_kind: str | None
    relaxed_interface_uid: str | None
    final_energy_eV: float | None
    n_steps: int | None
    converged: bool | None
    max_force_eV_per_A: float | None
    backend: str | None
    optimizer_reported_converged: bool | None = None
    residual_satisfied: bool | None = None
    max_optimizer_residual: float | None = None
    termination_reason: str | None = None
    backend_identity: Mapping[str, Any] = field(default_factory=dict)
    settings: Mapping[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()
    failure: FailureRecord | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectRelaxationResult":
        followup = ProjectFollowupResult.from_item(item)
        if followup.kind != "relaxation_stage":
            raise ValueError(
                "ProjectRelaxationResult requires a relaxation_stage follow-up result."
            )
        payload = dict(followup.payload or {})
        artifact_refs = payload.get("artifact_refs") or []
        return cls(
            uid_full=followup.uid_full,
            id_short=followup.id_short,
            status=followup.status,
            run_uid_full=followup.run_uid_full,
            run_id_short=followup.run_id_short,
            prototype_uid_full=followup.prototype_uid_full,
            target_uid_full=followup.target_uid_full,
            target_kind=followup.target_kind,
            relaxed_interface_uid=(
                payload.get("relaxed_interface_uid")
                or payload.get("derived_interface_uid")
            ),
            final_energy_eV=(
                float(payload["final_energy_eV"])
                if payload.get("final_energy_eV") is not None
                else (
                    float(followup.best_energy)
                    if followup.best_energy is not None
                    else None
                )
            ),
            n_steps=(
                int(payload["n_steps"])
                if payload.get("n_steps") is not None
                else (int(followup.n_points) if followup.n_points is not None else None)
            ),
            converged=(
                bool(payload["converged"])
                if payload.get("converged") is not None
                else None
            ),
            optimizer_reported_converged=(
                bool(payload["optimizer_reported_converged"])
                if payload.get("optimizer_reported_converged") is not None
                else None
            ),
            residual_satisfied=(
                bool(payload["residual_satisfied"])
                if payload.get("residual_satisfied") is not None
                else None
            ),
            max_force_eV_per_A=(
                float(payload["max_force_eV_per_A"])
                if payload.get("max_force_eV_per_A") is not None
                else None
            ),
            max_optimizer_residual=(
                float(payload["max_optimizer_residual"])
                if payload.get("max_optimizer_residual") is not None
                else None
            ),
            termination_reason=(
                str(payload["convergence_certificate"].get("termination_reason"))
                if isinstance(payload.get("convergence_certificate"), Mapping)
                and payload["convergence_certificate"].get("termination_reason")
                is not None
                else None
            ),
            backend=(
                str(payload.get("relaxation_backend"))
                if payload.get("relaxation_backend") is not None
                else None
            ),
            backend_identity=dict(payload.get("backend_identity") or {}),
            settings=dict(payload.get("relaxation_settings") or {}),
            artifact_refs=tuple(str(value) for value in artifact_refs),
            failure=followup.failure,
            payload=payload,
            authority=followup.authority,
        )

    @property
    def succeeded(self) -> bool:
        return (
            self.failure is None
            and self.status in {"done", "completed"}
            and self.converged is not False
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "id_short": self.id_short,
            "status": self.status,
            "run_uid_full": self.run_uid_full,
            "run_id_short": self.run_id_short,
            "prototype_uid_full": self.prototype_uid_full,
            "target_uid_full": self.target_uid_full,
            "target_kind": self.target_kind,
            "relaxed_interface_uid": self.relaxed_interface_uid,
            "final_energy_eV": self.final_energy_eV,
            "n_steps": self.n_steps,
            "converged": self.converged,
            "optimizer_reported_converged": self.optimizer_reported_converged,
            "residual_satisfied": self.residual_satisfied,
            "max_force_eV_per_A": self.max_force_eV_per_A,
            "max_optimizer_residual": (self.max_optimizer_residual),
            "termination_reason": self.termination_reason,
            "backend": self.backend,
            "backend_identity": dict(self.backend_identity),
            "settings": dict(self.settings),
            "artifact_refs": list(self.artifact_refs),
            "failure": self.failure.to_dict() if self.failure else None,
            "payload": dict(self.payload),
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class ProjectInterface(_MappingRecord):
    """Represent a constructed or refined interface stored in a project.

    The record carries persistent identity, prototype lineage, construction stage,
    and normalized metadata. Persisted interfaces are database-backed; the
    authority field remains explicit so generic record handling cannot silently
    promote an in-memory projection into durable project state.
    """

    uid_full: str | None
    id_short: str | None
    label: str | None
    prototype_uid_full: str | None
    stage: str | None
    spec: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    authority: RecordAuthority = RecordAuthority.PROJECTION

    @classmethod
    def from_item(cls, item: Any) -> "ProjectInterface":
        row = _mapping(item)
        obj = row.get("_object")
        source = obj if obj is not None else item
        uid = (
            _get(source, "uid_full")
            or row.get("project_interface_uid")
            or row.get("interface_uid")
        )
        sid = (
            _get(source, "id_short")
            or row.get("project_interface_id")
            or row.get("id_short")
        )
        prototype = _get(source, "prototype_uid_full") or row.get("prototype_uid_full")
        spec = dict(_get(source, "spec", default={}) or {})
        params = spec.get("params") if isinstance(spec.get("params"), Mapping) else {}
        stage = spec.get("stage") or row.get("stage")
        metadata = {k: v for k, v in row.items() if k != "_object"}
        for key in (
            "search_name",
            "source_followup_uid",
            "source_run_uid",
            "strain_target_metric",
            "registry_settings",
            "relaxation_backend",
            "relaxation_settings",
            "source_interface_uid",
        ):
            if metadata.get(key) is None and params.get(key) is not None:
                metadata[key] = params[key]
        return cls(
            uid_full=str(uid) if uid is not None else None,
            id_short=str(sid) if sid is not None else None,
            label=_get(source, "label")
            or row.get("label")
            or row.get("name")
            or row.get("interface_id"),
            prototype_uid_full=str(prototype) if prototype is not None else None,
            stage=stage,
            spec=spec,
            metadata=metadata,
            authority=record_authority(
                item,
                authoritative_keys=("project_interface_uid", "interface_uid"),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "label": self.label,
                "prototype_uid_full": self.prototype_uid_full,
                "stage": self.stage,
                "spec": dict(self.spec),
                "authority": self.authority.value,
            }
        )
        return row


@dataclass(frozen=True)
class ProjectEnergyResult(_MappingRecord):
    """Typed authoritative raw total-energy result for one target."""

    uid_full: str | None
    id_short: str | None
    status: str
    run_uid_full: str | None
    run_id_short: str | None
    prototype_uid_full: str | None
    target_uid_full: str | None
    target_kind: str | None
    quantity: str
    energy_eV: float | None
    backend: str | None
    backend_identity: Mapping[str, Any] = field(default_factory=dict)
    settings: Mapping[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()
    failure: FailureRecord | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    authority: RecordAuthority = RecordAuthority.PROJECTION

    @classmethod
    def from_item(cls, item: Any) -> "ProjectEnergyResult":
        followup = ProjectFollowupResult.from_item(item)
        if followup.kind != "energy_stage":
            raise ValueError(
                "ProjectEnergyResult requires an energy_stage follow-up result."
            )
        payload = dict(followup.payload or {})
        backend = dict(payload["backend"])
        return cls(
            uid_full=followup.uid_full,
            id_short=followup.id_short,
            status=followup.status,
            run_uid_full=followup.run_uid_full,
            run_id_short=followup.run_id_short,
            prototype_uid_full=followup.prototype_uid_full,
            target_uid_full=followup.target_uid_full,
            target_kind=followup.target_kind,
            quantity=str(payload["quantity"]),
            energy_eV=(
                float(payload["energy_eV"])
                if payload.get("energy_eV") is not None
                else None
            ),
            backend=str(backend["name"]),
            backend_identity=dict(backend["identity"]),
            settings=dict(backend["settings"]),
            artifact_refs=tuple(
                str(value) for value in payload.get("artifact_refs", [])
            ),
            failure=followup.failure,
            payload=payload,
            metadata=followup.to_dict(),
            authority=followup.authority,
        )

    @property
    def energy(self) -> float | None:
        return self.energy_eV

    @property
    def units(self) -> str:
        return "eV"

    @property
    def succeeded(self) -> bool:
        return self.failure is None and self.status in {"done", "completed"}

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "status": self.status,
                "run_uid_full": self.run_uid_full,
                "run_id_short": self.run_id_short,
                "prototype_uid_full": self.prototype_uid_full,
                "target_uid_full": self.target_uid_full,
                "target_kind": self.target_kind,
                "quantity": self.quantity,
                "energy_eV": self.energy_eV,
                "energy": self.energy_eV,
                "units": self.units,
                "backend": self.backend,
                "backend_identity": dict(self.backend_identity),
                "settings": dict(self.settings),
                "artifact_refs": list(self.artifact_refs),
                "failure": self.failure.to_dict() if self.failure else None,
                "payload": dict(self.payload),
                "authority": self.authority.value,
            }
        )
        return row


@dataclass(frozen=True)
class ProjectReferenceEnergyResult(_MappingRecord):
    """Typed authoritative reference energy for one interface side."""

    uid_full: str
    id_short: str
    status: str
    run_uid_full: str | None
    run_id_short: str | None
    prototype_uid_full: str | None
    target_uid_full: str | None
    reference_uid_full: str | None
    reference_kind: str
    side: str
    formula_id: str
    energy_eV: float | None
    energy_eV_per_formula_unit: float | None
    reference_formula_units: int | None
    interface_formula_units: int | None
    source_bulk_uid_full: str | None
    source_slab_uid_full: str | None
    structure_fingerprint: str | None
    backend: str | None
    backend_identity: Mapping[str, Any] = field(default_factory=dict)
    settings: Mapping[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[str, ...] = ()
    failure: FailureRecord | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectReferenceEnergyResult":
        followup = ProjectFollowupResult.from_item(item)
        if followup.kind != "reference_energy":
            raise ValueError(
                "ProjectReferenceEnergyResult requires a reference_energy follow-up."
            )
        payload = dict(followup.payload or {})
        reference = dict(payload["reference"])
        reference_metadata = dict(reference["metadata"])
        energy = dict(payload.get("energy") or {})
        backend = dict(payload["backend"])
        return cls(
            uid_full=followup.uid_full,
            id_short=followup.id_short,
            status=followup.status,
            run_uid_full=followup.run_uid_full,
            run_id_short=followup.run_id_short,
            prototype_uid_full=followup.prototype_uid_full,
            target_uid_full=followup.target_uid_full,
            reference_uid_full=reference.get("uid_full"),
            reference_kind=str(reference["kind"]),
            side=str(reference["side"]),
            formula_id=str(reference["formula_id"]),
            energy_eV=(
                float(energy["total_eV"])
                if energy.get("total_eV") is not None
                else None
            ),
            energy_eV_per_formula_unit=(
                float(energy["per_formula_unit_eV"])
                if energy.get("per_formula_unit_eV") is not None
                else None
            ),
            reference_formula_units=(
                int(reference_metadata["reference_formula_units"])
                if reference_metadata.get("reference_formula_units") is not None
                else None
            ),
            interface_formula_units=(
                int(reference_metadata["interface_formula_units"])
                if reference_metadata.get("interface_formula_units") is not None
                else None
            ),
            source_bulk_uid_full=reference_metadata.get("source_bulk_uid_full"),
            source_slab_uid_full=reference_metadata.get("source_slab_uid_full"),
            structure_fingerprint=reference_metadata.get("structure_fingerprint"),
            backend=str(backend["name"]),
            backend_identity=dict(backend["identity"]),
            settings=dict(backend["settings"]),
            artifact_refs=tuple(
                str(value) for value in payload.get("artifact_refs", [])
            ),
            failure=followup.failure,
            payload=payload,
            authority=followup.authority,
        )

    @property
    def source_interface_uid_full(self) -> str | None:
        """Authoritative interface whose strain state defines this reference."""
        return self.target_uid_full

    @property
    def succeeded(self) -> bool:
        return self.failure is None and self.status in {"done", "completed"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "id_short": self.id_short,
            "status": self.status,
            "run_uid_full": self.run_uid_full,
            "run_id_short": self.run_id_short,
            "prototype_uid_full": self.prototype_uid_full,
            "target_uid_full": self.target_uid_full,
            "source_interface_uid_full": self.source_interface_uid_full,
            "reference_uid_full": self.reference_uid_full,
            "reference_kind": self.reference_kind,
            "side": self.side,
            "formula_id": self.formula_id,
            "energy_eV": self.energy_eV,
            "energy_eV_per_formula_unit": self.energy_eV_per_formula_unit,
            "reference_formula_units": self.reference_formula_units,
            "interface_formula_units": self.interface_formula_units,
            "source_bulk_uid_full": self.source_bulk_uid_full,
            "source_slab_uid_full": self.source_slab_uid_full,
            "structure_fingerprint": self.structure_fingerprint,
            "backend": self.backend,
            "backend_identity": dict(self.backend_identity),
            "settings": dict(self.settings),
            "artifact_refs": list(self.artifact_refs),
            "failure": self.failure.to_dict() if self.failure else None,
            "payload": dict(self.payload),
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class ProjectThermodynamicResult(_MappingRecord):
    """Typed authoritative derived interfacial thermodynamic quantity."""

    uid_full: str
    id_short: str
    status: str
    run_uid_full: str | None
    run_id_short: str | None
    prototype_uid_full: str | None
    target_uid_full: str | None
    target_kind: str | None
    raw_energy_followup_uid: str | None
    quantity: str | None
    formula_id: str | None
    value_eV_per_A2: float | None
    value_J_per_m2: float | None
    normalization_area_A2: float | None
    n_interfaces: int | None
    convention: Mapping[str, Any] = field(default_factory=dict)
    references: Mapping[str, Any] = field(default_factory=dict)
    reference_source: Mapping[str, Any] = field(default_factory=dict)
    components: Mapping[str, Any] = field(default_factory=dict)
    units: Mapping[str, Any] = field(default_factory=dict)
    normalization_area_source_status: str | None = None
    calculator_compatibility: Mapping[str, Any] = field(default_factory=dict)
    failure: FailureRecord | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectThermodynamicResult":
        followup = ProjectFollowupResult.from_item(item)
        if followup.kind != "thermodynamic_quantity":
            raise ValueError(
                "ProjectThermodynamicResult requires a thermodynamic_quantity follow-up."
            )
        payload = dict(followup.payload or {})
        source = dict(payload["source"])
        quantity = dict(payload.get("quantity") or {})
        normalization = dict(payload.get("normalization") or {})
        return cls(
            uid_full=followup.uid_full,
            id_short=followup.id_short,
            status=followup.status,
            run_uid_full=followup.run_uid_full,
            run_id_short=followup.run_id_short,
            prototype_uid_full=followup.prototype_uid_full,
            target_uid_full=followup.target_uid_full,
            target_kind=followup.target_kind,
            raw_energy_followup_uid=source.get("raw_energy_followup_uid"),
            quantity=quantity.get("name"),
            formula_id=quantity.get("formula_id"),
            value_eV_per_A2=(
                float(quantity["value_eV_per_A2"])
                if quantity.get("value_eV_per_A2") is not None
                else None
            ),
            value_J_per_m2=(
                float(quantity["value_J_per_m2"])
                if quantity.get("value_J_per_m2") is not None
                else None
            ),
            normalization_area_A2=(
                float(normalization["area_A2"])
                if normalization.get("area_A2") is not None
                else None
            ),
            n_interfaces=(
                int(normalization["n_interfaces"])
                if normalization.get("n_interfaces") is not None
                else None
            ),
            convention=dict(payload.get("convention") or {}),
            references=dict(payload.get("references") or {}),
            reference_source={
                "mode": source.get("reference_mode"),
                "reference_run_uid_full": source.get("reference_run_uid_full"),
            },
            components=dict(payload.get("components") or {}),
            units=dict(payload.get("units") or {}),
            normalization_area_source_status=normalization.get(
                "area_source_status",
                payload.get("normalization_area_source_status"),
            ),
            calculator_compatibility=dict(
                payload.get("calculator_compatibility") or {}
            ),
            failure=followup.failure,
            payload=payload,
            authority=followup.authority,
        )

    @property
    def succeeded(self) -> bool:
        return self.failure is None and self.status in {"done", "completed"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "id_short": self.id_short,
            "status": self.status,
            "run_uid_full": self.run_uid_full,
            "run_id_short": self.run_id_short,
            "prototype_uid_full": self.prototype_uid_full,
            "target_uid_full": self.target_uid_full,
            "target_kind": self.target_kind,
            "raw_energy_followup_uid": self.raw_energy_followup_uid,
            "quantity": self.quantity,
            "formula_id": self.formula_id,
            "value_eV_per_A2": self.value_eV_per_A2,
            "value_J_per_m2": self.value_J_per_m2,
            "normalization_area_A2": self.normalization_area_A2,
            "n_interfaces": self.n_interfaces,
            "convention": dict(self.convention),
            "references": dict(self.references),
            "reference_source": dict(self.reference_source),
            "components": dict(self.components),
            "units": dict(self.units),
            "normalization_area_source_status": (self.normalization_area_source_status),
            "calculator_compatibility": dict(self.calculator_compatibility),
            "failure": self.failure.to_dict() if self.failure else None,
            "payload": dict(self.payload),
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class ProjectDataset(_MappingRecord):
    """Represent an authoritative dataset bound to an open project.

    The immutable record describes dataset identity and persisted settings. When
    retrieved through a ``Project``, it also provides project-bound methods for
    membership, validation, deterministic splits, tabular views, and atomic export.
    Detached records remain readable but cannot perform project mutations.
    """

    _default_view = "learning"
    _view_specs = DATASET_ITEM_VIEW_SPECS

    uid_full: str | None
    id_short: str | None
    name: str | None
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    authority: RecordAuthority = RecordAuthority.PROJECTION
    _project: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_item(cls, item: Any, *, project: Any = None) -> "ProjectDataset":
        row = _mapping(item)
        nested = dict(_get(item, "metadata", default={}) or {})
        metadata = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "_object",
                "uid_full",
                "id_short",
                "name",
                "description",
                "created_at",
                "metadata",
            }
        }
        metadata.update(nested)
        return cls(
            uid_full=_get(item, "uid_full") or row.get("project_dataset_uid"),
            id_short=_get(item, "id_short") or row.get("project_dataset_id"),
            name=_get(item, "name") or row.get("dataset_name") or row.get("dataset_id"),
            description=_get(item, "description"),
            metadata=metadata,
            created_at=_get(item, "created_at"),
            authority=record_authority(
                item, authoritative_keys=("project_dataset_uid",)
            ),
            _project=project,
        )

    @property
    def schema_version(self) -> str | None:
        value = self.metadata.get("schema_version")
        return str(value) if value is not None else None

    @property
    def settings(self) -> Mapping[str, Any]:
        value = self.metadata.get("settings")
        return dict(value) if isinstance(value, Mapping) else {}

    def _require_project(self) -> Any:
        if self._project is None:
            raise RuntimeError(
                "This dataset record is not bound to an open Project. Retrieve it "
                "through project.dataset(...) before mutating, validating, or exporting it."
            )
        return self._project

    def items(self):
        """Return authoritative membership records for this dataset.

        Returns:
            (DatasetItemCollection): Authoritative membership records bound to the
                same open project.

        Raises:
            RuntimeError: If this record is detached from an open project.
        """
        return self._require_project().dataset_items(
            self.uid_full or self.id_short or self.name
        )

    def add(self, items: Any):
        """Append sources under the dataset's persisted membership policy.

        Args:
            items: Supported project records, identifiers, or collection inputs.

        Returns:
            (DatasetItemCollection): The authoritative membership records created by
                the update.

        Raises:
            RuntimeError: If this record is detached from an open project.
        """
        return self._require_project().add_dataset_items(
            self.uid_full or self.id_short or self.name,
            items,
        )

    def validate(self):
        """Validate persisted membership against the dataset contract.

        Returns:
            (DatasetValidationReport): Structured validation of the persisted
                membership, schema, and provenance.

        Raises:
            RuntimeError: If this record is detached from an open project.
        """
        return self._require_project().validate_dataset(
            self.uid_full or self.id_short or self.name
        )

    @property
    def feature_declarations(self):
        from calm.public.inputs.settings import DatasetSettings

        return DatasetSettings(**dict(self.settings)).features

    @property
    def target_declarations(self):
        from calm.public.inputs.settings import DatasetSettings

        return DatasetSettings(**dict(self.settings)).targets

    @property
    def grouping_fields(self) -> tuple[str, ...]:
        from calm.public.inputs.settings import DatasetSettings

        return DatasetSettings(**dict(self.settings)).group_by

    @property
    def split_settings(self):
        from calm.public.inputs.settings import DatasetSettings

        return DatasetSettings(**dict(self.settings)).split

    def validate_ml(self, *, check_structures: bool = True):
        from calm.public.records.dataset_learning import validate_ml_readiness

        return validate_ml_readiness(
            self._require_project(),
            self,
            check_structures=check_structures,
        )

    def split(self, name: str):
        return self.items().split(name)

    def groups(self):
        return self.items().groups()

    @classmethod
    def available_views(cls) -> tuple[str, ...]:
        """Return canonical dataset-item views available through this dataset."""

        return tuple(spec.name for spec in cls._view_specs)

    def to_rows(self, *, view: str = "learning") -> list[dict[str, Any]]:
        """Return one named dataset-item projection."""

        return self.items().to_rows(view=view)

    def to_table(
        self,
        *,
        view: str = "learning",
        title: str = "Dataset items",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        max_rows: int = 50,
        max_width: int = 120,
        max_col_width: int = 40,
        sort_by: str | None = None,
        descending: bool = False,
        file: TextIO | None = None,
    ):
        """Return a deferred table for one named dataset-item projection."""

        return self.items().to_table(
            view=view,
            title=title,
            include=include,
            exclude=exclude,
            max_rows=max_rows,
            max_width=max_width,
            max_col_width=max_col_width,
            sort_by=sort_by,
            descending=descending,
            file=file,
        )

    def to_dataframe(self, *, view: str = "learning"):
        """Return a dataframe using the same ordered dataset-item schema."""

        return self.items().to_dataframe(view=view)

    def write_table(
        self,
        path: Any,
        *,
        view: str = "learning",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        """Write one named dataset-item projection to CSV."""

        self.items().write_table(
            path,
            view=view,
            include=include,
            exclude=exclude,
        )

    def export(self, destination: Any, **kwargs):
        """Validate and atomically export the dataset bundle.

        Args:
            destination: Target directory for the export bundle.
            **kwargs (Any): Supported project export options forwarded to
                ``Project.export_dataset()``.

        Returns:
            (DatasetExportResult): The completed bundle, manifest, files, and
                checksums.

        Raises:
            RuntimeError: If this record is detached from an open project.
        """
        return self._require_project().export_dataset(
            self.uid_full or self.id_short or self.name,
            destination,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "name": self.name,
                "description": self.description,
                "created_at": self.created_at,
                "authority": self.authority.value,
            }
        )
        return row


@dataclass(frozen=True)
class ProjectDatasetItem(_MappingRecord):
    """Represent one authoritative dataset membership record.

    Each item links a dataset index to canonical source metadata, artifact
    references, declared feature and target values, leakage-group identity, and an
    optional deterministic split assignment.
    """

    uid_full: str | None
    id_short: str | None
    dataset_uid_full: str | None
    index: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    artifact_refs: tuple[Any, ...] = ()
    created_at: str | None = None
    authority: RecordAuthority = RecordAuthority.PROJECTION

    @classmethod
    def from_item(cls, item: Any) -> "ProjectDatasetItem":
        row = _mapping(item)
        refs = _get(item, "artifact_refs", default=[]) or []
        if isinstance(refs, (str, bytes)):
            refs = [refs]
        nested_metadata = dict(_get(item, "metadata", default={}) or {})
        metadata = {key: value for key, value in row.items() if key != "_object"}
        metadata.update(nested_metadata)
        uid = (
            _get(item, "uid_full")
            or row.get("project_dataset_item_uid")
            or row.get("dataset_item_uid")
        )
        id_short = (
            _get(item, "id_short")
            or row.get("project_dataset_item_id")
            or row.get("dataset_item_id")
        )
        dataset_uid = (
            _get(item, "dataset_uid_full")
            or row.get("project_dataset_uid")
            or row.get("dataset_uid")
        )
        index = _get(item, "index")
        if index is None:
            index = row.get("dataset_index")
        return cls(
            uid_full=str(uid) if uid is not None else None,
            id_short=str(id_short) if id_short is not None else None,
            dataset_uid_full=(str(dataset_uid) if dataset_uid is not None else None),
            index=int(index) if index is not None else None,
            metadata=metadata,
            artifact_refs=tuple(
                dict(ref) if isinstance(ref, Mapping) else str(ref) for ref in refs
            ),
            created_at=_get(item, "created_at"),
            authority=record_authority(
                item,
                authoritative_keys=(
                    "project_dataset_item_uid",
                    "dataset_item_uid",
                ),
            ),
        )

    @property
    def features(self) -> Mapping[str, Any]:
        value = self.metadata.get("features")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def targets(self) -> Mapping[str, Any]:
        value = self.metadata.get("targets")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def group_id(self) -> str | None:
        value = self.metadata.get("group_id")
        return str(value) if value is not None else None

    @property
    def split_name(self) -> str | None:
        value = self.metadata.get("split")
        return str(value) if value is not None else None

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "dataset_uid_full": self.dataset_uid_full,
                "index": self.index,
                "dataset_index": self.index,
                "artifact_refs": [
                    dict(ref) if isinstance(ref, Mapping) else str(ref)
                    for ref in self.artifact_refs
                ],
                "created_at": self.created_at,
                "authority": self.authority.value,
            }
        )
        if self.uid_full is not None:
            row.setdefault("project_dataset_item_uid", self.uid_full)
        if self.id_short is not None:
            row.setdefault("project_dataset_item_id", self.id_short)
        return row


@dataclass(frozen=True)
class ProjectCampaign(_MappingRecord):
    """Represent a persisted campaign declaration bound to a project.

    The record retains campaign identity, typed specification, metadata, and
    creation time. Project-bound instances can enumerate deterministic runs or
    execute and resume the campaign; detached instances are read-only.
    """

    uid_full: str | None
    id_short: str | None
    name: str | None
    spec: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    authority: RecordAuthority = RecordAuthority.PROJECTION
    _project: Any = field(default=None, repr=False, compare=False)

    @classmethod
    def from_item(cls, item: Any, *, project: Any = None) -> "ProjectCampaign":
        row = _mapping(item)
        nested = dict(_get(item, "metadata", default={}) or {})
        canonical = {
            "_object",
            "uid_full",
            "id_short",
            "campaign_id",
            "id",
            "name",
            "spec",
            "metadata",
            "created_at",
            "authority",
            "_authority",
        }
        metadata = {
            key: value
            for key, value in row.items()
            if key not in canonical and not key.startswith("_")
        }
        metadata.update(
            {
                key: value
                for key, value in nested.items()
                if key not in canonical and not key.startswith("_")
            }
        )
        return cls(
            uid_full=_get(item, "uid_full"),
            id_short=_get(item, "id_short"),
            name=_get(item, "name"),
            spec=dict(_get(item, "spec", default={}) or {}),
            metadata=metadata,
            created_at=_get(item, "created_at"),
            authority=record_authority(item),
            _project=project,
        )

    def _require_project(self) -> Any:
        if self._project is None:
            raise RuntimeError(
                "This campaign record is not bound to an open Project. Retrieve it "
                "through project.campaign(...) before running it."
            )
        return self._project

    def runs(self):
        """Return deterministic persisted runs for this campaign.

        Returns:
            (CampaignRunCollection): Persisted runs selected by the campaign's
                durable identifier.

        Raises:
            RuntimeError: If this record is detached from an open project.
        """
        return (
            self._require_project()
            .campaigns()
            .runs(self.uid_full or self.id_short or self.name)
        )

    def run(self, **kwargs):
        """Execute or resume this project-bound campaign.

        Keyword arguments are forwarded to ``Project.run_campaign()``.

        Args:
            **kwargs (Any): Supported campaign execution options forwarded to
                ``Project.run_campaign()``.

        Returns:
            (CampaignWorkflowResult): The typed synchronous campaign result.

        Raises:
            RuntimeError: If this record is detached from an open project.
        """
        return self._require_project().run_campaign(
            self.uid_full or self.id_short or self.name,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "name": self.name,
                "spec": dict(self.spec),
                "created_at": self.created_at,
                "authority": self.authority.value,
            }
        )
        return row


@dataclass(frozen=True)
class ProjectCampaignRun(_MappingRecord):
    """Represent one persisted execution of a campaign.

    The record associates a campaign with its run-specification hash, backend
    identity, status, timestamps, and additional persisted metadata.
    """

    uid_full: str | None
    id_short: str | None
    campaign_uid_full: str | None
    run_spec_hash: str | None = None
    backend_id: str | None = None
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    authority: RecordAuthority = RecordAuthority.PROJECTION

    @classmethod
    def from_item(cls, item: Any) -> "ProjectCampaignRun":
        row = _mapping(item)
        return cls(
            uid_full=_get(item, "uid_full"),
            id_short=_get(item, "id_short"),
            campaign_uid_full=_get(item, "campaign_uid_full"),
            run_spec_hash=_get(item, "run_spec_hash"),
            backend_id=_get(item, "backend_id"),
            status=_get(item, "status"),
            started_at=_get(item, "started_at"),
            finished_at=_get(item, "finished_at"),
            metadata={
                key: value for key, value in row.items() if not key.startswith("_")
            },
            authority=record_authority(item),
        )

    def to_dict(self) -> dict[str, Any]:
        row = dict(self.metadata)
        row.update(
            {
                "uid_full": self.uid_full,
                "id_short": self.id_short,
                "campaign_uid_full": self.campaign_uid_full,
                "run_spec_hash": self.run_spec_hash,
                "backend_id": self.backend_id,
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "authority": self.authority.value,
            }
        )
        return row


@dataclass(frozen=True)
class ProjectArtifact(_MappingRecord):
    """Represent an authoritative artifact produced by a workflow run.

    The record stores artifact identity, parent run, kind, project-relative URI,
    metadata, and creation time. The URI identifies persisted project content; it
    is not guaranteed to be a portable external URL.
    """

    uid_full: str
    id_short: str
    run_uid_full: str
    kind: str
    uri: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectArtifact":
        return cls(
            uid_full=str(_get(item, "uid_full", default="") or ""),
            id_short=str(_get(item, "id_short", default="") or ""),
            run_uid_full=str(_get(item, "run_uid_full", default="") or ""),
            kind=str(_get(item, "kind", default="") or ""),
            uri=str(_get(item, "uri", default="") or ""),
            metadata=dict(_get(item, "metadata", default={}) or {}),
            created_at=_get(item, "created_at"),
            authority=record_authority(item),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "id_short": self.id_short,
            "run_uid_full": self.run_uid_full,
            "kind": self.kind,
            "uri": self.uri,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class ProjectEdge(_MappingRecord):
    """Represent one authoritative directed provenance edge.

    ``src_uid_full`` and ``dst_uid_full`` identify persisted entities, ``kind``
    defines the lineage relationship, and ``payload`` carries edge-specific
    metadata.
    """

    uid_full: str
    src_uid_full: str
    dst_uid_full: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    @classmethod
    def from_item(cls, item: Any) -> "ProjectEdge":
        return cls(
            uid_full=str(_get(item, "uid_full", default="") or ""),
            src_uid_full=str(_get(item, "src_uid_full", "src", default="") or ""),
            dst_uid_full=str(_get(item, "dst_uid_full", "dst", default="") or ""),
            kind=str(_get(item, "kind", default="") or ""),
            payload=dict(_get(item, "payload", default={}) or {}),
            created_at=_get(item, "created_at"),
            authority=record_authority(item),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "src_uid_full": self.src_uid_full,
            "dst_uid_full": self.dst_uid_full,
            "kind": self.kind,
            "payload": dict(self.payload),
            "created_at": self.created_at,
            "authority": self.authority.value,
        }


def uid_kind(uid_full: str) -> str:
    prefix = str(uid_full).split(":", 1)[0]
    return {
        "bulk": "material",
        "b": "material",
        "slab": "surface",
        "s": "surface",
        "proto": "candidate",
        "p": "candidate",
        "interface": "interface",
        "i": "interface",
        "run": "run",
        "followup": "followup_result",
        "f": "followup_result",
        "artifact": "artifact",
        "a": "artifact",
        "dataset": "dataset",
        "d": "dataset",
        "dataset_item": "dataset_item",
        "campaign": "campaign",
        "campaign_run": "campaign_run",
        "calc": "calculator",
    }.get(prefix, "unknown")


@dataclass(frozen=True)
class LineageNode(_MappingRecord):
    """Represent one typed node in a persisted provenance subgraph.

    The node carries the durable entity UID, normalized entity kind, and optional
    short identifier and label used for user-facing graph inspection.
    """

    uid_full: str
    kind: str
    id_short: str | None = None
    label: str | None = None
    authority: RecordAuthority = RecordAuthority.AUTHORITATIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid_full": self.uid_full,
            "kind": self.kind,
            "id_short": self.id_short,
            "label": self.label,
            "authority": self.authority.value,
        }


@dataclass(frozen=True)
class LineageGraph:
    """Authoritative persisted provenance subgraph rooted at one entity."""

    root_uid_full: str
    nodes: tuple[LineageNode, ...]
    edges: tuple[ProjectEdge, ...]

    def node(self, uid_full: str) -> LineageNode:
        for node in self.nodes:
            if node.uid_full == uid_full:
                return node
        raise KeyError(f"Lineage node not found: {uid_full}")

    def upstream(self, uid_full: str | None = None) -> tuple[LineageNode, ...]:
        target = uid_full or self.root_uid_full
        ids = {edge.src_uid_full for edge in self.edges if edge.dst_uid_full == target}
        return tuple(node for node in self.nodes if node.uid_full in ids)

    def downstream(self, uid_full: str | None = None) -> tuple[LineageNode, ...]:
        source = uid_full or self.root_uid_full
        ids = {edge.dst_uid_full for edge in self.edges if edge.src_uid_full == source}
        return tuple(node for node in self.nodes if node.uid_full in ids)

    def to_rows(self) -> list[dict[str, Any]]:
        return [edge.to_dict() for edge in self.edges]
