"""Internal composition owner for public named interface searches.

The :class:`~calm.public.project.Project` facade delegates named-search
composition to this service. Database-owned name and scientific-identity
uniqueness, lifecycle state, resume decisions, and run-to-prototype membership
remain owned by :class:`calm.project.application.interface_searches.InterfaceSearchesService`.
The in-memory scientific kernel remains in :mod:`calm.public.workflows.search`, while
prototype persistence remains owned by :class:`calm.public.workflows.saving.PublicProjectSaver`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, Protocol

from calm.project.application.interface_searches import InterfaceSearchConflictError
from calm.public.presentation.reporting import ensure_console_reporter

from calm.public.errors import SearchIdentityConflictError
from calm.public.records.search import PersistedInterfaceSearch
from calm.public.records.persistence import ProjectSearch, RecordAuthority
from calm.public.workflows.search_identity import (
    build_search_identity,
    normalize_search_error,
)
from calm.public.inputs.settings import SearchSettings


class _SearchWorkspace(Protocol):
    def prepare_interface_search(
        self,
        *,
        name: str,
        search_identity: str,
        run_spec: Mapping[str, Any],
        resume: bool,
    ) -> Any: ...

    def complete_interface_search(
        self,
        run_uid_full: str,
        *,
        n_candidates: int,
        enumeration_audit: Mapping[str, Any] | None = None,
    ) -> Any: ...

    def fail_interface_search(
        self,
        run_uid_full: str,
        *,
        error: Mapping[str, Any],
    ) -> Any: ...


class _SearchRepository(Protocol):
    def get_search(self, identifier: str) -> Any: ...


class _SearchSaver(Protocol):
    def record_search_result(
        self,
        result: Any,
        *,
        name: str | None = None,
        reporter: Any | None = None,
    ) -> None: ...


class ProjectInterfaceSearchWorkflowService:
    """Compose public named searches over authoritative lifecycle owners."""

    def __init__(
        self,
        *,
        project: Any,
        workspace: _SearchWorkspace,
        repository: _SearchRepository,
        saver: _SearchSaver,
    ) -> None:
        self._project = project
        self._workspace = workspace
        self._repo = repository
        self._saver = saver

    @staticmethod
    def _normalized_name(name: str | None) -> str:
        normalized = str(name or "").strip()
        if not normalized:
            raise ValueError(
                "Project-backed interface searches require a non-empty name."
            )
        return normalized

    @staticmethod
    def _validate_on_error(on_error: str) -> None:
        if on_error not in {"raise", "record"}:
            raise ValueError("on_error must be either 'raise' or 'record'.")

    @staticmethod
    def _settings(settings: SearchSettings | None) -> SearchSettings:
        resolved = SearchSettings() if settings is None else settings
        if not isinstance(resolved, SearchSettings):
            raise TypeError("settings must be a SearchSettings instance or None.")
        resolved.validate()
        return resolved

    @staticmethod
    def _surface_label(surface: Any) -> str:
        return str(
            getattr(surface, "label", None)
            or getattr(surface, "material", None)
            or getattr(surface, "project_slab_id_short", None)
            or type(surface).__name__
        )

    @staticmethod
    def _record_selector(record: ProjectSearch) -> str:
        for value in (
            record.run_uid_full,
            record.uid_full,
            record.search_identity,
            record.name,
        ):
            if value not in (None, ""):
                return str(value)
        raise ValueError("The persisted search record has no durable selector.")

    @staticmethod
    def _validate_record_match(
        supplied: ProjectSearch,
        resolved: ProjectSearch,
    ) -> None:
        for field in ("name", "search_identity", "run_uid_full"):
            expected = getattr(supplied, field, None)
            actual = getattr(resolved, field, None)
            if expected not in (None, "") and actual not in (None, ""):
                if str(expected) != str(actual):
                    raise ValueError(
                        "The persisted search record does not match this Project's "
                        f"authoritative {field}."
                    )

    def search(self, search: Any) -> PersistedInterfaceSearch:
        """Resolve one supported selector to a project-bound durable view."""

        if isinstance(search, PersistedInterfaceSearch):
            if search.project is not self._project:
                raise ValueError("The persisted search belongs to another Project.")
            return search

        supplied_record: ProjectSearch | None = None
        if isinstance(search, ProjectSearch):
            supplied_record = search
            selector = self._record_selector(search)
        elif isinstance(search, str):
            selector = search.strip()
            if not selector:
                raise ValueError("Search names must be non-empty strings.")
        else:
            raise TypeError(
                "search must be a persisted search name, ProjectSearch record, or "
                "PersistedInterfaceSearch returned by this Project."
            )

        try:
            item = self._repo.get_search(selector)
        except KeyError:
            raise KeyError(f"No persisted search matches {selector!r}.") from None
        record = ProjectSearch.from_item(item)
        if record.authority is not RecordAuthority.AUTHORITATIVE:
            record = replace(
                record,
                authority=RecordAuthority.AUTHORITATIVE,
            )
        if supplied_record is not None:
            self._validate_record_match(supplied_record, record)
        return PersistedInterfaceSearch(
            project=self._project,
            name=record.name,
            record=record,
        )

    def search_interfaces(
        self,
        surface_a: Any,
        surface_b: Any,
        *,
        settings: SearchSettings | None = None,
        name: str | None = None,
        resume: bool = True,
        on_error: str = "raise",
        reporter: Any | None = None,
    ) -> PersistedInterfaceSearch:
        """Run, resume, or reuse one deterministic named interface search."""

        from calm.public.workflows.search import (
            _coerce_surface,
            search_interfaces as execute_search,
        )

        normalized_name = self._normalized_name(name)
        self._validate_on_error(on_error)
        resolved_settings = self._settings(settings)
        surf_a = _coerce_surface(surface_a)
        surf_b = _coerce_surface(surface_b)
        search_identity, run_spec = build_search_identity(
            surf_a,
            surf_b,
            resolved_settings,
        )

        try:
            prepared = self._workspace.prepare_interface_search(
                name=normalized_name,
                search_identity=search_identity,
                run_spec=run_spec,
                resume=bool(resume),
            )
        except InterfaceSearchConflictError as exc:
            raise SearchIdentityConflictError(str(exc)) from exc

        search_record = prepared.search
        if prepared.action == "reuse":
            return self.search(normalized_name)

        rep = ensure_console_reporter(reporter)
        try:
            with rep.stage(
                "Search interfaces: "
                f"{self._surface_label(surf_a)} vs {self._surface_label(surf_b)}",
                name=normalized_name,
            ):
                result = execute_search(
                    surf_a,
                    surf_b,
                    settings=resolved_settings,
                    name=normalized_name,
                    reporter=rep,
                )
                result.metadata.update(
                    {
                        "search_identity": search_identity,
                        "run_uid_full": search_record.run_uid_full,
                        "run_id_short": search_record.run_id_short,
                        "status": "running",
                        "settings": resolved_settings.to_dict(),
                        "reused": False,
                    }
                )
                self._saver.record_search_result(
                    result,
                    name=normalized_name,
                    reporter=rep,
                )
                audit = result.enumeration_audit()
                completed = self._workspace.complete_interface_search(
                    search_record.run_uid_full,
                    n_candidates=len(result),
                    enumeration_audit=(
                        None if audit is None else audit.to_dict(cumulative=False)
                    ),
                )
                result.metadata.update(
                    {
                        "status": "done",
                        "run_uid_full": completed.run_uid_full,
                        "run_id_short": completed.run_id_short,
                        "progress": dict(getattr(completed, "progress", {}) or {}),
                    }
                )
                return self.search(normalized_name)
        except Exception as exc:
            self._workspace.fail_interface_search(
                search_record.run_uid_full,
                error=normalize_search_error(exc),
            )
            if on_error == "raise":
                raise
            return self.search(normalized_name)
