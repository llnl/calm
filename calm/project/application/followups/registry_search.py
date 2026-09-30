"""Registry search orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral
from typing import Any, Mapping, Sequence

import numpy as np

from calm.interface.refinement.contract import (
    REGISTRY_SEED_DERIVATION,
    REGISTRY_SEED_DERIVATION_VERSION,
    stable_registry_seed,
)
from calm.project.domain.contracts.refinement_result import (
    make_registry_search_result_payload,
    refinement_result_target,
)
from calm.calculators.exceptions import (
    CalculatorError,
    CalculatorProvenanceError,
)
from calm.calculators.runtime import construct_calculator
from calm.calculators.spec import CalculatorSpec
from calm.interface.refinement.registry import (
    PERSISTED_REGISTRY_IMPLEMENTATION,
    PERSISTED_REGISTRY_OBJECTIVE,
    PERSISTED_REGISTRY_SCORE_UNITS,
    PERSISTED_REGISTRY_TEMPERATURE,
    REGISTRY_SEARCH_PROTOCOL,
    REGISTRY_SEARCH_PROTOCOL_VERSION,
    RegistrySearchResult,
    monte_carlo_registry_search,
)

from ...domain.models import FollowupResult, Run
from ...ports.uow import UnitOfWork
from ..runs import RunsService
from .calculator_resolution import require_calculator_from_prototype
from .common import persisted_followup_uid, resolve_followup_targets_as_results
from .orch_helpers import load_existing_followups, persist_followups_with_edges


@dataclass
class RegistryStageResult:
    target_uid: str
    target_kind: str
    prototype_uid: str
    status: str  # completed | skipped | failed
    reason: str | None = None
    run_uid: str | None = None
    followup_uid: str | None = None
    derived_interface_uid: str | None = None


@dataclass(frozen=True)
class _RegistryTargetState:
    alpha: float
    translation: tuple[float, float]
    z_padding: float
    vacuum_padding: float | None


@dataclass(frozen=True)
class _PreparedRegistryEvaluator:
    """Fixed geometry and calculator state for one registry trajectory."""

    prepared_interface: Any
    calc_spec: CalculatorSpec
    calc: Any
    area_A2: float


def _authoritative_calculator_spec(uow: Any, prototype_uid: str) -> CalculatorSpec:
    """Resolve mandatory calculator provenance for one registry target."""

    try:
        return require_calculator_from_prototype(uow, prototype_uid)
    except CalculatorProvenanceError as exc:
        raise CalculatorProvenanceError(
            "Registry refinement requires authoritative calculator provenance; "
            f"none could be resolved for prototype {prototype_uid}."
        ) from exc


def _calculator_specs_for_targets(
    uow: Any,
    targets: Sequence[Mapping[str, str]],
) -> dict[str, dict[str, Any]]:
    """Resolve one exact calculator specification per target prototype."""

    specifications: dict[str, dict[str, Any]] = {}
    for prototype_uid in sorted(
        {str(target["prototype_uid_full"]) for target in targets}
    ):
        specifications[prototype_uid] = _authoritative_calculator_spec(
            uow,
            prototype_uid,
        ).to_dict()
    return specifications


def _finite_nonnegative(name: str, value: object) -> float:
    """Return one finite non-negative registry geometry scalar."""

    result = float(value)
    if not isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _canonical_registry_translation(value: object) -> tuple[float, float]:
    """Return one finite canonical persisted registry coordinate."""

    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Initial registry translation must contain two values.")
    translation = float(value[0]), float(value[1])
    if not all(isfinite(component) for component in translation):
        raise ValueError("Initial registry translation must contain finite values.")
    return tuple(float(component % 1.0) for component in translation)


def _registry_target_state(
    uow: Any,
    *,
    target_uid: str,
    target_kind: str,
) -> _RegistryTargetState:
    """Resolve and validate the fixed upstream state for one persisted search."""

    if target_kind == "interface":
        interface = uow.derived_interfaces.get_by_uid_full(target_uid)
        if interface is None:
            raise RuntimeError(f"Registry target interface {target_uid} was not found.")
        alpha = float(interface.strain_alpha)
        translation = tuple(interface.registry_shift_frac_a)
        z_padding = float(interface.z_padding)
        vacuum_padding = interface.vacuum
    elif target_kind == "prototype":
        alpha = 0.5
        translation = (0.0, 0.0)
        z_padding = 1.5
        vacuum_padding = None
    else:
        raise ValueError("Registry target_kind must be 'prototype' or 'interface'.")

    if not isfinite(alpha) or not 0.0 <= alpha <= 1.0:
        raise ValueError("Registry strain alpha must be finite and in [0, 1].")
    translation = _canonical_registry_translation(translation)
    z_padding = _finite_nonnegative("Registry internal gap", z_padding)
    if vacuum_padding is not None:
        vacuum_padding = _finite_nonnegative(
            "Registry boundary vacuum",
            vacuum_padding,
        )
    return _RegistryTargetState(
        alpha=alpha,
        translation=translation,
        z_padding=z_padding,
        vacuum_padding=vacuum_padding,
    )


def _registry_operational_controls(
    user_payload: Mapping[str, Any],
    *,
    seed_base: str,
) -> tuple[float, int | None, int]:
    """Resolve public operational controls and target-specific random seed."""

    settings = dict(user_payload.get("registry_settings") or {})
    step_scale = float(settings.get("translation_step", 0.08))
    if not isfinite(step_scale) or step_scale <= 0.0:
        raise ValueError("Registry translation_step must be finite and positive.")
    requested_seed = settings.get("seed")
    if requested_seed is not None:
        if isinstance(requested_seed, bool) or not isinstance(requested_seed, Integral):
            raise TypeError("Registry seed must be an integer or None.")
        requested_seed = int(requested_seed)
        if requested_seed < 0:
            raise ValueError("Registry seed must be non-negative.")
    return (
        step_scale,
        requested_seed,
        stable_registry_seed(seed_base, requested_seed),
    )


def _registry_followup_result(
    *,
    uow: Any,
    run: Run,
    prototype_uid: str,
    target_uid: str,
    target_kind: str,
    state: _RegistryTargetState,
    calc_spec: CalculatorSpec,
    search_result: RegistrySearchResult,
    requested_seed: int | None,
) -> FollowupResult:
    """Construct one registry followup record with complete provenance."""

    uid_full = persisted_followup_uid(
        run_uid_full=run.uid_full,
        prototype_uid_full=prototype_uid,
        target_uid_full=target_uid,
        target_kind=target_kind,
        kind="registry_search",
    )
    vacuum = state.vacuum_padding
    tx, ty = search_result.translation
    trace = list(search_result.trace or ())
    proposal_trace = [
        record.to_dict() for record in (search_result.proposal_trace or ())
    ]
    provenance = dict(search_result.metadata)
    provenance.update(
        {
            "implementation": PERSISTED_REGISTRY_IMPLEMENTATION,
            "alpha": float(state.alpha),
            "initial_translation": [
                float(state.translation[0]),
                float(state.translation[1]),
            ],
            "fixed_z_padding": float(state.z_padding),
            "fixed_vacuum_padding": (None if vacuum is None else float(vacuum)),
            "z_search_enabled": False,
            "requested_seed": requested_seed,
            "seed_derivation": REGISTRY_SEED_DERIVATION,
            "seed_derivation_version": REGISTRY_SEED_DERIVATION_VERSION,
        }
    )
    return FollowupResult(
        uid_full=uid_full,
        id_short=uow.ids.ensure_short_id(uid_full=uid_full, tag="f"),
        run_uid_full=run.uid_full,
        run_id_short=run.id_short,
        prototype_uid_full=prototype_uid,
        prototype_id_short=uow.ids.ensure_prototype_id(prototype_uid),
        target_uid_full=target_uid,
        target_kind=target_kind,
        kind="registry_search",
        best_energy=float(search_result.score),
        param1=float(tx),
        param2=float(ty),
        n_points=len(trace),
        payload=make_registry_search_result_payload(
            registry_shift_frac_a=(float(tx), float(ty)),
            z_padding=float(state.z_padding),
            vacuum=None if vacuum is None else float(vacuum),
            objective=PERSISTED_REGISTRY_OBJECTIVE,
            objective_units=PERSISTED_REGISTRY_SCORE_UNITS,
            score=float(search_result.score),
            n_steps=int(search_result.n_steps),
            n_accepted=int(search_result.n_accepted),
            trace=trace,
            proposal_trace=proposal_trace,
            calculator=calc_spec.to_dict(),
            calculator_fingerprint=calc_spec.fingerprint(),
            provenance=provenance,
        ),
    )


def _make_registry_calculator(calc_spec: CalculatorSpec) -> Any:
    """Construct one calculator while suppressing optional backend chatter."""

    return construct_calculator(calc_spec, quiet=True)


def _prepare_registry_energy_evaluator(
    uow_context: UnitOfWork,
    *,
    prototype_uid: str,
    calc_spec: CalculatorSpec,
    calc: Any,
    alpha: float,
    z_padding: float,
    vacuum_padding: float | None,
) -> _PreparedRegistryEvaluator:
    """Prepare all translation-independent registry objective state once."""

    from .interface_energy import prepare_interface_from_prototype_with_strain

    with uow_context as uow:
        prepared_interface = prepare_interface_from_prototype_with_strain(
            uow,
            prototype_uid,
            alpha=alpha,
            z_padding=z_padding,
            vacuum_padding=vacuum_padding,
        )
    area = float(np.linalg.norm(np.cross(prepared_interface.c1, prepared_interface.c2)))
    if not np.isfinite(area) or area <= 0.0:
        raise ValueError(
            "Registry objective requires a finite positive interface area."
        )
    return _PreparedRegistryEvaluator(
        prepared_interface=prepared_interface,
        calc_spec=calc_spec,
        calc=calc,
        area_A2=area,
    )


def _registry_energy_density(
    evaluator: _PreparedRegistryEvaluator,
    translation: np.ndarray,
) -> float:
    """Evaluate one translated state from prepared registry-search geometry."""

    from calm.interface.building._kernel import build_prepared_interface_atoms
    from .interface_energy import compute_interface_energy

    translation_frac = float(translation[0]), float(translation[1])
    atoms = build_prepared_interface_atoms(
        evaluator.prepared_interface,
        translation_frac=translation_frac,
    ).atoms
    total_energy = compute_interface_energy(
        atoms,
        evaluator.calc_spec,
        relax=False,
        calc=evaluator.calc,
    )
    score = float(total_energy) / evaluator.area_A2
    if not np.isfinite(score):
        raise ValueError(
            "Registry objective evaluation returned a non-finite energy density."
        )
    return score


class RegistrySearchOrchestrator:
    """Orchestrates registry search followups.

    This orchestrator coordinates input validation, target resolution,
    run creation and lifecycle management, Monte Carlo search computation,
    result persistence and edge creation. The class is implemented with
    focused private methods to keep responsibilities clear and testable.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        if getattr(uow, "_depth", 0):
            raise ValueError(
                "Do not construct RegistrySearchOrchestrator with an entered "
                "UnitOfWork; pass a fresh UnitOfWork."
            )
        self._uow = uow
        self._runs = RunsService(uow=uow)

    def run_stage(  # noqa: C901
        self,
        *,
        prototypes: Sequence[str],
        n_steps: int = 50,
        payload: Mapping[str, Any] | None = None,
        resume: bool = True,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
        partial_resume: bool = False,
    ) -> tuple[Run, list[RegistryStageResult]]:
        """Run registry refinement and return the run plus per-target results."""
        # Validate and normalize inputs
        self._validate_inputs(prototypes, n_steps)
        user_payload = self._normalize_payload(payload)

        # Resolve expected user-input errors into per-target skipped results.
        # Database, transaction, and resolver implementation failures propagate.
        with self._uow as uow:
            targets, unresolved = resolve_followup_targets_as_results(uow, prototypes)

        with self._uow as uow:
            calculator_specs = _calculator_specs_for_targets(uow, targets)

        # Create run specification
        spec = self._create_run_spec(
            targets,
            user_payload,
            n_steps,
            calculator_specs,
        )

        # Use lifecycle helper to create run and potentially short-circuit
        from .orch_helpers import (
            create_run_and_maybe_short_circuit,
            finalize_run_state_and_refresh,
        )

        run, shortcircuit = create_run_and_maybe_short_circuit(
            self._runs,
            run_type="registry_search",
            spec=spec,
            targets=targets,
            unresolved=unresolved,
            resume=resume,
        )
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
        if shortcircuit is not None:
            # convert neutral dicts to RegistryStageResult
            results_summary = [
                RegistryStageResult(
                    target_uid=str(item.get("target_uid") or ""),
                    target_kind=str(item.get("target_kind") or "unknown"),
                    prototype_uid=str(item.get("prototype_uid") or ""),
                    status=str(item.get("status") or "skipped"),
                    reason=item.get("reason"),
                    run_uid=item.get("run_uid"),
                )
                for item in shortcircuit
            ]
            return run, results_summary

        # Mark running with initial progress
        self._runs.mark_running(
            run.uid_full,
            progress={"stage": "running", "n_requested": len(targets)},
        )

        # Compute and persist search results; also build per-target RegistryStageResult
        registry_results: list[RegistryStageResult] = []
        try:
            with self._uow as uow:
                # Partial-resume: detect already-persisted followups and skip them
                # when requested.
                existing_followups = {}
                if partial_resume:
                    existing_followups = load_existing_followups(
                        uow,
                        run_uid_full=run.uid_full,
                        kind="registry_search",
                        targets=targets,
                    )

                compute_targets = []
                for t in targets:
                    key = (t.get("prototype_uid_full"), t.get("target_uid_full"))
                    if partial_resume and key in existing_followups:
                        # Skip computing this target and reconstruct the stage
                        # result from the existing row.
                        rr = existing_followups[key]
                        prototype_uid, target_uid, target_kind = (
                            refinement_result_target(
                                prototype_uid_full=rr.prototype_uid_full,
                                target_uid_full=rr.target_uid_full,
                                target_kind=rr.target_kind,
                            )
                        )
                        registry_results.append(
                            RegistryStageResult(
                                target_uid=target_uid,
                                target_kind=target_kind,
                                prototype_uid=prototype_uid,
                                status="skipped",
                                reason="existing_followup",
                                run_uid=run.uid_full,
                                followup_uid=rr.uid_full,
                            )
                        )
                    else:
                        compute_targets.append(t)

                # Compute search results for remaining targets
                results = []
                if compute_targets:
                    results = self._compute_search_results(
                        run,
                        compute_targets,
                        n_steps,
                        user_payload,
                        calculator_specs,
                        uow,
                    )
                    # Persist followup rows and mandatory provenance atomically.
                    persist_followups_with_edges(uow=uow, followups=results)
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

        # Convert persisted followup results into RegistryStageResult summary
        for r in results:
            prototype_uid, target_uid, target_kind = refinement_result_target(
                prototype_uid_full=r.prototype_uid_full,
                target_uid_full=r.target_uid_full,
                target_kind=r.target_kind,
            )
            registry_results.append(
                RegistryStageResult(
                    target_uid=target_uid,
                    target_kind=target_kind,
                    prototype_uid=prototype_uid,
                    status="completed",
                    reason=None,
                    run_uid=run.uid_full,
                    followup_uid=r.uid_full,
                )
            )

        # Attach unresolved skipped entries to registry_results
        registry_results.extend(
            RegistryStageResult(
                target_uid=str(item.get("target_uid") or ""),
                target_kind=str(item.get("target_kind") or "unknown"),
                prototype_uid=str(item.get("prototype_uid") or ""),
                status=str(item.get("status") or "skipped"),
                reason=item.get("reason"),
                run_uid=run.uid_full,
            )
            for item in unresolved
        )

        # Finalize run state using helper
        run = finalize_run_state_and_refresh(
            self._runs, run, registry_results, n_requested=len(targets)
        )
        return run, registry_results

    def _validate_inputs(self, prototypes: Sequence[str], n_steps: int) -> None:
        """Validate inputs.

        Parameters
        ----------
        prototypes : Sequence[str]
            Prototype identifiers.
        n_steps : int
            Number of Monte Carlo steps.

        Raises
        ------
        ValueError
            If inputs are invalid.
        """
        if not prototypes:
            raise ValueError("prototypes must be a non-empty sequence")
        if isinstance(n_steps, bool) or not isinstance(n_steps, Integral):
            raise TypeError("n_steps must be an integer")
        if n_steps <= 0:
            raise ValueError("n_steps must be > 0")

    @staticmethod
    def _normalize_payload(
        payload: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Return the exact user payload stored in the run specification."""

        return dict(payload or {})

    def _create_run_spec(
        self,
        targets: list[dict[str, str]],
        user_payload: dict[str, Any],
        n_steps: int,
        calculator_specs: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create run specification dictionary.

        Parameters
        ----------
        targets : list[dict[str, str]]
            Resolved followup targets.
        user_payload : dict[str, Any]
            User metadata.
        n_steps : int
            Number of Monte Carlo steps.

        Returns
        -------
        dict[str, Any]
            Run specification.
        """
        return {
            "kind": "registry_search",
            "targets": list(targets),
            "prototype_uids": [t["prototype_uid_full"] for t in targets],
            "payload": user_payload,
            "n_steps": n_steps,
            "impl": PERSISTED_REGISTRY_IMPLEMENTATION,
            "protocol": REGISTRY_SEARCH_PROTOCOL,
            "protocol_version": REGISTRY_SEARCH_PROTOCOL_VERSION,
            "objective": PERSISTED_REGISTRY_OBJECTIVE,
            "objective_units": PERSISTED_REGISTRY_SCORE_UNITS,
            "temperature": PERSISTED_REGISTRY_TEMPERATURE,
            "temperature_units": PERSISTED_REGISTRY_SCORE_UNITS,
            "search_space": "fractional_translation_torus",
            "translation_metric": "euclidean_in_fractional_coordinates",
            "z_search_enabled": False,
            "calculator_specs": {
                prototype_uid: dict(specification)
                for prototype_uid, specification in calculator_specs.items()
            },
            "calculator_fingerprints": {
                prototype_uid: CalculatorSpec.from_dict(specification).fingerprint()
                for prototype_uid, specification in calculator_specs.items()
            },
        }

    def _compute_search_results(
        self,
        run: Run,
        targets: list[dict[str, str]],
        n_steps: int,
        user_payload: dict[str, Any],
        calculator_specs: Mapping[str, Mapping[str, Any]],
        uow: Any,
    ) -> list[FollowupResult]:
        """Compute authoritative translation-only registry results."""

        results: list[FollowupResult] = []
        for target in targets:
            prototype_uid = target["prototype_uid_full"]
            target_uid = target["target_uid_full"]
            target_kind = target["target_kind"]
            calc_spec = CalculatorSpec.from_dict(calculator_specs[prototype_uid])
            state = _registry_target_state(
                uow,
                target_uid=target_uid,
                target_kind=target_kind,
            )
            seed_base = f"{run.uid_full}:{target_uid}:registry"
            step_scale, requested_seed, actual_seed = _registry_operational_controls(
                user_payload,
                seed_base=seed_base,
            )
            search_result = self._compute_monte_carlo_trace(
                base=seed_base,
                n_steps=n_steps,
                prototype_uid_full=prototype_uid,
                calc_spec=calc_spec,
                alpha=state.alpha,
                translation0=state.translation,
                z_padding=state.z_padding,
                vacuum_padding=state.vacuum_padding,
                step_scale=step_scale,
                seed=actual_seed,
            )
            results.append(
                _registry_followup_result(
                    uow=uow,
                    run=run,
                    prototype_uid=prototype_uid,
                    target_uid=target_uid,
                    target_kind=target_kind,
                    state=state,
                    calc_spec=calc_spec,
                    search_result=search_result,
                    requested_seed=requested_seed,
                )
            )
        return results

    def _compute_monte_carlo_trace(
        self,
        base: str,
        n_steps: int,
        prototype_uid_full: str,
        calc_spec: CalculatorSpec,
        alpha: float = 0.5,
        translation0: tuple[float, float] = (0.0, 0.0),
        z_padding: float = 1.5,
        vacuum_padding: float | None = None,
        step_scale: float = 0.08,
        temperature: float = PERSISTED_REGISTRY_TEMPERATURE,
        seed: int | None = None,
    ) -> RegistrySearchResult:
        """Evaluate a translation-only persisted registry trajectory."""

        if calc_spec is None:
            raise ValueError(
                "A real calculator specification is required for registry refinement."
            )
        calc = _make_registry_calculator(calc_spec)
        evaluator = _prepare_registry_energy_evaluator(
            self._uow,
            prototype_uid=prototype_uid_full,
            calc_spec=calc_spec,
            calc=calc,
            alpha=alpha,
            z_padding=float(z_padding),
            vacuum_padding=vacuum_padding,
        )

        def energy_fn(translation: np.ndarray) -> float:
            return _registry_energy_density(evaluator, translation)

        try:
            actual_seed = stable_registry_seed(base) if seed is None else int(seed)
            result = monte_carlo_registry_search(
                energy_fn,
                n_steps=n_steps,
                step_scale=float(step_scale),
                temperature=float(temperature),
                seed=actual_seed,
                x0=translation0,
                keep_trace=True,
                score_units=PERSISTED_REGISTRY_SCORE_UNITS,
            )
        except CalculatorError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Monte Carlo registry search failed for prototype "
                f"{prototype_uid_full}. Error: {exc}"
            ) from exc
        return result
