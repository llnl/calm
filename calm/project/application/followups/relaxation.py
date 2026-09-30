"""Authoritative structural-relaxation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
import warnings

from calm.project.domain.contracts.relaxation import (
    RelaxationControls,
    canonical_relaxation_controls,
    validate_relaxation_result,
)

from ...domain.models import FollowupResult, Run
from ...ports.uow import UnitOfWork
from ..runs import RunsService
from .common import persisted_followup_uid, resolve_followup_targets_as_results
from .orch_helpers import (
    finalize_run_state_and_refresh,
    persist_artifact_payloads,
    persist_followups_with_edges,
)
from .relaxation_backends import RealRelaxationBackend


@dataclass
class RelaxationStageResult:
    target_uid: str
    target_kind: str
    prototype_uid: str
    status: str
    reason: Any = None
    run_uid: Any = None
    followup_uid: Any = None
    relaxed_interface_uid: Any = None
    artifact_refs: Any = None


class RelaxationOrchestrator:
    """Run synchronous, persistent structural relaxation follow-ups."""

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        artifacts: Any | None = None,
        target_atoms_loader: Any | None = None,
    ) -> None:
        if getattr(uow, "_depth", 0):
            raise ValueError(
                "Do not construct RelaxationOrchestrator with an entered UnitOfWork; "
                "pass a fresh UnitOfWork."
            )
        self._uow = uow
        self._runs = RunsService(uow=uow)
        self._backend = RealRelaxationBackend()
        self._backend_name = "real"
        self._artifacts = artifacts
        self._target_atoms_loader = target_atoms_loader

    def _existing_uow_factory(self) -> UnitOfWork:
        """Return the orchestrator UoW for in-transaction service construction."""

        return self._uow

    def with_backend(self, backend: Any) -> "RelaxationOrchestrator":
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
                raise TypeError("Relaxation backend identity must be a mapping.")
            return dict(value)
        return {"name": self._backend_name}

    def _create_run_spec(
        self,
        targets: list[dict[str, str]],
        payload: dict[str, Any],
        controls: RelaxationControls,
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
            "kind": "relaxation_stage",
            "targets": ordered_targets,
            "controls": controls.to_dict(),
            "payload": dict(payload),
            "impl": "typed_persistent_v2",
            "backend": dict(backend_identity),
        }

    @staticmethod
    def _unresolved_result(item: Mapping[str, Any]) -> RelaxationStageResult:
        return RelaxationStageResult(
            target_uid=str(item.get("target_uid") or ""),
            target_kind=str(item.get("target_kind") or "unknown"),
            prototype_uid=str(item.get("prototype_uid") or ""),
            status=str(item.get("status") or "skipped"),
            reason=item.get("reason"),
        )

    def _existing_followups(
        self,
        *,
        run_uid_full: str,
    ) -> dict[tuple[str, str], FollowupResult]:
        out: dict[tuple[str, str], FollowupResult] = {}
        with self._uow as uow:
            rows = uow.followups.list(
                run_uid_full=run_uid_full,
                kind="relaxation_stage",
                limit=100000,
            )
            for row in rows:
                if str(row.status) not in {"done", "completed"}:
                    continue
                target_uid = row.target_uid_full or (row.payload or {}).get(
                    "target_uid_full"
                )
                if not row.prototype_uid_full or not target_uid:
                    raise ValueError(
                        f"Persisted relaxation follow-up {row.uid_full!r} is missing "
                        "prototype or target identity."
                    )
                out[(row.prototype_uid_full, str(target_uid))] = row
        return out

    def _load_target_atoms(self, target_uid_full: str, target_kind: str) -> Any | None:
        if target_kind != "interface" or not callable(self._target_atoms_loader):
            return None
        return self._target_atoms_loader(target_uid_full)

    def _target_atoms_for_backend(
        self,
        target_uid_full: str,
        target_kind: str,
    ) -> Any | None:
        """Load atomistic state only for backends that require it."""

        if not bool(getattr(self._backend, "requires_target_atoms", False)):
            return None
        atoms = self._load_target_atoms(target_uid_full, target_kind)
        if atoms is None:
            raise RuntimeError(
                "The selected relaxation backend requires a persisted "
                "atomistic interface target."
            )
        return atoms

    def _derive_relaxed_interface(  # noqa: C901
        self,
        *,
        uow: UnitOfWork,
        run: Run,
        followup_uid: str,
        prototype_uid_full: str,
        target_uid_full: str,
        target_kind: str,
        compute_result: Any,
        user_payload: Mapping[str, Any],
    ) -> tuple[str | None, list[str]]:
        params = dict(getattr(compute_result, "relaxed_params", {}) or {})
        authority = str(params.get("scientific_authority") or "").strip().lower()
        if authority != "calculator_backed":
            return None, []

        from ..derived_interfaces import DerivedInterfaceService

        seed = target_uid_full if target_kind == "interface" else prototype_uid_full
        settings = dict(user_payload.get("relax_settings") or {})
        params.update(
            {
                "source_followup_uid": followup_uid,
                "source_run_uid": run.uid_full,
                "source_interface_uid": (
                    target_uid_full if target_kind == "interface" else None
                ),
                "relaxation_backend": self._backend_name,
                "relaxation_settings": settings,
            }
        )
        search_name = user_payload.get("search_name")
        if search_name:
            params["search_name"] = search_name

        service = DerivedInterfaceService(
            uow_factory=self._existing_uow_factory,
            artifacts=self._artifacts,
        )
        interface = service.create_in(
            uow,
            prototype=seed,
            label=(
                str(user_payload.get("label")) if user_payload.get("label") else None
            ),
            stage="relaxed",
            params=params,
            atoms=getattr(compute_result, "relaxed_atoms", None),
            inherit_seed_strain_state=not bool(settings["relax_cell"]),
            artifact_run=run.uid_full,
        )
        interface_artifacts: list[str] = []
        if getattr(compute_result, "relaxed_atoms", None) is not None:
            for ref in interface.artifact_refs:
                value = ref["artifact_uid"]
                if value not in interface_artifacts:
                    interface_artifacts.append(value)
        return interface.uid_full, interface_artifacts

    @staticmethod
    def _compute_certificate(
        compute_result: Any,
        controls: RelaxationControls,
    ) -> dict[str, Any]:
        max_atomic = getattr(compute_result, "max_force", None)
        if max_atomic is None:
            max_atomic = 0.0
        max_optimizer_residual = getattr(
            compute_result,
            "max_optimizer_residual",
            None,
        )
        if max_optimizer_residual is None:
            max_optimizer_residual = max_atomic
        optimizer_converged = getattr(
            compute_result,
            "optimizer_reported_converged",
            None,
        )
        if optimizer_converged is None:
            optimizer_converged = getattr(compute_result, "converged", False)
        return validate_relaxation_result(
            final_energy_eV=getattr(compute_result, "final_energy", None),
            n_steps=getattr(compute_result, "n_steps", None),
            max_steps=controls.max_steps,
            converged=optimizer_converged,
            max_atomic_force_eV_per_A=max_atomic,
            max_optimizer_residual=max_optimizer_residual,
            force_tolerance_eV_per_A=controls.force_tolerance_eV_per_A,
        )

    def _failure_followup(
        self,
        *,
        uow: UnitOfWork,
        run: Run,
        followup_uid: str,
        followup_id: str,
        prototype_uid_full: str,
        target_uid_full: str,
        target_kind: str,
        message: str,
        backend_identity: Mapping[str, Any],
        relaxation_settings: Mapping[str, Any],
        diagnostics: Mapping[str, Any] | None = None,
        exception: Exception | None = None,
    ) -> tuple[FollowupResult, RelaxationStageResult]:
        failure = {
            "message": message,
            "exception_type": (
                type(exception).__name__
                if exception is not None
                else "RelaxationConvergenceError"
            ),
            "module": (
                type(exception).__module__
                if exception is not None
                else "calm.project.domain.contracts.relaxation"
            ),
        }
        values = dict(diagnostics or {})
        energy = (
            float(values["final_energy_eV"])
            if values.get("final_energy_eV") is not None
            else None
        )
        max_force = (
            float(values["max_atomic_force_eV_per_A"])
            if values.get("max_atomic_force_eV_per_A") is not None
            else None
        )
        n_steps = int(values["n_steps"]) if values.get("n_steps") is not None else None
        payload = {
            "target_uid_full": target_uid_full,
            "target_kind": target_kind,
            "failure": failure,
            "error": message,
            "relaxation_backend": self._backend_name,
            "backend_identity": dict(backend_identity),
            "relaxation_settings": dict(relaxation_settings),
            "convergence_certificate": values,
        }
        failed = FollowupResult(
            uid_full=followup_uid,
            id_short=followup_id,
            run_uid_full=run.uid_full,
            run_id_short=run.id_short,
            prototype_uid_full=prototype_uid_full,
            prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid_full),
            target_uid_full=target_uid_full,
            target_kind=target_kind,
            kind="relaxation_stage",
            status="failed",
            best_energy=energy,
            param1=max_force,
            param2=0.0,
            n_points=n_steps,
            payload=payload,
        )
        result = RelaxationStageResult(
            target_uid=target_uid_full,
            target_kind=target_kind,
            prototype_uid=prototype_uid_full,
            status="failed",
            reason=message,
            run_uid=run.uid_full,
            followup_uid=followup_uid,
        )
        return failed, result

    def run_stage(  # noqa: C901
        self,
        *,
        prototypes: Sequence[str],
        protocol: str = "ionic_positions_v1",
        convergence: Mapping[str, Any] | None = None,
        max_steps: int = 500,
        relax_cell: bool = False,
        payload: Mapping[str, Any] | None = None,
        resume: bool = True,
        partial_resume: bool = False,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
    ) -> tuple[Run, list[RelaxationStageResult]]:
        controls = canonical_relaxation_controls(
            protocol=protocol,
            convergence=convergence,
            max_steps=max_steps,
            relax_cell=relax_cell,
        )
        convergence_dict = {
            "force_tol": controls.force_tolerance_eV_per_A,
        }

        user_payload = dict(payload or {})
        user_payload["relax_settings"] = {
            "fmax": controls.force_tolerance_eV_per_A,
            "steps": controls.max_steps,
            "relax_cell": controls.relax_cell,
        }

        targets: list[dict[str, str]] = []
        unresolved_results: list[RelaxationStageResult] = []
        with self._uow as uow:
            resolved, unresolved = resolve_followup_targets_as_results(
                uow=uow,
                identifiers=prototypes,
            )
            targets.extend(resolved)
            unresolved_results.extend(
                self._unresolved_result(item) for item in unresolved
            )

        backend_identity = self._backend_identity(targets)
        spec = self._create_run_spec(
            targets,
            user_payload,
            controls,
            backend_identity,
        )
        run = self._runs.create(run_type="relaxation_stage", spec=spec)

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
                RelaxationStageResult(
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
            return self._runs.get(run.id_short), skipped + unresolved_results

        self._runs.mark_running(
            run.uid_full,
            progress={"stage": "relaxing", "n_requested": len(targets)},
        )

        existing = (
            self._existing_followups(run_uid_full=run.uid_full)
            if partial_resume
            else {}
        )
        completed_followups: list[FollowupResult] = []
        stage_results: list[RelaxationStageResult] = []

        with self._uow as uow:
            for target in targets:
                prototype_uid_full = target["prototype_uid_full"]
                target_uid_full = target["target_uid_full"]
                target_kind = target["target_kind"]
                key = (prototype_uid_full, target_uid_full)

                if key in existing:
                    row = existing[key]
                    row_payload = dict(row.payload or {})
                    stage_results.append(
                        RelaxationStageResult(
                            target_uid=target_uid_full,
                            target_kind=target_kind,
                            prototype_uid=prototype_uid_full,
                            status="skipped",
                            reason="existing_followup",
                            run_uid=run.uid_full,
                            followup_uid=row.uid_full,
                            relaxed_interface_uid=row_payload.get(
                                "relaxed_interface_uid"
                            )
                            or row_payload.get("derived_interface_uid"),
                            artifact_refs=row_payload.get("artifact_refs"),
                        )
                    )
                    continue

                followup_uid = persisted_followup_uid(
                    run_uid_full=run.uid_full,
                    prototype_uid_full=prototype_uid_full,
                    target_uid_full=target_uid_full,
                    target_kind=target_kind,
                    kind="relaxation_stage",
                )
                followup_id = uow.ids.ensure_short_id(
                    uid_full=followup_uid,
                    tag="f",
                )
                compute_config: dict[str, Any] = {
                    "max_steps": controls.max_steps,
                    "protocol": controls.protocol,
                    "convergence": convergence_dict,
                    "relax_cell": controls.relax_cell,
                    "target_kind": target_kind,
                }
                try:
                    target_atoms = self._target_atoms_for_backend(
                        target_uid_full,
                        target_kind,
                    )
                    if target_atoms is not None:
                        compute_config["target_atoms"] = target_atoms
                    compute_result = self._backend.compute(
                        run_uid=run.uid_full,
                        prototype_uid=prototype_uid_full,
                        target_uid=target_uid_full,
                        config=compute_config,
                        uow=uow,
                    )
                    certificate = self._compute_certificate(
                        compute_result,
                        controls,
                    )
                except Exception as exc:
                    warnings.warn(
                        f"Relaxation backend error for target {target_uid_full}: {exc}",
                        UserWarning,
                    )
                    failed, failed_result = self._failure_followup(
                        uow=uow,
                        run=run,
                        followup_uid=followup_uid,
                        followup_id=followup_id,
                        prototype_uid_full=prototype_uid_full,
                        target_uid_full=target_uid_full,
                        target_kind=target_kind,
                        message=str(exc),
                        backend_identity=backend_identity,
                        relaxation_settings=user_payload["relax_settings"],
                        exception=exc,
                    )
                    persist_followups_with_edges(uow=uow, followups=[failed])
                    stage_results.append(failed_result)
                    continue

                artifact_refs = persist_artifact_payloads(
                    uow=uow,
                    run_uid=run.uid_full,
                    proto_uid=prototype_uid_full,
                    target_uid=target_uid_full,
                    artifact_payloads=compute_result.artifact_payloads,
                    artifacts=self._artifacts,
                )
                if not certificate["converged"]:
                    message = (
                        "Structural relaxation did not satisfy the requested "
                        "optimizer-residual tolerance within the step budget."
                    )
                    failed, failed_result = self._failure_followup(
                        uow=uow,
                        run=run,
                        followup_uid=followup_uid,
                        followup_id=followup_id,
                        prototype_uid_full=prototype_uid_full,
                        target_uid_full=target_uid_full,
                        target_kind=target_kind,
                        message=message,
                        backend_identity=backend_identity,
                        relaxation_settings=user_payload["relax_settings"],
                        diagnostics=certificate,
                    )
                    failed.payload["artifact_refs"] = list(artifact_refs)
                    failed.payload["summary"] = dict(
                        getattr(compute_result, "summary", {}) or {}
                    )
                    persist_followups_with_edges(uow=uow, followups=[failed])
                    failed_result.artifact_refs = artifact_refs
                    stage_results.append(failed_result)
                    continue

                try:
                    relaxed_interface_uid, interface_artifact_refs = (
                        self._derive_relaxed_interface(
                            uow=uow,
                            run=run,
                            followup_uid=followup_uid,
                            prototype_uid_full=prototype_uid_full,
                            target_uid_full=target_uid_full,
                            target_kind=target_kind,
                            compute_result=compute_result,
                            user_payload=user_payload,
                        )
                    )
                except Exception as exc:
                    message = f"Could not persist relaxed interface: {exc}"
                    failed, failed_result = self._failure_followup(
                        uow=uow,
                        run=run,
                        followup_uid=followup_uid,
                        followup_id=followup_id,
                        prototype_uid_full=prototype_uid_full,
                        target_uid_full=target_uid_full,
                        target_kind=target_kind,
                        message=message,
                        backend_identity=backend_identity,
                        relaxation_settings=user_payload["relax_settings"],
                        diagnostics=certificate,
                        exception=exc,
                    )
                    failed.payload["artifact_refs"] = list(artifact_refs)
                    failed.payload["summary"] = dict(
                        getattr(compute_result, "summary", {}) or {}
                    )
                    persist_followups_with_edges(uow=uow, followups=[failed])
                    failed_result.artifact_refs = artifact_refs
                    stage_results.append(failed_result)
                    continue
                for artifact_uid in interface_artifact_refs:
                    if artifact_uid not in artifact_refs:
                        artifact_refs.append(artifact_uid)
                payload_row = {
                    "target_uid_full": target_uid_full,
                    "target_kind": target_kind,
                    "relaxed_interface_uid": relaxed_interface_uid,
                    "derived_interface_uid": relaxed_interface_uid,
                    "artifact_refs": artifact_refs,
                    "final_energy_eV": certificate["final_energy_eV"],
                    "n_steps": certificate["n_steps"],
                    "converged": certificate["converged"],
                    "optimizer_reported_converged": certificate[
                        "optimizer_reported_converged"
                    ],
                    "residual_satisfied": certificate["residual_satisfied"],
                    "max_force_eV_per_A": certificate["max_atomic_force_eV_per_A"],
                    "max_optimizer_residual": certificate["max_optimizer_residual"],
                    "relaxation_backend": self._backend_name,
                    "backend_identity": dict(backend_identity),
                    "relaxation_settings": user_payload["relax_settings"],
                    "convergence_certificate": dict(certificate),
                    "summary": dict(compute_result.summary or {}),
                }
                followup = FollowupResult(
                    uid_full=followup_uid,
                    id_short=followup_id,
                    run_uid_full=run.uid_full,
                    run_id_short=run.id_short,
                    prototype_uid_full=prototype_uid_full,
                    prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid_full),
                    target_uid_full=target_uid_full,
                    target_kind=target_kind,
                    kind="relaxation_stage",
                    status="done",
                    best_energy=certificate["final_energy_eV"],
                    param1=certificate["max_atomic_force_eV_per_A"],
                    param2=1.0,
                    n_points=certificate["n_steps"],
                    payload=payload_row,
                )
                completed_followups.append(followup)
                stage_results.append(
                    RelaxationStageResult(
                        target_uid=target_uid_full,
                        target_kind=target_kind,
                        prototype_uid=prototype_uid_full,
                        status="completed",
                        run_uid=run.uid_full,
                        followup_uid=followup_uid,
                        relaxed_interface_uid=relaxed_interface_uid,
                        artifact_refs=artifact_refs,
                    )
                )

            if completed_followups:
                persist_followups_with_edges(
                    uow=uow,
                    followups=completed_followups,
                )
                for followup in completed_followups:
                    relaxed_uid = (followup.payload or {}).get("relaxed_interface_uid")
                    if relaxed_uid:
                        uow.edges.add(
                            src_uid_full=followup.uid_full,
                            dst_uid_full=str(relaxed_uid),
                            kind="followup_to_interface",
                            payload={"stage": "relaxed"},
                        )

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
