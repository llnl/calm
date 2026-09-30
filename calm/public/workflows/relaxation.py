"""Internal orchestration owner for public relaxation workflows.

The :class:`~calm.public.project.Project` facade delegates structural-
relaxation composition to this service. Scientific execution, transaction
ownership, atom artifacts, relaxed-interface persistence, follow-up records,
and lineage remain owned by the existing Workspace relaxation orchestrator.
This module owns public target normalization, settings validation, stage
sequencing, failure policy, reporting, and typed result assembly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from calm.public.presentation.reporting import ensure_console_reporter

from calm.public.presentation.stage import summarize_stage_results
from calm.public.projections.stage import expose_public_stage_targets
from calm.public.records.followups import RelaxationWorkflowResult
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.collections.persistence import RelaxationResultCollection
from calm.public.records.persistence import ProjectInterface, ProjectRun
from calm.public.inputs.settings import RelaxSettings


class _RelaxationWorkspace(Protocol):
    def run_relaxation_stage(
        self,
        prototypes: list[str],
        **kwargs: Any,
    ) -> list[dict]: ...


class _RelaxationRepository(Protocol):
    def list_interfaces(
        self,
        *,
        search_name: str | None = None,
        limit: int | None = None,
    ) -> list[Any]: ...

    def get_interface(self, identifier: str) -> Any: ...

    def get_run(self, identifier: str) -> Any: ...

    def list_followup_results(self, **kwargs: Any) -> list[Any]: ...


class ProjectRelaxationWorkflowService:
    """Coordinate public structural relaxation over authoritative records."""

    _REFINED_STAGES = {"strain_partitioned", "registry_refined"}

    def __init__(
        self,
        *,
        project: Any,
        workspace: _RelaxationWorkspace,
        repository: _RelaxationRepository,
    ) -> None:
        self._project = project
        self._workspace = workspace
        self._repo = repository

    @staticmethod
    def _validate_on_error(on_error: str) -> None:
        if on_error not in {"raise", "record"}:
            raise ValueError("on_error must be 'raise' or 'record'.")

    @classmethod
    def _validate_stage(cls, stage: str) -> None:
        if stage not in cls._REFINED_STAGES:
            raise ValueError(
                "stage must be 'strain_partitioned' or 'registry_refined'."
            )

    @staticmethod
    def _validate_backend(backend: Any) -> None:
        if (
            backend is None
            or isinstance(backend, str)
            or callable(getattr(backend, "identity", None))
        ):
            return
        raise TypeError(
            "Custom relaxation backends used by Project.relax_interfaces must "
            "implement identity(targets=..., uow=...) so execution "
            "configuration participates in deterministic run identity."
        )

    def _interface(self, item: Any) -> ProjectInterface:
        if isinstance(item, ProjectInterface):
            return item
        if isinstance(item, str):
            item = self._repo.get_interface(item)
        return ProjectInterface.from_item(item)

    def _selected_interfaces(
        self,
        interfaces: Any | None,
        *,
        stage: str,
        search_name: str | None,
    ) -> list[Any]:
        if interfaces is None:
            return [
                item
                for item in self._repo.list_interfaces(
                    search_name=search_name,
                    limit=None,
                )
                if self._interface(item).stage == stage
            ]
        if isinstance(interfaces, str):
            return [interfaces]
        if hasattr(interfaces, "records") and callable(interfaces.records):
            return list(interfaces.records())
        try:
            return list(interfaces)
        except TypeError as exc:
            raise TypeError(
                "interfaces must be an interface identifier, a project-backed "
                "InterfaceCollection, or an iterable of persisted interfaces."
            ) from exc

    def _target_ids(
        self,
        interfaces: Any | None,
        *,
        stage: str,
        search_name: str | None,
    ) -> list[str]:
        identifiers: list[str] = []
        seen: set[str] = set()
        for item in self._selected_interfaces(
            interfaces,
            stage=stage,
            search_name=search_name,
        ):
            record = self._interface(item)
            if not record.is_authoritative:
                raise ValueError(
                    "Structural relaxation requires authoritative persisted "
                    "interfaces; projections are not valid scientific targets."
                )
            if record.stage not in self._REFINED_STAGES:
                raise ValueError(
                    "Structural relaxation requires a strain_partitioned or "
                    f"registry_refined interface, got stage={record.stage!r}."
                )
            if search_name is not None:
                owner = record.metadata.get("search_name")
                if owner not in {None, search_name}:
                    raise ValueError(
                        f"Interface {record.uid_full or record.id_short!r} belongs "
                        f"to search {owner!r}, not {search_name!r}."
                    )
            if not record.uid_full:
                raise ValueError(
                    "Persisted relaxation target is missing its full interface UID."
                )
            if record.uid_full not in seen:
                identifiers.append(record.uid_full)
                seen.add(record.uid_full)
        if not identifiers:
            raise ValueError(
                "No authoritative refined interfaces were selected for relaxation."
            )
        return identifiers

    @staticmethod
    def _single_run_uid(rows: Any) -> str:
        run_uids = {
            str(row.get("run_uid"))
            for row in rows
            if isinstance(row, Mapping) and row.get("run_uid")
        }
        if len(run_uids) != 1:
            raise RuntimeError(
                "Relaxation stage did not return exactly one persistent run identity."
            )
        return next(iter(run_uids))

    def _relaxed_interfaces(self, run_uid: str) -> InterfaceCollection:
        rows: list[Any] = []
        for item in self._repo.list_interfaces(limit=None):
            record = self._interface(item)
            if record.stage != "relaxed":
                continue
            if str(record.metadata.get("source_run_uid") or "") != str(run_uid):
                continue
            rows.append(item)
        return InterfaceCollection(
            interfaces=rows,
            repo=self._repo,
            project=self._project,
        )

    @staticmethod
    def _failure_messages(records: Any) -> list[str]:
        return [
            record.failure.message for record in records if record.failure is not None
        ]

    def relax_interfaces(
        self,
        interfaces: Any | None = None,
        *,
        settings: Any | None = None,
        backend: Any = "real",
        resume: bool = True,
        partial_resume: bool = True,
        on_error: str = "raise",
        search_name: str | None = None,
        stage: str = "registry_refined",
        reporter: Any | None = None,
    ) -> RelaxationWorkflowResult:
        """Validate, execute, and assemble one structural-relaxation workflow."""

        self._validate_on_error(on_error)
        self._validate_stage(stage)
        self._validate_backend(backend)
        settings = settings or RelaxSettings()
        if not isinstance(settings, RelaxSettings):
            raise TypeError("settings must be a RelaxSettings instance.")
        settings.validate()

        target_ids = self._target_ids(
            interfaces,
            stage=stage,
            search_name=search_name,
        )
        stage_kwargs = settings.to_stage_kwargs()
        payload = dict(stage_kwargs["payload"])
        payload["public_api"] = "Project.relax_interfaces"

        rows = self.run_relaxation_stage(
            target_ids,
            protocol=stage_kwargs["protocol"],
            convergence=stage_kwargs["convergence"],
            max_steps=stage_kwargs["max_steps"],
            payload=payload,
            resume=resume,
            backend=backend,
            relax_cell=settings.relax_cell,
            partial_resume=partial_resume,
            reporter=reporter,
        )
        run_uid = self._single_run_uid(rows)
        run = ProjectRun.from_item(self._repo.get_run(run_uid))
        results = RelaxationResultCollection(
            self._repo.list_followup_results(
                run=run_uid,
                kind="relaxation_stage",
                limit=100000,
            )
        )
        relaxed = self._relaxed_interfaces(run_uid)
        workflow = RelaxationWorkflowResult(
            run=run,
            results=results,
            relaxed_interfaces=relaxed,
        )

        failures = list(results.failures().records())
        if failures and on_error == "raise":
            messages = self._failure_messages(failures)
            raise RuntimeError(
                "Structural relaxation failed after persisting the run and failure "
                "records: " + ("; ".join(messages) or "unknown backend failure")
            )
        if len(results) == 0 and on_error == "raise":
            raise RuntimeError(
                "Structural relaxation produced no persisted per-target results."
            )
        return workflow

    def run_relaxation_stage(
        self,
        prototypes: list[str],
        *,
        run_name: str | None = None,
        protocol: str = "ionic_positions_v1",
        convergence: dict | None = None,
        max_steps: int = 500,
        payload: dict | None = None,
        resume: bool = True,
        backend: Any | None = None,
        relax_cell: bool = False,
        partial_resume: bool = False,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
        reporter: Any | None = None,
    ) -> list[dict]:
        """Run the low-level synchronous relaxation-stage adapter."""

        self._validate_backend(backend)
        rep = ensure_console_reporter(reporter)
        with rep.stage(
            "run_relaxation_stage",
            n_prototypes=len(prototypes),
            run_name=run_name,
        ):
            rep.info(
                f"Running relaxation stage: protocol={protocol}, "
                f"max_steps={max_steps}, backend={backend}, "
                f"relax_cell={relax_cell}, resume={resume}"
            )
            try:
                results = self._workspace.run_relaxation_stage(
                    prototypes,
                    protocol=protocol,
                    convergence=convergence,
                    max_steps=max_steps,
                    run_name=run_name,
                    payload=payload,
                    resume=resume,
                    backend=backend,
                    relax_cell=relax_cell,
                    partial_resume=partial_resume,
                    campaign_uid_full=campaign_uid_full,
                    campaign_run_uid_full=campaign_run_uid_full,
                    reporter=rep,
                )
                results = expose_public_stage_targets(results)
                if not isinstance(results, (list, tuple)):
                    raise RuntimeError("Relaxation stage returned non-iterable results")
                try:
                    rep.mapping(
                        summarize_stage_results(results),
                        title="Relaxation stage summary",
                    )
                except Exception:
                    rep.info(f"Relaxation stage completed: n_results={len(results)}")
                return list(results)
            except Exception as exc:
                rep.warn(f"run_relaxation_stage failed: {exc}")
                raise RuntimeError(f"run_relaxation_stage failed: {exc}") from exc
