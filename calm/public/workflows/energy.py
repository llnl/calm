"""Internal orchestration owner for public energy workflows.

The :class:`~calm.public.project.Project` facade delegates raw-energy,
reference-energy, and thermodynamic workflow composition to this service.
Scientific stage execution and persistence remain owned by the existing
Workspace follow-up orchestrators; this module owns only public target
normalization, workflow sequencing, failure policy, and typed result assembly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from calm.public.presentation.reporting import ensure_console_reporter

from calm.public.records.followups import (
    EnergyWorkflowResult,
    ReferenceEnergyWorkflowResult,
)
from calm.public.collections.persistence import (
    EnergyResultCollection,
    ReferenceEnergyResultCollection,
    ThermodynamicResultCollection,
)
from calm.public.records.persistence import ProjectInterface, ProjectRun
from calm.public.presentation.stage import summarize_stage_results
from calm.public.inputs.settings import (
    EnergyConvention,
    EnergySettings,
    ReferenceEnergySettings,
    RelaxSettings,
)


class _EnergyWorkspace(Protocol):
    def run_energy_stage(self, prototypes: list[str], **kwargs: Any) -> list[dict]: ...

    def run_reference_energy_stage(
        self,
        interfaces: list[str],
        **kwargs: Any,
    ) -> list[dict]: ...

    def run_thermodynamic_stage(
        self,
        raw_energy_results: list[str],
        **kwargs: Any,
    ) -> list[dict]: ...


class _EnergyRepository(Protocol):
    def list_interfaces(
        self,
        *,
        search_name: str | None = None,
        limit: int | None = None,
    ) -> list[Any]: ...

    def get_interface(self, identifier: str) -> Any: ...

    def get_run(self, identifier: str) -> Any: ...

    def list_followup_results(self, **kwargs: Any) -> list[Any]: ...


class ProjectEnergyWorkflowService:
    """Coordinate the public energy workflows over authoritative records."""

    def __init__(
        self,
        *,
        workspace: _EnergyWorkspace,
        repository: _EnergyRepository,
    ) -> None:
        self._workspace = workspace
        self._repo = repository

    @staticmethod
    def _validate_on_error(on_error: str) -> None:
        if on_error not in {"raise", "record"}:
            raise ValueError("on_error must be 'raise' or 'record'.")

    @staticmethod
    def _validate_backend(backend: Any, *, reference: bool) -> None:
        if isinstance(backend, str) or callable(getattr(backend, "identity", None)):
            return
        if reference:
            raise TypeError(
                "Custom reference-energy backends must implement "
                "identity(targets=..., uow=...)."
            )
        raise TypeError(
            "Custom energy backends used by Project.evaluate_energies must "
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
        search_name: str | None,
    ) -> list[Any]:
        if interfaces is None:
            return [
                row
                for row in self._repo.list_interfaces(search_name=search_name)
                if self._interface(row).stage == "relaxed"
            ]
        if isinstance(interfaces, str):
            return [interfaces]
        if hasattr(interfaces, "records"):
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
        search_name: str | None,
    ) -> list[str]:
        identifiers: list[str] = []
        seen: set[str] = set()
        for item in self._selected_interfaces(
            interfaces,
            search_name=search_name,
        ):
            record = self._interface(item)
            if not record.is_authoritative:
                raise ValueError(
                    "Energy evaluation requires authoritative persisted interfaces."
                )
            if record.stage != "relaxed":
                raise ValueError(
                    "The public energy workflow requires relaxed interfaces; "
                    f"got stage={record.stage!r}."
                )
            if not record.uid_full:
                raise ValueError(
                    "Persisted energy target is missing its full interface UID."
                )
            if record.uid_full not in seen:
                identifiers.append(record.uid_full)
                seen.add(record.uid_full)
        if not identifiers:
            raise ValueError("No authoritative relaxed interfaces were selected.")
        return identifiers

    @staticmethod
    def _single_run_uid(rows: Any, *, error_message: str) -> str:
        run_uids = {
            str(row.get("run_uid"))
            for row in rows
            if isinstance(row, Mapping) and row.get("run_uid")
        }
        if len(run_uids) != 1:
            raise RuntimeError(error_message)
        return next(iter(run_uids))

    @staticmethod
    def _failure_messages(records: Any) -> list[str]:
        return [
            record.failure.message for record in records if record.failure is not None
        ]

    def _run(self, identifier: str) -> ProjectRun:
        return ProjectRun.from_item(self._repo.get_run(identifier))

    def evaluate_reference_energies(
        self,
        interfaces: Any | None = None,
        *,
        convention: Any,
        settings: Any | None = None,
        surface_relaxation: Any | None = None,
        backend: Any = "real",
        resume: bool = True,
        partial_resume: bool = True,
        on_error: str = "raise",
        search_name: str | None = None,
        reporter: Any | None = None,
    ) -> ReferenceEnergyWorkflowResult:
        """Validate, execute, and assemble one reference-energy workflow."""

        self._validate_on_error(on_error)
        if not isinstance(convention, EnergyConvention):
            raise TypeError("convention must be an EnergyConvention instance.")
        convention.validate()
        convention.reference_capability().raise_for_calculated_references()

        settings = settings or EnergySettings()
        if not isinstance(settings, EnergySettings):
            raise TypeError("settings must be an EnergySettings instance.")
        settings.validate()

        if convention.formula == "work_of_adhesion_relaxed_surfaces":
            surface_relaxation = surface_relaxation or RelaxSettings()
            if not isinstance(surface_relaxation, RelaxSettings):
                raise TypeError("surface_relaxation must be a RelaxSettings instance.")
            surface_relaxation.validate()
            if surface_relaxation.relax_cell:
                raise ValueError(
                    "Relaxed isolated-surface references require fixed-cell "
                    "surface relaxation."
                )
        elif surface_relaxation is not None:
            raise ValueError(
                "surface_relaxation is used only with "
                "work_of_adhesion_relaxed_surfaces."
            )
        self._validate_backend(backend, reference=True)

        target_ids = self._target_ids(interfaces, search_name=search_name)
        stage_kwargs = settings.to_stage_kwargs()
        calculation = dict(stage_kwargs["calculation"])
        if surface_relaxation is not None:
            calculation["reference_relaxation"] = surface_relaxation.to_dict()
        payload: dict[str, Any] = {}
        payload["public_api"] = "Project.evaluate_reference_energies"
        if search_name is not None:
            payload["search_name"] = search_name

        rep = ensure_console_reporter(reporter)
        with rep.stage(
            "evaluate_reference_energies",
            n_interfaces=len(target_ids),
            formula=convention.formula,
        ):
            rows = self._workspace.run_reference_energy_stage(
                target_ids,
                formula=convention.formula,
                backend=backend,
                calculation=calculation,
                payload=payload,
                resume=resume,
                partial_resume=partial_resume,
            )

        run_uid = self._single_run_uid(
            rows,
            error_message=(
                "Reference-energy evaluation did not return exactly one "
                "authoritative run identity."
            ),
        )
        run = self._run(run_uid)
        results = ReferenceEnergyResultCollection(
            self._repo.list_followup_results(
                run=run_uid,
                kind="reference_energy",
                limit=100000,
            )
        )
        failures = list(results.failures().records())
        if failures and on_error == "raise":
            messages = self._failure_messages(failures)
            raise RuntimeError(
                "Reference-energy evaluation failed after persisting failure records: "
                + ("; ".join(messages) or "unknown backend failure")
            )
        if len(results) == 0 and on_error == "raise":
            raise RuntimeError(
                "Reference-energy evaluation produced no persisted results."
            )

        workflow = ReferenceEnergyWorkflowResult(
            run=run,
            results=results,
            convention=convention,
        )
        if on_error == "raise":
            workflow.reference_map()
        return workflow

    @staticmethod
    def _reference_payload(
        *,
        convention: Any | None,
        references: Any | None,
    ) -> tuple[EnergyConvention | None, dict[str, Any] | None]:
        if (convention is None) != (references is None):
            raise ValueError(
                "convention and references must either both be provided or both be omitted."
            )
        if convention is None:
            return None, None
        if not isinstance(convention, EnergyConvention):
            raise TypeError("convention must be an EnergyConvention instance.")
        convention.validate()

        if isinstance(references, ReferenceEnergyWorkflowResult):
            if str(references.convention.formula) != str(convention.formula):
                raise ValueError(
                    "The reference-energy workflow formula does not match the "
                    "requested thermodynamic convention."
                )
            return convention, references.to_thermodynamic_payload()
        if isinstance(references, ReferenceEnergySettings):
            references.validate_for(convention)
            return convention, references.to_dict()
        raise TypeError(
            "references must be ReferenceEnergySettings or a "
            "ReferenceEnergyWorkflowResult."
        )

    def evaluate_energies(
        self,
        interfaces: Any | None = None,
        *,
        settings: Any | None = None,
        backend: Any = "real",
        convention: Any | None = None,
        references: Any | None = None,
        resume: bool = True,
        partial_resume: bool = True,
        on_error: str = "raise",
        search_name: str | None = None,
        reporter: Any | None = None,
    ) -> EnergyWorkflowResult:
        """Validate, execute, and assemble raw and derived energy workflows."""

        self._validate_on_error(on_error)
        self._validate_backend(backend, reference=False)
        settings = settings or EnergySettings()
        if not isinstance(settings, EnergySettings):
            raise TypeError("settings must be an EnergySettings instance.")
        settings.validate()
        convention, reference_payload = self._reference_payload(
            convention=convention,
            references=references,
        )

        target_ids = self._target_ids(interfaces, search_name=search_name)
        stage_kwargs = settings.to_stage_kwargs()
        payload: dict[str, Any] = {}
        payload["public_api"] = "Project.evaluate_energies"
        if search_name is not None:
            payload["search_name"] = search_name

        rows = self.run_energy_stage(
            target_ids,
            backend=backend,
            calculation=stage_kwargs["calculation"],
            payload=payload,
            resume=resume,
            partial_resume=partial_resume,
            reporter=reporter,
        )
        energy_run_uid = self._single_run_uid(
            rows,
            error_message=(
                "Energy evaluation did not return exactly one authoritative "
                "run identity."
            ),
        )
        energy_run = self._run(energy_run_uid)
        energy_results = EnergyResultCollection(
            self._repo.list_followup_results(
                run=energy_run_uid,
                kind="energy_stage",
                limit=100000,
            )
        )
        raw_failures = list(energy_results.failures().records())
        if raw_failures and on_error == "raise":
            messages = self._failure_messages(raw_failures)
            raise RuntimeError(
                "Raw energy evaluation failed after persisting failure records: "
                + ("; ".join(messages) or "unknown backend failure")
            )
        if len(energy_results) == 0 and on_error == "raise":
            raise RuntimeError("Energy evaluation produced no persisted results.")

        thermodynamic_run = None
        thermodynamic_results = None
        if convention is not None and reference_payload is not None:
            completed_raw = list(energy_results.completed().records())
            if not completed_raw:
                if on_error == "raise":
                    raise RuntimeError(
                        "No completed raw energies are available for thermodynamic derivation."
                    )
            else:
                thermo_rows = self._workspace.run_thermodynamic_stage(
                    [record.uid_full for record in completed_raw if record.uid_full],
                    convention=convention.to_dict(),
                    references=reference_payload,
                    resume=resume,
                    partial_resume=partial_resume,
                )
                thermo_run_uid = self._single_run_uid(
                    thermo_rows,
                    error_message=(
                        "Thermodynamic derivation did not return exactly one "
                        "run identity."
                    ),
                )
                thermodynamic_run = self._run(thermo_run_uid)
                thermodynamic_results = ThermodynamicResultCollection(
                    self._repo.list_followup_results(
                        run=thermo_run_uid,
                        kind="thermodynamic_quantity",
                        limit=100000,
                    )
                )
                thermo_failures = list(thermodynamic_results.failures().records())
                if thermo_failures and on_error == "raise":
                    messages = self._failure_messages(thermo_failures)
                    raise RuntimeError(
                        "Thermodynamic derivation failed after persisting failure records: "
                        + ("; ".join(messages) or "unknown derivation failure")
                    )

        return EnergyWorkflowResult(
            energy_run=energy_run,
            energy_results=energy_results,
            thermodynamic_run=thermodynamic_run,
            thermodynamic_results=thermodynamic_results,
        )

    def run_energy_stage(
        self,
        prototypes: list[str],
        *,
        run_name: str | None = None,
        backend: Any | None = None,
        calculation: dict | None = None,
        payload: dict | None = None,
        resume: bool = True,
        partial_resume: bool = False,
        campaign_uid_full: str | None = None,
        campaign_run_uid_full: str | None = None,
        reporter: Any | None = None,
    ) -> list[dict]:
        """Run the low-level synchronous raw-energy stage adapter."""

        rep = ensure_console_reporter(reporter)
        with rep.stage(
            "run_energy_stage",
            n_prototypes=len(prototypes),
            run_name=run_name,
        ):
            rep.info(
                "Running energy stage: "
                f"backend={backend}, resume={resume}, "
                f"partial_resume={partial_resume}"
            )
            try:
                results = self._workspace.run_energy_stage(
                    prototypes,
                    backend=backend,
                    calculation=calculation,
                    run_name=run_name,
                    payload=payload,
                    resume=resume,
                    partial_resume=partial_resume,
                    campaign_uid_full=campaign_uid_full,
                    campaign_run_uid_full=campaign_run_uid_full,
                )
                from calm.public.projections.stage import expose_public_stage_targets

                results = expose_public_stage_targets(results)
                if not isinstance(results, (list, tuple)):
                    raise RuntimeError("Energy stage returned non-iterable results")
                try:
                    rep.mapping(
                        summarize_stage_results(results),
                        title="Energy stage summary",
                    )
                except Exception:
                    rep.info(f"Energy stage completed: n_results={len(results)}")
                return list(results)
            except Exception as exc:
                rep.warn(f"run_energy_stage failed: {exc}")
                raise RuntimeError(f"run_energy_stage failed: {exc}") from exc
