"""Deterministic derivation of interfacial thermodynamic quantities."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any, Mapping, Sequence

from calm.interface.energy.contract import (
    EV_PER_A2_TO_J_PER_M2,
    UnsupportedReferenceWorkflowError,
    _finite_float,
    canonical_energy_formula,
    derive_thermodynamic_quantity,
)
from calm.project.domain.contracts.energy_result import (
    ENERGY_RESULT_VERSION,
    THERMODYNAMIC_RESULT_SCHEMA,
)
from ...domain.models import FollowupResult, Run
from ...ports.uow import UnitOfWork
from ..interface_prototype_payload import infer_interface_area_A2
from ..runs import RunsService
from .common import persisted_followup_uid
from .orch_helpers import finalize_run_state_and_refresh, persist_followups_with_edges


def _reference_calculator_compatibility(  # noqa: C901
    raw_payload: Mapping[str, Any],
    references: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify calculated-reference calculator provenance against the raw energy."""

    metadata = references.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    if metadata.get("compatibility_source") != "calculated_reference_workflow":
        return {
            "status": "manual_unverified",
            "reference_source": metadata.get("source", "manual"),
        }

    raw_backend_record = raw_payload.get("backend")
    if not isinstance(raw_backend_record, Mapping):
        raise ValueError("Raw interface energy is missing exact backend provenance.")
    raw_backend = raw_backend_record.get("name")
    raw_identity = raw_backend_record.get("identity")
    raw_settings = raw_backend_record.get("settings")
    expected_backend = metadata.get("energy_backend")
    expected_identity = metadata.get("backend_identity")
    expected_settings = metadata.get("energy_settings")
    if not raw_backend or not isinstance(raw_identity, Mapping) or not raw_identity:
        raise ValueError(
            "Raw interface energy is missing calculator provenance required to "
            "compare it with calculated references."
        )
    if (
        not expected_backend
        or not isinstance(expected_identity, Mapping)
        or not expected_identity
    ):
        raise ValueError("Calculated references are missing calculator provenance.")
    if str(raw_backend) != str(expected_backend):
        raise ValueError(
            "Raw interface and calculated reference energies use different backends."
        )
    if dict(raw_identity) != dict(expected_identity):
        raise ValueError(
            "Raw interface and calculated reference energies use different "
            "calculator identities."
        )
    if raw_settings is not None and not isinstance(raw_settings, Mapping):
        raise ValueError("Raw interface energy has invalid calculation settings.")
    if expected_settings is not None and not isinstance(expected_settings, Mapping):
        raise ValueError("Calculated references have invalid calculation settings.")
    if dict(raw_settings or {}) != dict(expected_settings or {}):
        raise ValueError(
            "Raw interface and calculated reference energies use different "
            "calculation settings."
        )
    raw_area = _finite_float(
        raw_payload.get("interface_area_A2"),
        name="The raw interface-energy area",
    )
    reference_area = _finite_float(
        metadata.get("reference_area_A2"),
        name="The calculated-reference area",
    )
    if (
        raw_area <= 0.0
        or reference_area <= 0.0
        or not isclose(
            raw_area,
            reference_area,
            rel_tol=1e-10,
            abs_tol=1e-10,
        )
    ):
        raise ValueError(
            "Raw interface and calculated reference energies use different "
            "normalization areas."
        )
    result = {
        "status": "verified",
        "raw": {
            "backend": str(raw_backend),
            "identity": dict(raw_identity),
            "settings": dict(raw_settings or {}),
            "interface_area_A2": raw_area,
        },
        "reference": {
            "backend": str(expected_backend),
            "identity": dict(expected_identity),
            "settings": dict(expected_settings or {}),
            "interface_area_A2": reference_area,
            "relaxation": None,
        },
    }
    if metadata.get("formula_id") == "work_of_adhesion_relaxed_surfaces":
        protocol = metadata.get("reference_protocol")
        relaxation = metadata.get("reference_relaxation")
        engine = metadata.get("reference_relaxation_engine")
        if (
            not protocol
            or not isinstance(relaxation, Mapping)
            or not isinstance(engine, Mapping)
        ):
            raise ValueError(
                "Relaxed surface references are missing relaxation-protocol "
                "or relaxation-engine provenance."
            )
        result["reference"]["relaxation"] = {
            "protocol": str(protocol),
            "settings": dict(relaxation),
            "engine": dict(engine),
            "source_interface_structure_fingerprint": metadata.get(
                "source_interface_structure_fingerprint"
            ),
        }
    return result


_REFERENCE_METADATA_OWNED_FIELDS = frozenset(
    {
        "compatibility_source",
        "energy_backend",
        "backend_identity",
        "energy_settings",
        "formula_id",
        "reference_area_A2",
        "reference_protocol",
        "reference_relaxation",
        "reference_relaxation_engine",
        "reference_result_uids",
        "reference_run_uid_full",
        "source",
        "source_interface_structure_fingerprint",
    }
)


def _persisted_reference_bundle(
    references: Mapping[str, Any],
    *,
    formula: str,
) -> dict[str, Any]:
    """Return the exact formula-specific reference state persisted in a result."""

    metadata_raw = references.get("metadata")
    if metadata_raw is None:
        metadata: dict[str, Any] = {}
    elif isinstance(metadata_raw, Mapping):
        metadata = dict(metadata_raw)
    else:
        raise TypeError("Thermodynamic reference metadata must be a mapping.")
    result_uids_raw = metadata.get("reference_result_uids")
    if result_uids_raw is None:
        result_uids: dict[str, Any] = {}
    elif isinstance(result_uids_raw, Mapping):
        result_uids = dict(result_uids_raw)
    else:
        raise TypeError("Calculated reference result_uids must be a mapping.")
    calculated = metadata.get(
        "compatibility_source"
    ) == "calculated_reference_workflow" or bool(result_uids)
    if formula == "interface_excess_strained_bulk":
        values = {
            "bulk_a_eV_per_formula_unit": references["bulk_a_eV_per_formula_unit"],
            "bulk_b_eV_per_formula_unit": references["bulk_b_eV_per_formula_unit"],
            "n_formula_units_a": references["n_formula_units_a"],
            "n_formula_units_b": references["n_formula_units_b"],
        }
    else:
        values = {
            "surface_a_total_energy_eV": references["surface_a_total_energy_eV"],
            "surface_b_total_energy_eV": references["surface_b_total_energy_eV"],
        }
    return {
        "status": "resolved",
        "source_kind": "calculated" if calculated else "manual",
        "result_uids": result_uids if calculated else {},
        "values": values,
        "metadata": {
            key: value
            for key, value in metadata.items()
            if key not in _REFERENCE_METADATA_OWNED_FIELDS
        },
    }


def _prototype_normalization_area(  # noqa: C901
    uow: Any,
    *,
    raw: FollowupResult,
    prototype: Any,
    area_source: str = "authoritative_interface_area",
) -> tuple[float, str]:
    """Resolve one explicit, auditable interface normalization area."""

    raw_payload = dict(getattr(raw, "payload", {}) or {})
    target_kind = raw.target_kind
    if str(target_kind or "") != "interface":
        raise ValueError(
            "Interfacial thermodynamic quantities require an interface "
            "raw-energy target."
        )

    authoritative_area: float | None = None
    if raw_payload.get("interface_area_A2") is not None:
        authoritative_area = _finite_float(
            raw_payload["interface_area_A2"],
            name="The authoritative raw-energy interface area",
        )
        if authoritative_area <= 0.0:
            raise ValueError(
                "The authoritative raw-energy interface area must be positive."
            )

    if area_source == "authoritative_interface_area":
        if authoritative_area is None:
            raise ValueError(
                "The raw interface-energy result does not contain an authoritative "
                "interface area. Re-evaluate the energy with the corrected workflow "
                "or explicitly request the legacy prototype-area convention."
            )
        return authoritative_area, "authoritative_interface_cell"

    if area_source != "prototype_interface_area":
        raise ValueError(f"Unsupported interface area source: {area_source!r}.")

    prototype_area = infer_interface_area_A2(prototype)
    if prototype_area is None:
        raise ValueError(
            "Prototype interface area is missing or non-positive; thermodynamic "
            "normalization requires an authoritative interface area."
        )

    repository = getattr(uow, "derived_interfaces", None)
    getter = getattr(repository, "get_by_uid_full", None)
    interface = getter(str(raw.target_uid_full or "")) if callable(getter) else None
    if interface is not None:
        params_raw = getattr(interface, "params", None)
        if not isinstance(params_raw, Mapping):
            raise TypeError("The source interface must expose exact current params.")
        params = dict(params_raw)
        relaxation = dict(params.get("relaxation_settings") or {})
        if bool(relaxation.get("relax_cell")):
            raise UnsupportedReferenceWorkflowError(
                "Prototype-area normalization is invalid after variable-cell interface "
                "relaxation. Use the authoritative interface-cell area instead."
            )

    prototype_area = float(prototype_area)
    if authoritative_area is not None:
        if not isclose(
            authoritative_area,
            prototype_area,
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ValueError(
                "The prototype area does not match the evaluated interface cell. "
                "Use area_source='authoritative_interface_area'."
            )
        return prototype_area, "verified_prototype_matches_interface"

    return prototype_area, "legacy_prototype_area_unverified"


@dataclass
class ThermodynamicStageResult:
    target_uid: str
    prototype_uid: str
    status: str
    quantity: str | None = None
    value_eV_per_A2: float | None = None
    value_J_per_m2: float | None = None
    run_uid: str | None = None
    followup_uid: str | None = None
    raw_energy_followup_uid: str | None = None
    reason: Any = None


class ThermodynamicOrchestrator:
    """Persist algebraic quantities derived from authoritative raw energies."""

    def __init__(self, uow: UnitOfWork) -> None:
        if hasattr(uow, "_depth") and getattr(uow, "_depth", 0) > 0:
            raise ValueError(
                "Do not construct ThermodynamicOrchestrator with an entered UnitOfWork."
            )
        self._uow = uow
        self._runs = RunsService(uow=uow)

    def _resolve_raw_results(
        self,
        identifiers: Sequence[str],
    ) -> list[FollowupResult]:
        rows: list[FollowupResult] = []
        with self._uow as uow:
            for identifier in identifiers:
                uid = uow.ids.resolve(str(identifier), expected_tag="f")
                row = uow.followups.get_by_uid_full(uid)
                if row is None:
                    raise KeyError(f"Raw energy result not found: {identifier!r}")
                if row.kind != "energy_stage":
                    raise ValueError(
                        f"Expected an energy_stage result, got {row.kind!r}."
                    )
                if str(row.status) not in {"done", "completed"}:
                    raise ValueError(
                        f"Raw energy result {identifier!r} is not completed."
                    )
                rows.append(row)
        return rows

    @staticmethod
    def _run_spec(
        raw_results: Sequence[FollowupResult],
        convention: Mapping[str, Any],
        references: Mapping[str, Any],
    ) -> dict[str, Any]:
        targets = sorted(
            [
                {
                    "raw_energy_followup_uid": row.uid_full,
                    "target_uid_full": row.target_uid_full,
                    "prototype_uid_full": row.prototype_uid_full,
                }
                for row in raw_results
            ],
            key=lambda item: (
                str(item["target_uid_full"] or ""),
                str(item["raw_energy_followup_uid"] or ""),
            ),
        )
        return {
            "kind": "thermodynamic_derivation",
            "targets": targets,
            "convention": dict(convention),
            "references": dict(references),
            "impl": "typed_persistent_v2",
        }

    @staticmethod
    def _references_for_target(
        references: Mapping[str, Any],
        target_uid_full: str,
    ) -> dict[str, Any]:
        if references.get("mode") != "by_target_uid":
            return dict(references)
        by_target = references.get("by_target_uid")
        if not isinstance(by_target, Mapping):
            raise ValueError(
                "Target-indexed references require a by_target_uid mapping."
            )
        value = by_target.get(str(target_uid_full))
        if not isinstance(value, Mapping):
            raise KeyError(
                f"No authoritative reference values were persisted for target "
                f"{target_uid_full!r}."
            )
        resolved = dict(value)
        if references.get("formula_id") is not None:
            resolved.setdefault("formula_id", references.get("formula_id"))
        return resolved

    def _existing(self, run_uid_full: str) -> dict[str, FollowupResult]:
        out: dict[str, FollowupResult] = {}
        with self._uow as uow:
            for row in uow.followups.list(
                run_uid_full=run_uid_full,
                kind="thermodynamic_quantity",
                limit=100000,
            ):
                if str(row.status) not in {"done", "completed"}:
                    continue
                payload = dict(row.payload or {})
                source = payload.get("source")
                if not isinstance(source, Mapping):
                    raise ValueError(
                        f"Persisted thermodynamic follow-up {row.uid_full!r} is "
                        "missing exact source identity."
                    )
                raw_uid = source.get("raw_energy_followup_uid")
                if not raw_uid:
                    raise ValueError(
                        f"Persisted thermodynamic follow-up {row.uid_full!r} is "
                        "missing raw_energy_followup_uid."
                    )
                out[str(raw_uid)] = row
        return out

    def run_stage(  # noqa: C901
        self,
        *,
        raw_energy_results: Sequence[str],
        convention: Mapping[str, Any],
        references: Mapping[str, Any],
        resume: bool = True,
        partial_resume: bool = True,
    ) -> tuple[Run, list[ThermodynamicStageResult]]:
        formula, quantity = canonical_energy_formula(str(convention["formula"]))
        declared_quantity = convention.get("quantity")
        if declared_quantity is not None and str(declared_quantity) != quantity:
            raise ValueError(
                "The thermodynamic convention quantity does not match its formula."
            )
        canonical_convention = dict(convention)
        canonical_convention["formula"] = formula
        canonical_convention["quantity"] = quantity
        canonical_convention.setdefault(
            "area_source",
            "authoritative_interface_area",
        )
        raw_rows = self._resolve_raw_results(raw_energy_results)
        spec = self._run_spec(raw_rows, canonical_convention, references)
        run = self._runs.create(run_type="thermodynamic_derivation", spec=spec)

        if resume and run.status == "done":
            return run, [
                ThermodynamicStageResult(
                    target_uid=str(row.target_uid_full or ""),
                    prototype_uid=row.prototype_uid_full,
                    status="skipped",
                    run_uid=run.uid_full,
                    raw_energy_followup_uid=row.uid_full,
                    reason="run_already_done",
                )
                for row in raw_rows
            ]

        self._runs.mark_running(
            run.uid_full,
            progress={"stage": "thermodynamics", "n_requested": len(raw_rows)},
        )
        existing = self._existing(run.uid_full) if partial_resume else {}
        stage_results: list[ThermodynamicStageResult] = []
        completed: list[FollowupResult] = []

        with self._uow as uow:
            for raw in raw_rows:
                raw_uid = raw.uid_full
                target_uid = str(raw.target_uid_full or "")
                prototype_uid = raw.prototype_uid_full
                if raw_uid in existing:
                    row = existing[raw_uid]
                    payload = dict(row.payload or {})
                    stage_results.append(
                        ThermodynamicStageResult(
                            target_uid=target_uid,
                            prototype_uid=prototype_uid,
                            status="skipped",
                            quantity=payload["quantity"]["name"],
                            value_eV_per_A2=payload["quantity"]["value_eV_per_A2"],
                            value_J_per_m2=payload["quantity"]["value_J_per_m2"],
                            run_uid=run.uid_full,
                            followup_uid=row.uid_full,
                            raw_energy_followup_uid=raw_uid,
                            reason="existing_followup",
                        )
                    )
                    continue

                followup_uid = persisted_followup_uid(
                    run_uid_full=run.uid_full,
                    prototype_uid_full=prototype_uid,
                    target_uid_full=target_uid,
                    target_kind=raw.target_kind,
                    kind="thermodynamic_quantity",
                    qualifiers={"raw_energy_followup_uid": raw_uid},
                )
                followup_id = uow.ids.ensure_short_id(uid_full=followup_uid, tag="f")
                target_references: dict[str, Any] | None = None
                persisted_references: dict[str, Any] = {
                    "status": "unresolved",
                    "reason": (
                        "thermodynamic_derivation_failed_before_reference_resolution"
                    ),
                }
                compatibility: dict[str, Any] = {
                    "status": "unresolved",
                    "reason": (
                        "thermodynamic_derivation_failed_before_calculator_"
                        "compatibility_verification"
                    ),
                }
                area_status: str | None = None
                try:
                    target_references = self._references_for_target(
                        references,
                        target_uid,
                    )
                    prototype = uow.prototypes.get_by_uid_full(prototype_uid)
                    if prototype is None:
                        raise KeyError(f"Prototype not found: {prototype_uid}")
                    area_A2, area_status = _prototype_normalization_area(
                        uow,
                        raw=raw,
                        prototype=prototype,
                        area_source=str(canonical_convention["area_source"]),
                    )
                    raw_payload = dict(raw.payload or {})
                    raw_quantity = raw_payload.get("quantity")
                    if raw_quantity not in {None, "total_energy"}:
                        raise ValueError(
                            "Thermodynamic derivation requires a raw total-energy "
                            "result."
                        )
                    reference_formula = target_references.get("formula_id")
                    if reference_formula is not None:
                        reference_formula, _ = canonical_energy_formula(
                            str(reference_formula)
                        )
                        if reference_formula != formula:
                            raise ValueError(
                                "Reference-energy formula does not match the requested "
                                "thermodynamic convention."
                            )
                    persisted_references = _persisted_reference_bundle(
                        target_references,
                        formula=formula,
                    )
                    compatibility = _reference_calculator_compatibility(
                        raw_payload,
                        target_references,
                    )
                    energy_eV = raw_payload["energy_eV"]
                    quantity, value, components = derive_thermodynamic_quantity(
                        interface_total_energy_eV=energy_eV,
                        area_A2=area_A2,
                        convention=canonical_convention,
                        references=target_references,
                    )
                except Exception as exc:
                    failure = {
                        "message": str(exc),
                        "exception_type": type(exc).__name__,
                        "module": type(exc).__module__,
                    }
                    failed = FollowupResult(
                        uid_full=followup_uid,
                        id_short=followup_id,
                        run_uid_full=run.uid_full,
                        run_id_short=run.id_short,
                        prototype_uid_full=prototype_uid,
                        prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid),
                        target_uid_full=target_uid,
                        target_kind=raw.target_kind,
                        kind="thermodynamic_quantity",
                        status="failed",
                        best_energy=None,
                        param1=None,
                        param2=None,
                        n_points=None,
                        payload={
                            "schema": THERMODYNAMIC_RESULT_SCHEMA,
                            "version": ENERGY_RESULT_VERSION,
                            "result_stage": "thermodynamic_failed",
                            "source": {
                                "raw_energy_followup_uid": raw_uid,
                                "reference_mode": references.get("mode", "static"),
                                "reference_run_uid_full": references.get(
                                    "reference_run_uid_full"
                                ),
                            },
                            "convention": dict(canonical_convention),
                            "references": dict(persisted_references),
                            "calculator_compatibility": dict(compatibility),
                            "normalization_area_source_status": area_status,
                            "failure": failure,
                        },
                    )
                    persist_followups_with_edges(uow=uow, followups=[failed])
                    stage_results.append(
                        ThermodynamicStageResult(
                            target_uid=target_uid,
                            prototype_uid=prototype_uid,
                            status="failed",
                            run_uid=run.uid_full,
                            followup_uid=followup_uid,
                            raw_energy_followup_uid=raw_uid,
                            reason=str(exc),
                        )
                    )
                    continue

                value_j = _finite_float(
                    float(value) * EV_PER_A2_TO_J_PER_M2,
                    name="The converted thermodynamic quantity",
                )
                payload = {
                    "schema": THERMODYNAMIC_RESULT_SCHEMA,
                    "version": ENERGY_RESULT_VERSION,
                    "result_stage": "thermodynamic_derived",
                    "source": {
                        "raw_energy_followup_uid": raw_uid,
                        "reference_mode": references.get("mode", "static"),
                        "reference_run_uid_full": references.get(
                            "reference_run_uid_full"
                        ),
                    },
                    "quantity": {
                        "name": quantity,
                        "formula_id": formula,
                        "value_eV_per_A2": float(value),
                        "value_J_per_m2": value_j,
                    },
                    "normalization": {
                        "area_A2": area_A2,
                        "area_source_status": area_status,
                        "n_interfaces": int(canonical_convention["n_interfaces"]),
                    },
                    "convention": dict(canonical_convention),
                    "references": dict(persisted_references),
                    "components": components,
                    "calculator_compatibility": dict(compatibility),
                    "units": {
                        "primary": "eV/angstrom^2",
                        "secondary": "J/m^2",
                    },
                }
                followup = FollowupResult(
                    uid_full=followup_uid,
                    id_short=followup_id,
                    run_uid_full=run.uid_full,
                    run_id_short=run.id_short,
                    prototype_uid_full=prototype_uid,
                    prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid),
                    target_uid_full=target_uid,
                    target_kind=raw.target_kind,
                    kind="thermodynamic_quantity",
                    status="done",
                    best_energy=float(value),
                    param1=area_A2,
                    param2=float(canonical_convention["n_interfaces"]),
                    n_points=1,
                    payload=payload,
                )
                completed.append(followup)
                stage_results.append(
                    ThermodynamicStageResult(
                        target_uid=target_uid,
                        prototype_uid=prototype_uid,
                        status="completed",
                        quantity=quantity,
                        value_eV_per_A2=float(value),
                        value_J_per_m2=value_j,
                        run_uid=run.uid_full,
                        followup_uid=followup_uid,
                        raw_energy_followup_uid=raw_uid,
                    )
                )

            if completed:
                persist_followups_with_edges(uow=uow, followups=completed)
                for row in completed:
                    payload_row = dict(row.payload or {})
                    source = dict(payload_row["source"])
                    raw_uid = source.get("raw_energy_followup_uid")
                    if not raw_uid:
                        raise ValueError(
                            f"Thermodynamic follow-up {row.uid_full!r} is missing "
                            "raw_energy_followup_uid."
                        )
                    uow.edges.add(
                        src_uid_full=str(raw_uid),
                        dst_uid_full=row.uid_full,
                        kind="energy_to_thermodynamic",
                        payload={"formula_id": payload_row["quantity"]["formula_id"]},
                    )
                    references_row = dict(payload_row["references"])
                    reference_result_uids = dict(
                        references_row.get("result_uids") or {}
                    )
                    for reference_kind, reference_uid in sorted(
                        reference_result_uids.items()
                    ):
                        uow.edges.add(
                            src_uid_full=str(reference_uid),
                            dst_uid_full=row.uid_full,
                            kind="reference_to_thermodynamic",
                            payload={
                                "formula_id": payload_row["quantity"]["formula_id"],
                                "reference_kind": str(reference_kind),
                            },
                        )

        run = finalize_run_state_and_refresh(
            self._runs,
            run,
            stage_results,
            n_requested=len(raw_rows),
        )
        return run, stage_results
