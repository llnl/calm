"""Authoritative raw total-energy orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from calm.interface.energy.contract import _finite_float, _positive_integer
from calm.project.domain.contracts.energy_result import (
    ENERGY_RESULT_VERSION,
    RAW_ENERGY_RESULT_SCHEMA,
)
from ...domain.models import FollowupResult, Run
from ...ports.uow import UnitOfWork
from ..runs import RunsService
from .common import persisted_followup_uid, resolve_followup_targets_as_results
from .energy_backends import DeterministicEnergyBackend
from .orch_helpers import (
    finalize_run_state_and_refresh,
    persist_artifact_payloads,
    persist_followups_with_edges,
)


@dataclass
class EnergyStageResult:
    target_uid: str
    target_kind: str
    prototype_uid: str
    status: str
    reason: Any = None
    run_uid: Any = None
    followup_uid: Any = None
    energy: Any = None
    energy_units: str | None = None
    artifact_refs: Any = None


def _interface_area_A2_from_atoms(atoms: Any) -> float:
    """Return the finite area spanned by the first two row cell vectors."""

    import numpy as np

    cell = np.asarray(atoms.get_cell(), dtype=float)
    if cell.shape != (3, 3) or not np.all(np.isfinite(cell)):
        raise ValueError("Interface atoms must have one finite 3x3 cell.")
    area = float(np.linalg.norm(np.cross(cell[0], cell[1])))
    if not np.isfinite(area) or area <= 0.0:
        raise ValueError("The authoritative interface cell area must be positive.")
    return area


class EnergyOrchestrator:
    """Run synchronous, persistent raw total-energy calculations."""

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        target_atoms_loader: Any | None = None,
        artifacts: Any | None = None,
    ) -> None:
        if getattr(uow, "_depth", 0):
            raise ValueError(
                "Do not construct EnergyOrchestrator with an entered UnitOfWork; "
                "pass a fresh UnitOfWork."
            )
        self._uow = uow
        self._runs = RunsService(uow=uow)
        self._backend = DeterministicEnergyBackend()
        self._backend_name = "deterministic"
        self._target_atoms_loader = target_atoms_loader
        self._artifacts = artifacts

    def with_backend(self, backend: Any) -> "EnergyOrchestrator":
        self._backend = backend
        name = (
            getattr(backend, "name", None)
            or getattr(backend, "__name__", None)
            or type(backend).__name__
        )
        self._backend_name = str(name).strip().lower()
        return self

    def _backend_identity(
        self,
        targets: list[dict[str, str]],
    ) -> dict[str, Any]:
        identity = getattr(self._backend, "identity", None)
        if callable(identity):
            value = identity(targets=targets, uow=self._uow)
            if not isinstance(value, Mapping):
                raise TypeError("Energy backend identity() must return a mapping.")
            return dict(value)
        return {
            "name": self._backend_name,
            "class": (
                f"{type(self._backend).__module__}.{type(self._backend).__qualname__}"
            ),
        }

    def _create_run_spec(
        self,
        targets: list[dict[str, str]],
        calculation: Mapping[str, Any],
        backend_identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        ordered_targets = sorted(
            (dict(target) for target in targets),
            key=lambda row: (
                str(row.get("target_uid_full") or ""),
                str(row.get("prototype_uid_full") or ""),
            ),
        )
        return {
            "kind": "energy_stage",
            "targets": ordered_targets,
            "backend": dict(backend_identity),
            "calculation": dict(calculation),
            "impl": "typed_persistent_v2",
        }

    def _existing_followups(
        self,
        *,
        run_uid_full: str,
    ) -> dict[tuple[str, str], FollowupResult]:
        out: dict[tuple[str, str], FollowupResult] = {}
        with self._uow as uow:
            rows = uow.followups.list(
                run_uid_full=run_uid_full,
                kind="energy_stage",
                limit=100000,
            )
            for row in rows:
                if str(row.status) not in {"done", "completed"}:
                    continue
                target_uid = row.target_uid_full
                if not row.prototype_uid_full or not target_uid:
                    raise ValueError(
                        f"Persisted energy follow-up {row.uid_full!r} is missing "
                        "prototype or target identity."
                    )
                out[(row.prototype_uid_full, str(target_uid))] = row
        return out

    def _load_target_atoms(self, target_uid_full: str, target_kind: str) -> Any | None:
        if target_kind != "interface":
            return None
        if not callable(self._target_atoms_loader):
            raise RuntimeError(
                "Interface energy targets require an authoritative atoms loader."
            )
        return self._target_atoms_loader(target_uid_full)

    def run_stage(  # noqa: C901
        self,
        *,
        prototypes: Sequence[str],
        backend: str = "deterministic",
        calculation: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        resume: bool = True,
        partial_resume: bool = False,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
    ) -> tuple[Run, list[EnergyStageResult]]:
        del backend  # the injected backend and its canonical identity are authoritative
        calculation_dict = (
            dict(calculation) if calculation is not None else {"mode": "single_point"}
        )
        calculation_dict.setdefault("mode", "single_point")
        user_payload = dict(payload or {})

        targets: list[dict[str, str]] = []
        unresolved_results: list[EnergyStageResult] = []
        with self._uow as uow:
            resolved, unresolved = resolve_followup_targets_as_results(
                uow=uow,
                identifiers=prototypes,
            )
            targets.extend(resolved)
            for item in unresolved:
                unresolved_results.append(
                    EnergyStageResult(
                        target_uid=str(item.get("target_uid") or ""),
                        target_kind=str(item.get("target_kind") or "unknown"),
                        prototype_uid=str(item.get("prototype_uid") or ""),
                        status=str(item.get("status") or "skipped"),
                        reason=item.get("reason"),
                    )
                )

        backend_identity = self._backend_identity(targets)
        spec = self._create_run_spec(
            targets,
            calculation_dict,
            backend_identity,
        )
        run = self._runs.create(run_type="energy_stage", spec=spec)

        if campaign_uid_full:
            with self._uow as uow:
                uow.edges.add(
                    src_uid_full=run.uid_full,
                    dst_uid_full=campaign_uid_full,
                    kind="run_of_campaign",
                    payload={
                        "campaign_uid_full": campaign_uid_full,
                        "campaign_run_uid_full": campaign_run_uid_full,
                    },
                )
                uow.commit()

        if resume and run.status == "done":
            skipped = [
                EnergyStageResult(
                    target_uid=target.get("target_uid_full")
                    or target.get("prototype_uid_full")
                    or "",
                    target_kind=target.get("target_kind") or "prototype",
                    prototype_uid=target.get("prototype_uid_full") or "",
                    status="skipped",
                    reason="run_already_done",
                    run_uid=run.uid_full,
                )
                for target in targets
            ]
            for result in unresolved_results:
                result.run_uid = run.uid_full
            return run, skipped + unresolved_results

        self._runs.mark_running(
            run.uid_full,
            progress={"stage": "energy", "n_requested": len(targets)},
        )
        existing = (
            self._existing_followups(run_uid_full=run.uid_full)
            if partial_resume
            else {}
        )

        stage_results: list[EnergyStageResult] = []
        completed_followups: list[FollowupResult] = []
        with self._uow as uow:
            for target in targets:
                prototype_uid = target["prototype_uid_full"]
                target_uid = target["target_uid_full"]
                target_kind = target["target_kind"]
                key = (prototype_uid, target_uid)
                if key in existing:
                    row = existing[key]
                    stage_results.append(
                        EnergyStageResult(
                            target_uid=target_uid,
                            target_kind=target_kind,
                            prototype_uid=prototype_uid,
                            status="skipped",
                            reason="existing_followup",
                            run_uid=run.uid_full,
                            followup_uid=row.uid_full,
                            energy=(row.payload or {})["energy_eV"],
                            energy_units="eV",
                            artifact_refs=(row.payload or {})["artifact_refs"],
                        )
                    )
                    continue

                followup_uid = persisted_followup_uid(
                    run_uid_full=run.uid_full,
                    prototype_uid_full=prototype_uid,
                    target_uid_full=target_uid,
                    target_kind=target_kind,
                    kind="energy_stage",
                )
                followup_id = uow.ids.ensure_short_id(uid_full=followup_uid, tag="f")
                compute_config = dict(calculation_dict)
                target_atoms = self._load_target_atoms(target_uid, target_kind)
                if target_atoms is not None:
                    compute_config["target_atoms"] = target_atoms

                interface_area_A2: float | None = None
                try:
                    if target_kind == "interface":
                        if target_atoms is None:
                            raise ValueError(
                                "Authoritative interface atoms are required to record "
                                "the thermodynamic normalization area."
                            )
                        interface_area_A2 = _interface_area_A2_from_atoms(target_atoms)
                    compute_result = self._backend.compute(
                        run_uid=run.uid_full,
                        prototype_uid=prototype_uid,
                        target_uid=target_uid,
                        config=compute_config,
                        uow=uow,
                    )
                    energy = _finite_float(
                        compute_result.energy,
                        name="Computed total energy",
                    )
                    n_steps = _positive_integer(
                        compute_result.n_steps,
                        name="Computed energy step count",
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
                        target_kind=target_kind,
                        kind="energy_stage",
                        status="failed",
                        best_energy=None,
                        param1=None,
                        param2=None,
                        n_points=None,
                        payload={
                            "schema": RAW_ENERGY_RESULT_SCHEMA,
                            "version": ENERGY_RESULT_VERSION,
                            "result_stage": "energy_failed",
                            "quantity": "total_energy",
                            "backend": {
                                "name": self._backend_name,
                                "identity": dict(backend_identity),
                                "settings": dict(calculation_dict),
                            },
                            "workflow_metadata": dict(user_payload),
                            "failure": failure,
                        },
                    )
                    persist_followups_with_edges(uow=uow, followups=[failed])
                    stage_results.append(
                        EnergyStageResult(
                            target_uid=target_uid,
                            target_kind=target_kind,
                            prototype_uid=prototype_uid,
                            status="failed",
                            reason=str(exc),
                            run_uid=run.uid_full,
                            followup_uid=followup_uid,
                        )
                    )
                    continue

                artifact_refs = persist_artifact_payloads(
                    uow=uow,
                    run_uid=run.uid_full,
                    proto_uid=prototype_uid,
                    target_uid=target_uid,
                    artifact_payloads=compute_result.artifact_payloads,
                    artifacts=self._artifacts,
                )
                payload_row = {
                    "schema": RAW_ENERGY_RESULT_SCHEMA,
                    "version": ENERGY_RESULT_VERSION,
                    "result_stage": "energy_evaluated",
                    "quantity": "total_energy",
                    "energy_eV": energy,
                    "n_steps": n_steps,
                    "interface_area_A2": interface_area_A2,
                    "area_source": (
                        "authoritative_interface_cell"
                        if interface_area_A2 is not None
                        else None
                    ),
                    "backend": {
                        "name": self._backend_name,
                        "identity": dict(backend_identity),
                        "settings": dict(calculation_dict),
                    },
                    "workflow_metadata": dict(user_payload),
                    "artifact_refs": artifact_refs,
                    "summary": dict(compute_result.summary or {}),
                }
                followup = FollowupResult(
                    uid_full=followup_uid,
                    id_short=followup_id,
                    run_uid_full=run.uid_full,
                    run_id_short=run.id_short,
                    prototype_uid_full=prototype_uid,
                    prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid),
                    target_uid_full=target_uid,
                    target_kind=target_kind,
                    kind="energy_stage",
                    status="done",
                    best_energy=energy,
                    param1=None,
                    param2=None,
                    n_points=n_steps,
                    payload=payload_row,
                )
                completed_followups.append(followup)
                stage_results.append(
                    EnergyStageResult(
                        target_uid=target_uid,
                        target_kind=target_kind,
                        prototype_uid=prototype_uid,
                        status="completed",
                        run_uid=run.uid_full,
                        followup_uid=followup_uid,
                        energy=energy,
                        energy_units="eV",
                        artifact_refs=artifact_refs,
                    )
                )

            if completed_followups:
                persist_followups_with_edges(uow=uow, followups=completed_followups)

        for result in unresolved_results:
            result.run_uid = run.uid_full
        stage_results.extend(unresolved_results)
        run = finalize_run_state_and_refresh(
            self._runs,
            run,
            stage_results,
            n_requested=len(targets),
        )
        return run, stage_results
