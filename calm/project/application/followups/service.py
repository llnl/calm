"""Application facade for persisted follow-up workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ...domain.models import FollowupResult, Run
from .._uow import fresh_uow, require_uow_factory
from .query import FollowupQueryService


class FollowupsService:
    """Coordinate follow-up stages and persisted follow-up queries.

    The service is the run-only facade used by :class:`Workspace`. Stage
    orchestrators own execution and structured per-target results; this facade
    returns the persisted :class:`Run` for internal Workspace calls.
    """

    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        artifacts: Any | None = None,
    ) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="FollowupsService",
        )
        self._query = FollowupQueryService(uow_factory=uow_factory)
        self._artifacts = artifacts

    def _fresh_orchestrator_uow(self) -> Any:
        """Return one fresh, non-entered UnitOfWork for an orchestrator."""

        return fresh_uow(self._uow_factory, owner="FollowupsService")

    def start_strain_partition_scan(
        self,
        *,
        prototypes: Sequence[str],
        alphas: Sequence[float] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Run:
        """Run a strain-partition stage and return its persisted run."""

        from .strain_scan import StrainPartitionScanOrchestrator

        orchestrator = StrainPartitionScanOrchestrator(self._fresh_orchestrator_uow())
        run, _ = orchestrator.run_stage(
            prototypes=prototypes,
            alphas=alphas,
            payload=payload,
        )
        return run

    def start_registry_search(
        self,
        *,
        prototypes: Sequence[str],
        n_steps: int = 50,
        payload: Mapping[str, Any] | None = None,
    ) -> Run:
        """Run a registry-search stage and return its persisted run."""

        from .registry_search import RegistrySearchOrchestrator

        orchestrator = RegistrySearchOrchestrator(self._fresh_orchestrator_uow())
        run, _ = orchestrator.run_stage(
            prototypes=prototypes,
            n_steps=n_steps,
            payload=payload,
        )
        return run

    def start_relaxation_run(
        self,
        *,
        prototypes: Sequence[str],
        protocol: str = "ionic_positions_v1",
        convergence: Mapping[str, Any] | None = None,
        max_steps: int = 500,
        payload: Mapping[str, Any] | None = None,
        resume: bool = True,
        backend: Any | None = None,
        relax_cell: bool = False,
        partial_resume: bool = False,
    ) -> Run:
        """Run a structural-relaxation stage and return its persisted run."""

        from .relaxation import RelaxationOrchestrator

        orchestrator = RelaxationOrchestrator(
            self._fresh_orchestrator_uow(),
            artifacts=self._artifacts,
        )
        if backend is not None:
            if isinstance(backend, str):
                from .relaxation_backends import make_relaxation_backend

                backend = make_relaxation_backend(backend)
            orchestrator.with_backend(backend)
        run, _ = orchestrator.run_stage(
            prototypes=prototypes,
            protocol=protocol,
            convergence=convergence,
            max_steps=max_steps,
            relax_cell=relax_cell,
            payload=payload,
            resume=resume,
            partial_resume=partial_resume,
        )
        return run

    def get_result(self, identifier: str) -> FollowupResult:
        """Return one authoritative persisted follow-up result."""
        return self._query.get_result(identifier)

    def list_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[FollowupResult]:
        """List persisted follow-up summaries."""

        return self._query.list_results(
            run=run,
            prototype=prototype,
            kind=kind,
            limit=limit,
        )
