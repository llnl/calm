"""Authoritative lifecycle service for named interface searches.

A named search is an explicit database relation between one user-facing project
name, one deterministic scientific search identity, and one content-addressed
``prototype_search`` run. Search status, progress, and failures remain owned by
the run; candidate membership remains owned by prototypes linked to that run.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal

from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    run_identity_payload,
)
from calm.project.domain.models import InterfaceSearch, Run

from ._uow import fresh_uow, require_uow_factory


class InterfaceSearchConflictError(RuntimeError):
    """Raised when a public name and scientific identity do not agree."""


@dataclass(frozen=True)
class InterfaceSearchPreparation:
    """Result of atomically preparing one named search for execution."""

    action: Literal["execute", "reuse"]
    search: InterfaceSearch


class InterfaceSearchesService:
    """Own named-search identity, resume decisions, and run transitions."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="InterfaceSearchesService",
        )

    @staticmethod
    def _validated_inputs(
        *,
        name: str,
        search_identity: str,
        run_spec: Mapping[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("Interface-search name must be non-empty.")
        normalized_identity = str(search_identity).strip()
        if not normalized_identity:
            raise ValueError("Interface-search identity must be non-empty.")
        spec = dict(run_spec)
        if str(spec.get("search_identity") or "") != normalized_identity:
            raise ValueError(
                "Interface-search run spec must contain its exact search_identity."
            )
        if "name" in spec:
            raise ValueError(
                "Interface-search names are authoritative aliases and must not "
                "participate in content-addressed run identity."
            )
        return normalized_name, normalized_identity, spec

    @staticmethod
    def _new_run(uow: Any, *, spec: Mapping[str, Any]) -> Run:
        uid_full = persisted_entity_uid_v2(
            "run",
            run_identity_payload(run_type="prototype_search", spec=spec),
        )
        existing = uow.runs.get_by_uid_full(uid_full)
        if existing is not None:
            if existing.run_type != "prototype_search" or dict(existing.spec) != dict(
                spec
            ):
                raise RuntimeError(
                    "Content-addressed interface-search run identity resolved to "
                    "inconsistent authoritative state."
                )
            return existing
        run = Run(
            uid_full=uid_full,
            id_short=uow.ids.ensure_run_id(uid_full),
            run_type="prototype_search",
            spec=dict(spec),
            status="queued",
        )
        return uow.runs.upsert(run)

    @staticmethod
    def _set_run_state(
        uow: Any,
        run: Run,
        *,
        status: str,
        progress: Mapping[str, Any] | None,
        error: Mapping[str, Any] | None,
    ) -> Run:
        updated = replace(
            run,
            status=status,
            progress=dict(progress or {}) or None,
            error=dict(error or {}),
        )
        return uow.runs.upsert(updated)

    def prepare(
        self,
        *,
        name: str,
        search_identity: str,
        run_spec: Mapping[str, Any],
        resume: bool,
    ) -> InterfaceSearchPreparation:
        """Resolve conflicts and prepare one search in a single transaction."""

        name, search_identity, spec = self._validated_inputs(
            name=name,
            search_identity=search_identity,
            run_spec=run_spec,
        )
        with fresh_uow(self._uow_factory, owner="InterfaceSearchesService") as uow:
            by_name = uow.interface_searches.get_by_name(name)
            by_identity = uow.interface_searches.get_by_search_identity(search_identity)

            if by_name is not None and by_name.search_identity != search_identity:
                raise InterfaceSearchConflictError(
                    f"Persisted search name {name!r} is already bound to a "
                    "different surface/settings identity. Choose a new name or "
                    "restore the original inputs."
                )
            if by_identity is not None and by_identity.name != name:
                raise InterfaceSearchConflictError(
                    "This surface/settings identity is already persisted as "
                    f"search {by_identity.name!r}. Reuse that name rather than "
                    "creating a second public alias for the same scientific search."
                )

            existing = by_name or by_identity
            if existing is None:
                run = self._new_run(uow, spec=spec)
                search = uow.interface_searches.create(
                    name=name,
                    search_identity=search_identity,
                    run_uid_full=run.uid_full,
                )
                recovery = False
            else:
                search = existing
                run = uow.runs.get_by_uid_full(search.run_uid_full)
                if run is None:
                    raise RuntimeError(
                        f"Interface search {name!r} references missing run "
                        f"{search.run_uid_full!r}."
                    )
                if run.run_type != "prototype_search" or dict(run.spec) != spec:
                    raise RuntimeError(
                        f"Interface search {name!r} references inconsistent run state."
                    )
                recovery = True

            if resume and run.status == "done":
                return InterfaceSearchPreparation(
                    action="reuse",
                    search=uow.interface_searches.get_by_name(name) or search,
                )

            progress = {
                "name": name,
                "phase": "search",
                "recovery": recovery,
                "resume": bool(resume),
            }
            self._set_run_state(
                uow,
                run,
                status="running",
                progress=progress,
                error=None,
            )
            refreshed = uow.interface_searches.get_by_name(name)
            assert refreshed is not None
            return InterfaceSearchPreparation(action="execute", search=refreshed)

    def complete(
        self,
        run_uid_full: str,
        *,
        n_candidates: int,
        enumeration_audit: Mapping[str, Any] | None = None,
    ) -> InterfaceSearch:
        """Mark one authoritative search run complete."""

        with fresh_uow(self._uow_factory, owner="InterfaceSearchesService") as uow:
            search = uow.interface_searches.get_by_run_uid_full(str(run_uid_full))
            if search is None:
                raise KeyError(
                    f"No authoritative interface search owns run {run_uid_full!r}."
                )
            run = uow.runs.get_by_uid_full(search.run_uid_full)
            if run is None:
                raise RuntimeError(
                    f"Interface search {search.name!r} references a missing run."
                )
            progress: dict[str, Any] = {
                "name": search.name,
                "phase": "complete",
                "n_candidates": int(n_candidates),
            }
            if enumeration_audit is not None:
                progress["enumeration_audit"] = dict(enumeration_audit)
            self._set_run_state(
                uow,
                run,
                status="done",
                progress=progress,
                error=None,
            )
            refreshed = uow.interface_searches.get_by_name(search.name)
            assert refreshed is not None
            return refreshed

    def fail(
        self,
        run_uid_full: str,
        *,
        error: Mapping[str, Any],
    ) -> InterfaceSearch:
        """Persist one structured search failure."""

        with fresh_uow(self._uow_factory, owner="InterfaceSearchesService") as uow:
            search = uow.interface_searches.get_by_run_uid_full(str(run_uid_full))
            if search is None:
                raise KeyError(
                    f"No authoritative interface search owns run {run_uid_full!r}."
                )
            run = uow.runs.get_by_uid_full(search.run_uid_full)
            if run is None:
                raise RuntimeError(
                    f"Interface search {search.name!r} references a missing run."
                )
            self._set_run_state(
                uow,
                run,
                status="failed",
                progress={"name": search.name, "phase": "failed"},
                error=error,
            )
            refreshed = uow.interface_searches.get_by_name(search.name)
            assert refreshed is not None
            return refreshed

    def list(self, *, limit: int | None = None) -> list[InterfaceSearch]:
        with fresh_uow(self._uow_factory, owner="InterfaceSearchesService") as uow:
            return uow.interface_searches.list(limit=limit)

    def get(self, identifier: str) -> InterfaceSearch:
        needle = str(identifier)
        with fresh_uow(self._uow_factory, owner="InterfaceSearchesService") as uow:
            direct = (
                uow.interface_searches.get_by_name(needle)
                or uow.interface_searches.get_by_search_identity(needle)
                or uow.interface_searches.get_by_run_uid_full(needle)
                or uow.interface_searches.get_by_run_id_short(needle)
            )
            if direct is not None:
                return direct
            raise KeyError(f"No persisted interface search matches {needle!r}.")
