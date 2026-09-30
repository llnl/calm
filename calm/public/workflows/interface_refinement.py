"""Internal orchestration owner for public interface refinement.

The :class:`~calm.public.project.Project` facade delegates strain-partition and
registry-refinement composition to this service. Scientific follow-up execution
and persistence remain owned by the existing Workspace application services;
this module owns target normalization, sequencing, failure policy, reporting,
and typed result assembly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from calm.public.presentation.reporting import ensure_console_reporter

from calm.public.records.followups import (
    InterfaceRefinementResult,
    RegistrySearchRun,
    StrainPartitionScan,
)
from calm.public.records.persistence import ProjectInterface
from calm.public.inputs.settings import RegistrySettings, StrainPartitionSettings


class _RefinementWorkspace(Protocol):
    def start_strain_partition_scan(self, **kwargs: Any) -> Any: ...

    def derive_interfaces_from_strain_partition_scan(
        self,
        run: str,
        **kwargs: Any,
    ) -> list[Any]: ...

    def start_registry_search(self, **kwargs: Any) -> Any: ...

    def derive_interfaces_from_registry_search(
        self,
        run: str,
        **kwargs: Any,
    ) -> list[Any]: ...


class _RefinementRepository(Protocol):
    def get_interface(self, identifier: str) -> Any: ...


class ProjectInterfaceRefinementService:
    """Coordinate public strain-partition and optional registry workflows."""

    def __init__(
        self,
        *,
        project: Any,
        workspace: _RefinementWorkspace,
        repository: _RefinementRepository,
    ) -> None:
        self._project = project
        self._workspace = workspace
        self._repo = repository

    def _persistent_interface_ids(
        self,
        values: Any,
        *,
        search_name: str,
    ) -> list[str]:
        if isinstance(values, str):
            items: Iterable[Any] = (values,)
        elif hasattr(values, "records") and callable(values.records):
            items = values.records()
        else:
            try:
                items = list(values)
            except TypeError as exc:
                raise TypeError(
                    "interfaces must be a persisted interface identifier, a "
                    "project-backed collection, or an iterable of persisted interfaces."
                ) from exc

        selected: list[str] = []
        seen: set[str] = set()
        for item in items:
            if isinstance(item, str):
                identifier = item
            elif isinstance(item, Mapping):
                identifier = (
                    item.get("uid_full")
                    or item.get("project_interface_uid")
                    or item.get("id_short")
                    or item.get("project_interface_id")
                )
            else:
                identifier = getattr(item, "uid_full", None) or getattr(
                    item,
                    "id_short",
                    None,
                )
            if not identifier:
                raise ValueError(
                    "Explicit refinement targets must have persistent "
                    "interface identities."
                )
            record = ProjectInterface.from_item(
                self._repo.get_interface(str(identifier))
            )
            if not record.is_authoritative:
                raise ValueError(
                    "Explicit refinement targets must be authoritative "
                    "persisted interfaces."
                )
            if record.stage != "built":
                raise ValueError(
                    "Explicit refinement targets must have stage='built'; "
                    f"got {record.stage!r}."
                )
            owner = record.metadata.get("search_name")
            if owner not in {None, search_name}:
                raise ValueError(
                    f"Interface {identifier!r} belongs to search {owner!r}, "
                    f"not {search_name!r}."
                )
            uid = record.uid_full
            if not uid:
                raise ValueError("Explicit refinement target is missing its full UID.")
            if uid not in seen:
                selected.append(uid)
                seen.add(uid)
        return selected

    def _persistent_registry_targets(self, values: Any) -> list[ProjectInterface]:
        if isinstance(values, str):
            items: Iterable[Any] = (values,)
        elif hasattr(values, "records") and callable(values.records):
            items = values.records()
        else:
            try:
                items = list(values)
            except TypeError as exc:
                raise TypeError(
                    "interfaces must be a persisted interface identifier, a "
                    "project-backed collection, or an iterable of persisted interfaces."
                ) from exc

        selected: list[ProjectInterface] = []
        seen: set[str] = set()
        for item in items:
            if isinstance(item, str):
                identifier = item
            elif isinstance(item, Mapping):
                identifier = (
                    item.get("uid_full")
                    or item.get("project_interface_uid")
                    or item.get("id_short")
                    or item.get("project_interface_id")
                )
            else:
                identifier = getattr(item, "uid_full", None) or getattr(
                    item,
                    "id_short",
                    None,
                )
            if not identifier:
                raise ValueError(
                    "Registry targets must have persistent interface identities."
                )
            record = ProjectInterface.from_item(
                self._repo.get_interface(str(identifier))
            )
            if not record.is_authoritative:
                raise ValueError(
                    "Registry targets must be authoritative persisted interfaces."
                )
            if record.stage != "strain_partitioned":
                raise ValueError(
                    "Registry targets must have stage='strain_partitioned'; "
                    f"got {record.stage!r}."
                )
            uid = record.uid_full
            if not uid:
                raise ValueError("Registry target is missing its full UID.")
            if uid not in seen:
                selected.append(record)
                seen.add(uid)
        return selected

    @staticmethod
    def _selected_built_interface_ids(
        search: Any,
        *,
        top: int | None,
        pareto: bool,
    ) -> list[str]:
        candidates = search.candidates()
        if pareto:
            candidates = candidates.select(pareto=True)
        if top is not None:
            if isinstance(top, bool) or not isinstance(top, int) or top <= 0:
                raise ValueError("top must be a positive integer or None.")
            candidates = candidates.select_top(top, by="score")

        prototype_aliases = {
            str(row[key])
            for row in candidates.to_rows(view="all")
            for key in (
                "project_prototype_uid",
                "project_prototype_id",
                "prototype_uid_full",
                "prototype_uid",
                "prototype_id_short",
            )
            if row.get(key)
        }
        if not prototype_aliases:
            return []

        selected: list[str] = []
        seen: set[str] = set()
        for row in search.interfaces().to_rows(view="all"):
            if str(row.get("stage") or "built") != "built":
                continue
            if str(row.get("authority") or "") != "authoritative":
                continue
            row_prototypes = {
                str(row[key])
                for key in (
                    "prototype_uid_full",
                    "prototype_uid",
                    "prototype_id_short",
                    "project_prototype_uid",
                    "project_prototype_id",
                    "candidate_uid",
                )
                if row.get(key)
            }
            if row_prototypes and not row_prototypes.intersection(prototype_aliases):
                continue
            identifier = (
                row.get("project_interface_uid")
                or row.get("uid_full")
                or row.get("project_interface_id")
                or row.get("id_short")
            )
            if identifier and str(identifier) not in seen:
                selected.append(str(identifier))
                seen.add(str(identifier))
        return selected

    @staticmethod
    def _run_id(run: Any) -> str:
        value = getattr(run, "id_short", None) or getattr(run, "uid_full", None)
        if not value:
            raise RuntimeError("Follow-up run did not return a persistent identifier.")
        return str(value)

    def _start_strain_partition_scan(
        self,
        interfaces: list[str],
        *,
        settings: StrainPartitionSettings,
        label: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        settings.validate()
        merged = dict(payload or {})
        merged.update(settings.to_dict())
        return self._workspace.start_strain_partition_scan(
            prototypes=list(interfaces),
            alphas=list(settings.resolve_alphas()),
            label=label,
            payload=merged,
        )

    def _start_registry_search(
        self,
        interfaces: list[str],
        *,
        settings: RegistrySettings,
        label: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        settings.validate_for_persisted_refinement()
        merged = dict(payload or {})
        merged["registry_settings"] = settings.to_dict()
        return self._workspace.start_registry_search(
            prototypes=list(interfaces),
            n_steps=int(settings.steps),
            label=label,
            payload=merged,
        )

    def refine_registry(
        self,
        interfaces: Any,
        *,
        settings: RegistrySettings,
        label_prefix: str | None = None,
        on_error: str = "explain",
        reporter: Any | None = None,
    ) -> InterfaceRefinementResult:
        """Run registry refinement from persisted strain-partitioned interfaces."""

        if on_error not in {"explain", "raise"}:
            raise ValueError("on_error must be 'explain' or 'raise'.")
        if not isinstance(settings, RegistrySettings):
            raise TypeError("settings must be a RegistrySettings instance.")
        settings.validate_for_persisted_refinement()
        rep = ensure_console_reporter(reporter)
        issues: list[str] = []

        try:
            with rep.section("Refine interface registry"):
                source_interfaces = self._persistent_registry_targets(interfaces)
                if not source_interfaces:
                    issues.append("no_strain_partitioned_interfaces")
                    rep.warn(
                        "No authoritative strain-partitioned interfaces were supplied."
                    )
                    return InterfaceRefinementResult(ok=False, issues=issues)

                source_ids = [record.uid_full for record in source_interfaces]
                rep.mapping(
                    {
                        "n_strain_partitioned_interfaces": len(source_ids),
                        "registry_steps": settings.steps,
                        "registry_translation_step": (
                            settings.operational_translation_step
                        ),
                        "registry_seed": settings.seed,
                    },
                    title="Registry-refinement inputs",
                )

                registry_label = (
                    f"{label_prefix}_registry_search" if label_prefix else None
                )
                registry_run = self._start_registry_search(
                    source_ids,
                    settings=settings,
                    label=registry_label,
                    payload={"public_api": "Project.refine_registry"},
                )
                registry_wrapper = RegistrySearchRun(
                    project=self._project,
                    run=registry_run,
                )
                registry_interfaces = (
                    self._workspace.derive_interfaces_from_registry_search(
                        self._run_id(registry_run),
                        label=(
                            f"{label_prefix}_registry_refined" if label_prefix else None
                        ),
                        params={"registry_settings": settings.to_dict()},
                    )
                )
                if not registry_interfaces:
                    issues.append("no_registry_derived_interfaces")

                rep.mapping(
                    {
                        "ok": not issues,
                        "n_strain_partitioned_interfaces": len(source_ids),
                        "n_registry_refined": len(registry_interfaces),
                        "n_issues": len(issues),
                    },
                    title="Registry-refinement summary",
                )
                return InterfaceRefinementResult(
                    ok=not issues,
                    issues=issues,
                    registry_run=registry_wrapper,
                    strain_interfaces=list(source_interfaces),
                    registry_interfaces=list(registry_interfaces),
                )
        except Exception as exc:
            if on_error == "raise":
                raise
            issues.append(f"unexpected:{exc}")
            rep.warn(f"Registry refinement failed: {exc}")
            return InterfaceRefinementResult(ok=False, issues=issues)

    def refine_interfaces(
        self,
        search: Any,
        *,
        strain_settings: StrainPartitionSettings,
        registry_settings: RegistrySettings | None = None,
        interfaces: Any | None = None,
        top: int | None = None,
        pareto: bool = True,
        label_prefix: str | None = None,
        on_error: str = "explain",
        reporter: Any | None = None,
    ) -> InterfaceRefinementResult:
        """Run the canonical persisted interface-refinement lineage."""

        if on_error not in {"explain", "raise"}:
            raise ValueError("on_error must be 'explain' or 'raise'.")
        if not isinstance(strain_settings, StrainPartitionSettings):
            raise TypeError(
                "strain_settings must be a StrainPartitionSettings instance."
            )
        strain_settings.validate()
        resolved_registry = registry_settings
        if resolved_registry is not None:
            if not isinstance(resolved_registry, RegistrySettings):
                raise TypeError(
                    "registry_settings must be a RegistrySettings instance or None."
                )
            resolved_registry.validate_for_persisted_refinement()

        search = self._project.search(search)
        rep = ensure_console_reporter(reporter)
        issues: list[str] = []

        try:
            with rep.section(f"Refine interfaces: search={search.name}"):
                if interfaces is not None:
                    if top is not None:
                        raise ValueError(
                            "top cannot be combined with explicit refinement "
                            "interfaces."
                        )
                    built_ids = self._persistent_interface_ids(
                        interfaces,
                        search_name=search.name,
                    )
                else:
                    built_ids = self._selected_built_interface_ids(
                        search,
                        top=top,
                        pareto=pareto,
                    )

                if not built_ids:
                    issues.append("no_built_interfaces_found_for_search")
                    rep.warn(
                        "No authoritative built interfaces were found for the selected "
                        "candidates. Build interfaces before running refinement."
                    )
                    return InterfaceRefinementResult(ok=False, issues=issues)

                input_summary: dict[str, Any] = {
                    "n_built_interfaces": len(built_ids),
                    "strain_target_metric": strain_settings.resolve_metric(),
                    "registry_refinement": (
                        "enabled" if resolved_registry is not None else "disabled"
                    ),
                }
                if resolved_registry is not None:
                    input_summary.update(
                        {
                            "registry_steps": resolved_registry.steps,
                            "registry_translation_step": (
                                resolved_registry.operational_translation_step
                            ),
                            "registry_seed": resolved_registry.seed,
                        }
                    )
                rep.mapping(input_summary, title="Refinement inputs")

                strain_label = f"{label_prefix}_strain_scan" if label_prefix else None
                strain_run = self._start_strain_partition_scan(
                    built_ids,
                    settings=strain_settings,
                    label=strain_label,
                    payload={
                        "public_api": "Project.refine_interfaces",
                        "search_name": search.name,
                    },
                )
                strain_wrapper = StrainPartitionScan(
                    project=self._project,
                    run=strain_run,
                )
                strain_interfaces = (
                    self._workspace.derive_interfaces_from_strain_partition_scan(
                        self._run_id(strain_run),
                        label=(
                            f"{label_prefix}_strain_partitioned"
                            if label_prefix
                            else None
                        ),
                        params={
                            "search_name": search.name,
                            "strain_target_metric": strain_settings.resolve_metric(),
                        },
                    )
                )
                if not strain_interfaces:
                    return InterfaceRefinementResult(
                        ok=False,
                        issues=[*issues, "no_strain_derived_interfaces"],
                        strain_scan=strain_wrapper,
                        strain_interfaces=[],
                        registry_interfaces=[],
                    )

                strain_ids = [
                    str(value)
                    for interface in strain_interfaces
                    if (
                        value := getattr(interface, "uid_full", None)
                        or getattr(interface, "id_short", None)
                    )
                ]
                if len(strain_ids) != len(strain_interfaces):
                    return InterfaceRefinementResult(
                        ok=False,
                        issues=[
                            *issues,
                            "strain_interfaces_missing_persistent_identity",
                        ],
                        strain_scan=strain_wrapper,
                        strain_interfaces=list(strain_interfaces),
                        registry_interfaces=[],
                    )

                if resolved_registry is None:
                    rep.mapping(
                        {
                            "ok": True,
                            "n_built_interfaces": len(built_ids),
                            "n_strain_partitioned": len(strain_interfaces),
                            "n_registry_refined": 0,
                            "n_issues": 0,
                        },
                        title="Refinement summary",
                    )
                    return InterfaceRefinementResult(
                        ok=True,
                        issues=[],
                        strain_scan=strain_wrapper,
                        strain_interfaces=list(strain_interfaces),
                        registry_interfaces=[],
                    )

                registry_label = (
                    f"{label_prefix}_registry_search" if label_prefix else None
                )
                registry_run = self._start_registry_search(
                    strain_ids,
                    settings=resolved_registry,
                    label=registry_label,
                    payload={
                        "public_api": "Project.refine_interfaces",
                        "search_name": search.name,
                    },
                )
                registry_wrapper = RegistrySearchRun(
                    project=self._project,
                    run=registry_run,
                )
                registry_interfaces = (
                    self._workspace.derive_interfaces_from_registry_search(
                        self._run_id(registry_run),
                        label=(
                            f"{label_prefix}_registry_refined" if label_prefix else None
                        ),
                        params={
                            "search_name": search.name,
                            "registry_settings": resolved_registry.to_dict(),
                        },
                    )
                )
                if not registry_interfaces:
                    issues.append("no_registry_derived_interfaces")

                rep.mapping(
                    {
                        "ok": not issues,
                        "n_built_interfaces": len(built_ids),
                        "n_strain_partitioned": len(strain_interfaces),
                        "n_registry_refined": len(registry_interfaces),
                        "n_issues": len(issues),
                    },
                    title="Refinement summary",
                )
                return InterfaceRefinementResult(
                    ok=not issues,
                    issues=issues,
                    strain_scan=strain_wrapper,
                    registry_run=registry_wrapper,
                    strain_interfaces=list(strain_interfaces),
                    registry_interfaces=list(registry_interfaces),
                )
        except Exception as exc:
            if on_error == "raise":
                raise
            issues.append(f"unexpected:{exc}")
            rep.warn(f"Interface refinement failed: {exc}")
            return InterfaceRefinementResult(ok=False, issues=issues)
