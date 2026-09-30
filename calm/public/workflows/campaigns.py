"""Internal composition owner for public campaign workflows.

The :class:`~calm.public.project.Project` facade delegates deterministic
campaign creation, execution, reuse, stage sequencing, provenance, and typed
result assembly to this service. Scientific stage execution remains owned by
the existing search, build, refinement, relaxation, energy, dataset, and
application-layer persistence owners.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from calm.project.domain.contracts.campaign import (
    CAMPAIGN_SPEC_VERSION,
    CampaignIdentityConflictError,
    campaign_spec_equal,
    canonical_campaign_name,
    validate_typed_campaign_spec,
)
from calm.project.domain.identity_v2 import (
    campaign_identity_payload,
    persisted_entity_uid_v2,
)

from calm.public.inputs.campaigns import (
    CampaignCase,
    CampaignCaseResult,
    CampaignSettings,
    CampaignWorkflowResult,
)
from calm.public.records.persistence import ProjectCampaign, ProjectCampaignRun


class ProjectCampaignWorkflowService:
    """Compose public campaign lifecycle and synchronous case execution."""

    def __init__(
        self,
        *,
        project: Any,
        workspace: Any,
        repository: Any,
        search_workflows: Any,
        interface_builds: Any,
        interface_refinements: Any,
        relaxation_workflows: Any,
        energy_workflows: Any,
        dataset_workflows: Any,
    ) -> None:
        self._project = project
        self._adapter = workspace
        self._repo = repository
        self._searches = search_workflows
        self._builds = interface_builds
        self._refinements = interface_refinements
        self._relaxations = relaxation_workflows
        self._energies = energy_workflows
        self._datasets = dataset_workflows

    def create_campaign(
        self,
        *,
        name: str | None = None,
        spec: dict | None = None,
        cases: Any | None = None,
        settings: Any | None = None,
    ) -> ProjectCampaign:
        """Create or reopen one deterministic authoritative campaign."""

        if name is None:
            raise ValueError("Campaign name must be non-empty.")
        exact_name = canonical_campaign_name(name)
        if spec is not None and (cases is not None or settings is not None):
            raise ValueError("spec cannot be combined with cases or settings.")
        if spec is None:
            typed_settings = settings or CampaignSettings()
            if not isinstance(typed_settings, CampaignSettings):
                raise TypeError("settings must be a CampaignSettings instance.")
            typed_settings.validate()
            typed_cases = tuple(cases or ())
            if not typed_cases:
                raise ValueError("A typed campaign requires at least one CampaignCase.")
            if not all(isinstance(case, CampaignCase) for case in typed_cases):
                raise TypeError("cases must contain only CampaignCase instances.")
            for case in typed_cases:
                case.validate()
            case_names = [case.name for case in typed_cases]
            if len(case_names) != len(set(case_names)):
                raise ValueError("Campaign case names must be unique.")
            declared_searches: dict[str, tuple[str, str, dict[str, Any]]] = {}
            for case in typed_cases:
                if case.surface_a is None or case.surface_b is None:
                    continue
                declaration = (
                    case.surface_a,
                    case.surface_b,
                    case.search_settings.to_dict(),
                )
                previous = declared_searches.get(case.search_name)
                if previous is not None and previous != declaration:
                    raise ValueError(
                        "Campaign cases may share a search name only when their "
                        "exact surfaces and search settings are identical."
                    )
                declared_searches[case.search_name] = declaration
            resolved_spec = {
                "identity_version": CAMPAIGN_SPEC_VERSION,
                "cases": [case.to_dict() for case in typed_cases],
                "settings": typed_settings.to_dict(),
            }
            validate_typed_campaign_spec(resolved_spec)
        else:
            resolved_spec = dict(spec)

        uid_full = persisted_entity_uid_v2(
            "campaign",
            campaign_identity_payload(name=exact_name, spec=resolved_spec),
        )
        try:
            existing_item = self._repo.get_campaign(exact_name)
        except KeyError:
            existing_item = None
        if existing_item is not None:
            existing = ProjectCampaign.from_item(existing_item, project=self._project)
            if existing.uid_full != uid_full or not campaign_spec_equal(
                existing.spec, resolved_spec
            ):
                raise CampaignIdentityConflictError(
                    f"Campaign name {exact_name!r} is already bound to a different specification."
                )
            return existing

        try:
            row = self._adapter.create_campaign(
                name=exact_name,
                spec=resolved_spec,
                uid_full=uid_full,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to create campaign: {exc}") from exc
        return ProjectCampaign.from_item(row, project=self._project)

    def run_campaign(
        self,
        campaign: Any,
        *,
        resume: bool = True,
        export_root: str | Path | None = None,
        reporter: Any | None = None,
    ) -> CampaignWorkflowResult:
        """Run or reuse one first-class campaign synchronously."""

        supplied = campaign if isinstance(campaign, ProjectCampaign) else None
        if supplied is not None:
            bound_project = getattr(supplied, "_project", None)
            if bound_project is not None and bound_project is not self._project:
                raise ValueError("The campaign belongs to another Project.")
            selector = supplied.uid_full or supplied.id_short or supplied.name
            if not selector:
                raise ValueError("The campaign record has no durable selector.")
        else:
            selector = str(campaign).strip()
            if not selector:
                raise ValueError("Campaign selectors must be non-empty.")
        record = ProjectCampaign.from_item(
            self._repo.get_campaign(str(selector)),
            project=self._project,
        )
        if supplied is not None:
            for field in ("uid_full", "name"):
                expected = getattr(supplied, field, None)
                actual = getattr(record, field, None)
                if expected not in (None, "") and actual not in (None, ""):
                    if str(expected) != str(actual):
                        raise ValueError(
                            "The campaign record does not match this Project's "
                            f"authoritative {field}."
                        )
            if not campaign_spec_equal(supplied.spec, record.spec):
                raise ValueError(
                    "The campaign record does not match this Project's "
                    "authoritative specification."
                )
        campaign_uid = record.uid_full
        if not campaign_uid:
            raise RuntimeError(
                "Campaign execution requires an authoritative campaign UID."
            )
        run_spec = {
            "campaign_uid_full": campaign_uid,
            "campaign_spec": dict(record.spec),
            "execution_contract": "synchronous_campaign_v2",
        }
        run_row = self._adapter.create_or_get_campaign_run(
            campaign_uid,
            run_spec=run_spec,
            backend_id="synchronous",
            status="pending",
        )
        run = ProjectCampaignRun.from_item(run_row)
        if resume and run.status == "completed":
            return self.reused_campaign_result(record, run)
        try:
            updated = self._adapter.mark_campaign_run(run.uid_full, status="running")
            run = ProjectCampaignRun.from_item(updated)
            result = self.execute_campaign(
                record,
                run,
                resume=resume,
                export_root=export_root,
                reporter=reporter,
            )
            final = self._adapter.mark_campaign_run(
                run.uid_full,
                status=result.status,
            )
            return CampaignWorkflowResult(
                campaign=record,
                run=ProjectCampaignRun.from_item(final),
                cases=result.cases,
                status=result.status,
                reused=False,
            )
        except Exception:
            try:
                self._adapter.mark_campaign_run(run.uid_full, status="failed")
            except Exception:
                pass
            raise

    def execute_campaign(
        self,
        campaign: Any,
        campaign_run: Any,
        *,
        resume: bool = True,
        export_root: str | Path | None = None,
        reporter: Any | None = None,
    ) -> CampaignWorkflowResult:
        """Execute one persisted campaign in canonical stage order."""
        return _execute_campaign(
            self,
            campaign,
            campaign_run,
            resume=resume,
            export_root=export_root,
            reporter=reporter,
        )

    def reused_campaign_result(
        self,
        campaign: Any,
        campaign_run: Any,
    ) -> CampaignWorkflowResult:
        """Reconstruct one completed campaign from persisted case edges."""
        return _reused_campaign_result(self, campaign, campaign_run)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in (
            "uid_full",
            "project_interface_uid",
            "project_dataset_uid",
            "run_uid_full",
            "id_short",
        ):
            item = value.get(key)
            if item:
                return str(item)
    for key in (
        "uid_full",
        "project_interface_uid",
        "project_dataset_uid",
        "run_uid_full",
        "id_short",
    ):
        item = getattr(value, key, None)
        if item:
            return str(item)
    return None


def _count(value: Any) -> int:
    try:
        return len(value)
    except Exception:
        return 0


def _records(value: Any) -> list[Any]:
    if value is None:
        return []
    records = getattr(value, "records", None)
    if callable(records):
        return list(records())
    try:
        return list(value)
    except TypeError:
        return []


def _value(item: Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item.get(name)
    return getattr(item, name, None)


def _numeric_summary(value: Any, *, field_name: str, prefix: str) -> dict[str, Any]:
    values = [
        float(item_value)
        for item in _records(value)
        if _is_number(item_value := _value(item, field_name))
    ]
    if not values:
        return {}
    return {
        f"{prefix}_min": min(values),
        f"{prefix}_mean": sum(values) / len(values),
        f"{prefix}_max": max(values),
    }


def _persist_case_result(
    owner: "ProjectCampaignWorkflowService",
    *,
    campaign: Any,
    campaign_run: Any,
    result: CampaignCaseResult,
) -> None:
    _link(
        owner,
        src=campaign,
        dst=campaign_run,
        kind="campaign_case_result",
        payload=result.to_persisted_payload(),
    )


def _link(
    owner: "ProjectCampaignWorkflowService",
    *,
    src: Any,
    dst: Any,
    kind: str,
    payload: Mapping[str, Any],
) -> None:
    src_uid = _identifier(src)
    dst_uid = _identifier(dst)
    if not src_uid or not dst_uid:
        return
    try:
        owner._adapter.add_provenance_edge(
            src_uid_full=src_uid,
            dst_uid_full=dst_uid,
            kind=kind,
            payload=dict(payload),
        )
    except AttributeError:
        return


def _surface_request(owner: "ProjectCampaignWorkflowService", identifier: str) -> Any:
    surface = owner._project.surface(identifier)
    converter = getattr(surface, "to_surface", None)
    return converter() if callable(converter) else surface


def _resolve_search(
    owner: "ProjectCampaignWorkflowService",
    case: CampaignCase,
    *,
    resume: bool,
    reporter: Any,
) -> Any:
    try:
        existing = owner._searches.search(case.search_name)
    except KeyError:
        existing = None
    if case.surface_a is None or case.surface_b is None:
        if existing is None:
            raise KeyError(
                f"Campaign case {case.name!r} references missing search "
                f"{case.search_name!r} and does not provide exact surfaces."
            )
        return existing
    return owner._searches.search_interfaces(
        _surface_request(owner, case.surface_a),
        _surface_request(owner, case.surface_b),
        settings=case.search_settings,
        name=case.search_name,
        resume=resume,
        on_error="raise",
        reporter=reporter,
    )


def _case_label_prefix(campaign: Any, case: CampaignCase) -> str:
    campaign_name = getattr(campaign, "name", None) or _identifier(campaign)
    return f"{campaign_name}__{case.name}"


def _case_built_interfaces(
    search: Any,
    *,
    label_prefix: str,
    count: int,
) -> tuple[Any, ...]:
    interfaces = search.interfaces()
    selected: list[Any] = []
    for index in range(int(count)):
        item = interfaces.one_or_none(
            label=f"{label_prefix}_built_{index:04d}",
            stage="built",
            authority="authoritative",
        )
        if item is None:
            return ()
        selected.append(item)
    return tuple(selected)


def _case_refined_interfaces(
    owner: "ProjectCampaignWorkflowService",
    case: CampaignCase,
    *,
    label_prefix: str,
) -> Any:
    return owner._project.refined_interfaces(
        stage="registry_refined",
        search_name=case.search_name,
    ).where(label=f"{label_prefix}_registry_refined")


def _execute_campaign(
    owner: "ProjectCampaignWorkflowService",
    campaign: Any,
    campaign_run: Any,
    *,
    resume: bool = True,
    export_root: str | Path | None = None,
    reporter: Any | None = None,
) -> CampaignWorkflowResult:
    """Execute one persisted campaign synchronously in canonical stage order."""

    from calm.public.presentation.reporting import ensure_console_reporter

    rep = ensure_console_reporter(reporter)
    spec = dict(getattr(campaign, "spec", {}) or {})
    cases = tuple(CampaignCase.from_dict(row) for row in spec.get("cases", []))
    settings = CampaignSettings.from_dict(dict(spec.get("settings") or {}))
    settings.validate()
    run_uid = _identifier(campaign_run)
    campaign_uid = _identifier(campaign)
    if not run_uid or not campaign_uid:
        raise RuntimeError(
            "Campaign execution requires authoritative campaign identities."
        )

    case_results: list[CampaignCaseResult] = []
    any_failed = False
    any_skipped = False
    with rep.section(f"Run campaign: {getattr(campaign, 'name', campaign_uid)}"):
        for case in cases:
            case_settings = case.resolved_settings(settings)
            label_prefix = _case_label_prefix(campaign, case)
            stage_rows: dict[str, Any] = {}
            dataset = None
            export_path = None
            try:
                search = _resolve_search(
                    owner,
                    case,
                    resume=resume,
                    reporter=rep,
                )
                if "search" in case_settings.canonical_stages:
                    status = search.status()
                    stage_rows["search"] = status
                    search_run_uid = status.get("run_uid")
                    if search_run_uid:
                        _link(
                            owner,
                            src={"uid_full": search_run_uid},
                            dst=campaign_run,
                            kind="run_of_campaign_execution",
                            payload={"case": case.name, "stage": "search"},
                        )

                built = None
                if "build" in case_settings.canonical_stages:
                    existing_built = _case_built_interfaces(
                        search,
                        label_prefix=label_prefix,
                        count=case_settings.build_top,
                    )
                    if resume and len(existing_built) == case_settings.build_top:
                        built = existing_built
                        build_reused = True
                    else:
                        built = owner._builds.build_interfaces(
                            case.search_name,
                            top=case_settings.build_top,
                            settings=case_settings.build_settings,
                            name_prefix=f"{label_prefix}_built",
                            reporter=rep,
                        )
                        build_reused = False
                    stage_rows["build"] = {
                        "reused": build_reused,
                        "n_interfaces": _count(built),
                    }
                    for item in _records(built):
                        _link(
                            owner,
                            src=item,
                            dst=campaign_run,
                            kind="produced_by_campaign_run",
                            payload={"case": case.name, "stage": "build"},
                        )

                refined = None
                if "refine" in case_settings.canonical_stages:
                    existing_refined = _case_refined_interfaces(
                        owner,
                        case,
                        label_prefix=label_prefix,
                    )
                    expected_refined = (
                        _count(built) if built is not None else case_settings.build_top
                    )
                    if resume and _count(existing_refined) >= expected_refined:
                        refined = existing_refined
                        stage_rows["refine"] = {
                            "reused": True,
                            "n_registry_refined": _count(refined),
                        }
                    else:
                        refinement_kwargs: dict[str, Any] = {
                            "strain_settings": case_settings.strain_settings,
                            "registry_settings": case_settings.registry_settings,
                            "pareto": True,
                            "label_prefix": label_prefix,
                            "on_error": "raise",
                            "reporter": rep,
                        }
                        if built is not None:
                            refinement_kwargs["interfaces"] = built
                        else:
                            refinement_kwargs["top"] = case_settings.build_top
                        refinement = owner._refinements.refine_interfaces(
                            case.search_name,
                            **refinement_kwargs,
                        )
                        if not refinement.ok:
                            raise RuntimeError(
                                "Campaign refinement did not produce a complete "
                                f"result: {', '.join(refinement.issues)}"
                            )
                        refined = refinement.interfaces(stage="registry_refined")
                        stage_rows["refine"] = {
                            "reused": False,
                            "n_registry_refined": _count(refined),
                        }
                        for wrapper in (
                            refinement.strain_scan,
                            refinement.registry_run,
                        ):
                            run = getattr(wrapper, "run", None)
                            if run is not None:
                                _link(
                                    owner,
                                    src=run,
                                    dst=campaign_run,
                                    kind="run_of_campaign_execution",
                                    payload={"case": case.name, "stage": "refine"},
                                )
                    for item in _records(refined):
                        _link(
                            owner,
                            src=item,
                            dst=campaign_run,
                            kind="produced_by_campaign_run",
                            payload={"case": case.name, "stage": "refine"},
                        )

                relaxation = None
                if "relax" in case_settings.canonical_stages:
                    if refined is not None:
                        relaxation = owner._relaxations.relax_interfaces(
                            refined,
                            settings=case_settings.relax_settings,
                            backend=case_settings.relax_backend,
                            resume=resume,
                            partial_resume=True,
                            on_error="raise",
                            reporter=rep,
                        )
                    else:
                        relaxation = owner._relaxations.relax_interfaces(
                            settings=case_settings.relax_settings,
                            search_name=case.search_name,
                            backend=case_settings.relax_backend,
                            resume=resume,
                            partial_resume=True,
                            on_error="raise",
                            reporter=rep,
                        )
                    stage_rows["relax"] = {
                        "run_uid": _identifier(relaxation.run),
                        "n_results": _count(relaxation.results),
                        "n_relaxed_interfaces": _count(relaxation.relaxed_interfaces),
                    }
                    _link(
                        owner,
                        src=relaxation.run,
                        dst=campaign_run,
                        kind="run_of_campaign_execution",
                        payload={"case": case.name, "stage": "relax"},
                    )

                energy = None
                if "energy" in case_settings.canonical_stages:
                    energy_targets = (
                        relaxation.relaxed_interfaces
                        if relaxation is not None
                        else None
                    )
                    references: Any = case_settings.energy_references
                    if (
                        case_settings.energy_convention is not None
                        and references is None
                    ):
                        if energy_targets is not None:
                            reference_energy = (
                                owner._energies.evaluate_reference_energies(
                                    energy_targets,
                                    convention=case_settings.energy_convention,
                                    settings=case_settings.energy_settings,
                                    backend=case_settings.energy_backend,
                                    resume=resume,
                                    partial_resume=True,
                                    on_error="raise",
                                    reporter=rep,
                                )
                            )
                        else:
                            reference_energy = (
                                owner._energies.evaluate_reference_energies(
                                    convention=case_settings.energy_convention,
                                    search_name=case.search_name,
                                    settings=case_settings.energy_settings,
                                    backend=case_settings.energy_backend,
                                    resume=resume,
                                    partial_resume=True,
                                    on_error="raise",
                                    reporter=rep,
                                )
                            )
                        references = reference_energy
                        stage_rows["reference_energy"] = {
                            "run_uid": _identifier(reference_energy.run),
                            "n_results": _count(reference_energy.results),
                        }
                        _link(
                            owner,
                            src=reference_energy.run,
                            dst=campaign_run,
                            kind="run_of_campaign_execution",
                            payload={"case": case.name, "stage": "reference_energy"},
                        )

                    if energy_targets is not None:
                        energy = owner._energies.evaluate_energies(
                            energy_targets,
                            settings=case_settings.energy_settings,
                            backend=case_settings.energy_backend,
                            convention=case_settings.energy_convention,
                            references=references,
                            resume=resume,
                            partial_resume=True,
                            on_error="raise",
                            reporter=rep,
                        )
                    else:
                        energy = owner._energies.evaluate_energies(
                            settings=case_settings.energy_settings,
                            search_name=case.search_name,
                            backend=case_settings.energy_backend,
                            convention=case_settings.energy_convention,
                            references=references,
                            resume=resume,
                            partial_resume=True,
                            on_error="raise",
                            reporter=rep,
                        )
                    energy_stage = {
                        "raw_run_uid": _identifier(energy.energy_run),
                        "n_raw_results": _count(energy.energy_results),
                        "thermodynamic_run_uid": _identifier(energy.thermodynamic_run),
                        "n_thermodynamic_results": _count(energy.thermodynamic_results),
                    }
                    energy_stage.update(
                        _numeric_summary(
                            energy.energy_results,
                            field_name="energy_eV",
                            prefix="raw_eV",
                        )
                    )
                    energy_stage.update(
                        _numeric_summary(
                            energy.thermodynamic_results,
                            field_name="value_eV_per_A2",
                            prefix="thermodynamic_eV_per_A2",
                        )
                    )
                    energy_stage.update(
                        _numeric_summary(
                            energy.thermodynamic_results,
                            field_name="value_J_per_m2",
                            prefix="thermodynamic_J_per_m2",
                        )
                    )
                    stage_rows["energy"] = energy_stage
                    for run in (energy.energy_run, energy.thermodynamic_run):
                        if run is not None:
                            _link(
                                owner,
                                src=run,
                                dst=campaign_run,
                                kind="run_of_campaign_execution",
                                payload={"case": case.name, "stage": "energy"},
                            )

                if "dataset" in case_settings.canonical_stages:
                    if energy is None:
                        raise RuntimeError(
                            "Campaign dataset stage requires energy results from the "
                            "same execution."
                        )
                    sources = (
                        energy.thermodynamic_results
                        if energy.thermodynamic_results is not None
                        else energy.energy_results
                    )
                    dataset_name = case.dataset_name or (
                        case_settings.dataset_name_template.format(
                            campaign=str(getattr(campaign, "name", campaign_uid)),
                            case=case.name,
                        )
                    )
                    dataset = owner._datasets.create_dataset(
                        dataset_name,
                        sources,
                        settings=case_settings.resolved_dataset_settings,
                        description=(
                            f"Campaign dataset for {case.name} in "
                            f"{getattr(campaign, 'name', campaign_uid)}"
                        ),
                        tags=[
                            "campaign",
                            str(getattr(campaign, "name", campaign_uid)),
                            *(
                                f"{key}:{value}"
                                for key, value in sorted(case.dimensions.items())
                            ),
                        ],
                    )
                    _link(
                        owner,
                        src=dataset,
                        dst=campaign_run,
                        kind="produced_by",
                        payload={"case": case.name, "stage": "dataset"},
                    )
                    _link(
                        owner,
                        src=dataset,
                        dst=campaign,
                        kind="belonged_to_campaign",
                        payload={"case": case.name},
                    )
                    stage_rows["dataset"] = {
                        "dataset_uid": _identifier(dataset),
                        "n_items": _count(dataset.items()),
                    }
                    if export_root is not None:
                        destination = Path(export_root) / dataset_name
                        export_result = dataset.export(
                            destination,
                            manifest_format="json",
                            include_structures=True,
                            overwrite=True,
                        )
                        export_path = Path(
                            getattr(export_result, "destination", destination)
                        )

                case_result = CampaignCaseResult(
                    case=case,
                    status="completed",
                    stages=stage_rows,
                    dataset=dataset,
                    export_path=(Path(export_path) if export_path else None),
                )
                _persist_case_result(
                    owner,
                    campaign=campaign,
                    campaign_run=campaign_run,
                    result=case_result,
                )
                case_results.append(case_result)
            except Exception as exc:
                any_failed = True
                failure = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "module": type(exc).__module__,
                }
                if case_settings.on_error == "skip":
                    any_skipped = True
                    case_status = "skipped"
                else:
                    case_status = "failed"
                case_result = CampaignCaseResult(
                    case=case,
                    status=case_status,
                    stages=stage_rows,
                    dataset=dataset,
                    export_path=(Path(export_path) if export_path else None),
                    failure=failure,
                )
                _persist_case_result(
                    owner,
                    campaign=campaign,
                    campaign_run=campaign_run,
                    result=case_result,
                )
                case_results.append(case_result)
                if case_settings.on_error == "raise":
                    raise

    status = "completed"
    if any_failed:
        if any(result.status == "completed" for result in case_results):
            status = "partial"
        elif all(result.status == "skipped" for result in case_results):
            status = "skipped"
        else:
            status = "failed"
    elif any_skipped:
        status = "partial"
    return CampaignWorkflowResult(
        campaign=campaign,
        run=campaign_run,
        cases=tuple(case_results),
        status=status,
        reused=False,
    )


def _reused_campaign_result(
    owner: "ProjectCampaignWorkflowService",
    campaign: Any,
    campaign_run: Any,
) -> CampaignWorkflowResult:
    """Reconstruct a completed campaign result from exact persisted case edges."""

    spec = dict(getattr(campaign, "spec", {}) or {})
    cases = tuple(CampaignCase.from_dict(row) for row in spec.get("cases", []))
    run_uid = _identifier(campaign_run)
    campaign_uid = _identifier(campaign)
    repo = owner._repo
    if repo is None or not run_uid or not campaign_uid:
        raise RuntimeError(
            "Campaign reuse requires authoritative campaign, run, and "
            "repository identities."
        )

    persisted_by_case: dict[str, Mapping[str, Any]] = {}
    case_edges = repo.list_edges(
        src=campaign_uid,
        dst=run_uid,
        kind="campaign_case_result",
        limit=10000,
    )
    for edge in case_edges:
        payload = getattr(edge, "payload", None)
        if payload is None and isinstance(edge, Mapping):
            payload = edge.get("payload")
        if not isinstance(payload, Mapping):
            raise RuntimeError(
                "Persisted campaign-case result edge is missing its mapping payload."
            )
        payload = dict(payload)
        if payload.get("contract") != "calm.campaign_case_result.v1":
            raise RuntimeError(
                "Persisted campaign-case result uses an unsupported contract."
            )
        case_payload = payload.get("case")
        if not isinstance(case_payload, Mapping):
            raise RuntimeError(
                "Persisted campaign-case result is missing its exact case declaration."
            )
        case_name = case_payload.get("name")
        if not isinstance(case_name, str) or not case_name:
            raise RuntimeError(
                "Persisted campaign-case result is missing its case name."
            )
        previous = persisted_by_case.get(case_name)
        if previous is None or (
            previous.get("status") != "completed"
            and payload.get("status") == "completed"
        ):
            persisted_by_case[case_name] = payload

    expected_names = {case.name for case in cases}
    unexpected = sorted(set(persisted_by_case) - expected_names)
    if unexpected:
        raise RuntimeError(
            "Persisted campaign run contains results for undeclared cases: "
            + ", ".join(unexpected)
        )

    missing = [case.name for case in cases if case.name not in persisted_by_case]
    if missing:
        raise RuntimeError(
            "Completed campaign run is missing persisted case results: "
            + ", ".join(missing)
        )

    results: list[CampaignCaseResult] = []
    for case in cases:
        payload = persisted_by_case[case.name]
        resolved_case = CampaignCase.from_dict(payload["case"])
        if resolved_case != case:
            raise RuntimeError(
                f"Persisted campaign case {case.name!r} does not match the current "
                "campaign specification."
            )
        dataset = None
        dataset_uid = payload.get("dataset_uid_full")
        if dataset_uid:
            dataset = owner._project.dataset(str(dataset_uid))
        export_path = payload.get("export_path")
        failure = payload.get("failure")
        if failure is not None and not isinstance(failure, Mapping):
            raise RuntimeError(
                f"Persisted campaign case {case.name!r} has a malformed "
                "failure payload."
            )
        results.append(
            CampaignCaseResult(
                case=resolved_case,
                status=str(payload.get("status") or "completed"),
                stages=dict(payload.get("stages") or {}),
                dataset=dataset,
                export_path=Path(str(export_path)) if export_path else None,
                failure=dict(failure) if failure is not None else None,
            )
        )

    return CampaignWorkflowResult(
        campaign=campaign,
        run=campaign_run,
        cases=tuple(results),
        status=str(getattr(campaign_run, "status", None) or "completed"),
        reused=True,
    )
