"""Strain-partition scan orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from calm.interface.refinement.contract import (
    canonical_alpha_grid,
    canonical_strain_metric,
    select_strain_point,
)
from calm.project.domain.contracts.refinement_result import (
    make_strain_partition_result_payload,
    refinement_result_target,
    strain_partition_selection,
)
from calm.calculators.runtime import construct_calculator
from calm.calculators.spec import CalculatorSpec

from ...domain.models import FollowupResult, Run
from ...ports.uow import UnitOfWork
from ..runs import RunsService
from .calculator_resolution import require_calculator_from_prototype
from .common import persisted_followup_uid, resolve_followup_targets_as_results
from .orch_helpers import (
    finalize_run_state_and_refresh,
    persist_followups_with_edges,
)


@dataclass
class StrainScanStageResult:
    """Per-target outcome from a strain-partition stage."""

    target_uid: str
    target_kind: str
    prototype_uid: str
    status: str
    reason: Any = None
    run_uid: Any = None
    followup_uid: Any = None
    best_energy: Any = None
    best_alpha: Any = None


class StrainPartitionScanOrchestrator:
    """Execute and persist one strain-partition stage."""

    def __init__(self, uow: UnitOfWork) -> None:
        if getattr(uow, "_depth", 0):
            raise ValueError(
                "Do not construct StrainPartitionScanOrchestrator with an "
                "entered UnitOfWork; pass a fresh UnitOfWork."
            )
        self._uow = uow
        self._runs = RunsService(uow=uow)

    def run_stage(
        self,
        *,
        prototypes: Sequence[str],
        alphas: Sequence[float] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[Run, list[StrainScanStageResult]]:
        """Run the scan and return the persisted run and per-target results."""

        alpha_grid = self._validate_and_normalize_inputs(prototypes, alphas)
        user_payload = self._normalize_payload(payload, alpha_grid)

        with self._uow as uow:
            targets, unresolved = resolve_followup_targets_as_results(
                uow=uow,
                identifiers=prototypes,
            )

        with self._uow as uow:
            calculator_specs = {
                prototype_uid: require_calculator_from_prototype(
                    uow,
                    prototype_uid,
                ).to_dict()
                for prototype_uid in sorted(
                    {str(target["prototype_uid_full"]) for target in targets}
                )
            }

        spec = self._create_run_spec(
            targets,
            user_payload,
            alpha_grid,
            calculator_specs,
        )
        run = self._runs.create(run_type="strain_partition_scan", spec=spec)
        self._runs.mark_running(run.uid_full)

        results: list[FollowupResult] = []
        try:
            if targets:
                with self._uow as uow:
                    results = self._compute_scan_results(
                        run,
                        targets,
                        alpha_grid,
                        user_payload,
                        calculator_specs,
                        uow,
                    )
                    persist_followups_with_edges(uow=uow, followups=results)
                    uow.commit()
        except Exception as exc:
            self._runs.mark_failed(
                run.uid_full,
                error={
                    "exception_type": type(exc).__name__,
                    "module": type(exc).__module__,
                    "message": str(exc),
                },
            )
            raise

        stage_results: list[StrainScanStageResult] = []
        for result in results:
            prototype_uid, target_uid, target_kind = refinement_result_target(
                prototype_uid_full=result.prototype_uid_full,
                target_uid_full=result.target_uid_full,
                target_kind=result.target_kind,
            )
            _metric, best_alpha, best_energy = strain_partition_selection(
                result.payload or {}
            )
            stage_results.append(
                StrainScanStageResult(
                    target_uid=target_uid,
                    target_kind=target_kind,
                    prototype_uid=prototype_uid,
                    status="completed",
                    run_uid=run.uid_full,
                    followup_uid=result.uid_full,
                    best_energy=best_energy,
                    best_alpha=best_alpha,
                )
            )
        stage_results.extend(
            StrainScanStageResult(
                target_uid=str(item.get("target_uid") or ""),
                target_kind=str(item.get("target_kind") or "unknown"),
                prototype_uid=str(item.get("prototype_uid") or ""),
                status=str(item.get("status") or "skipped"),
                reason=item.get("reason"),
                run_uid=run.uid_full,
            )
            for item in unresolved
        )

        run = finalize_run_state_and_refresh(
            self._runs,
            run,
            stage_results,
            n_requested=len(targets),
        )
        return run, stage_results

    @staticmethod
    def _validate_and_normalize_inputs(
        prototypes: Sequence[str],
        alphas: Sequence[float] | None,
    ) -> list[float]:
        if not prototypes:
            raise ValueError("prototypes must be a non-empty sequence")
        return list(canonical_alpha_grid(alphas))

    @staticmethod
    def _normalize_payload(
        payload: Mapping[str, Any] | None,
        alpha_grid: list[float],
    ) -> dict[str, Any]:
        user_payload = dict(payload or {})
        user_payload["alphas"] = [float(alpha) for alpha in alpha_grid]
        user_payload["target_metric"] = canonical_strain_metric(
            user_payload.get(
                "target_metric",
                "potential_energy_density_eV_per_A2",
            )
        )
        return user_payload

    @staticmethod
    def _create_run_spec(
        targets: list[dict[str, str]],
        user_payload: dict[str, Any],
        alpha_grid: list[float],
        calculator_specs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        return {
            "kind": "strain_partition_scan",
            "targets": list(targets),
            "prototype_uids": [target["prototype_uid_full"] for target in targets],
            "payload": user_payload,
            "alphas": alpha_grid,
            "impl": "production_v1",
            "calculator_specs": {
                prototype_uid: dict(specification)
                for prototype_uid, specification in calculator_specs.items()
            },
            "calculator_fingerprints": {
                prototype_uid: CalculatorSpec.from_dict(specification).fingerprint()
                for prototype_uid, specification in calculator_specs.items()
            },
        }

    def _compute_scan_results(
        self,
        run: Run,
        targets: list[dict[str, str]],
        alpha_grid: list[float],
        user_payload: dict[str, Any],
        calculator_specs: Mapping[str, Mapping[str, Any]],
        uow: Any,
    ) -> list[FollowupResult]:
        results: list[FollowupResult] = []
        for target in targets:
            prototype_uid = target["prototype_uid_full"]
            target_uid = target["target_uid_full"]
            target_kind = target["target_kind"]

            calculator = CalculatorSpec.from_dict(calculator_specs[prototype_uid])

            points = self._compute_alpha_scan_points(
                prototype_uid,
                alpha_grid,
                calculator,
            )
            target_metric = canonical_strain_metric(user_payload["target_metric"])
            selected = select_strain_point(points, target_metric)
            target_alpha = float(selected["alpha"])
            target_energy = float(selected[target_metric])

            uid_full = persisted_followup_uid(
                run_uid_full=run.uid_full,
                prototype_uid_full=prototype_uid,
                target_uid_full=target_uid,
                target_kind=target_kind,
                kind="strain_partition_scan",
            )
            results.append(
                FollowupResult(
                    uid_full=uid_full,
                    id_short=uow.ids.ensure_short_id(uid_full=uid_full, tag="f"),
                    run_uid_full=run.uid_full,
                    run_id_short=run.id_short,
                    prototype_uid_full=prototype_uid,
                    prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid),
                    target_uid_full=target_uid,
                    target_kind=target_kind,
                    kind="strain_partition_scan",
                    best_energy=target_energy,
                    param1=target_alpha,
                    param2=None,
                    n_points=len(points),
                    payload=make_strain_partition_result_payload(
                        points=points,
                        target_metric=target_metric,
                        target_alpha=target_alpha,
                        target_value=target_energy,
                        calculator=calculator.to_dict(),
                        calculator_fingerprint=calculator.fingerprint(),
                    ),
                )
            )
        return results

    def _compute_alpha_scan_points(
        self,
        prototype_uid: str,
        alpha_grid: list[float],
        calculator_spec: CalculatorSpec | None,
    ) -> list[dict[str, float]]:
        if calculator_spec is None:
            raise ValueError(
                "Calculator specification is required for strain partition scan."
            )

        from .interface_energy import compute_strain_scan_energy_point

        calculator = construct_calculator(calculator_spec, quiet=True)

        points: list[dict[str, float]] = []
        with self._uow as uow:
            for alpha in alpha_grid:
                point = compute_strain_scan_energy_point(
                    uow=uow,
                    prototype_uid_full=prototype_uid,
                    alpha=float(alpha),
                    calc_spec=calculator_spec,
                    translation_frac=(0.0, 0.0),
                    z_padding=1.5,
                    calc=calculator,
                )
                points.append(point)
        return points
