"""Application-level helpers for managing runs.

This module implements run creation and status management helpers used by the
workspace UX and job runner layers.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    run_identity_payload,
)

from ..domain.models import Run
from ..ports.uow import UnitOfWork


class RunsService:
    """Application service for creating and managing runs."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def create(self, *, run_type: str, spec: Mapping[str, Any]) -> Run:
        """Create (or reuse) a queued run."""

        with self._uow:
            uid_full = persisted_entity_uid_v2(
                "run",
                run_identity_payload(run_type=run_type, spec=spec),
            )
            existing = self._uow.runs.get_by_uid_full(uid_full)
            if existing is not None:
                return existing

            id_short = self._uow.ids.ensure_run_id(uid_full)
            run = Run(
                uid_full=uid_full,
                id_short=id_short,
                run_type=run_type,
                status="queued",
                spec=dict(spec),
            )
            stored = self._uow.runs.upsert(run)
            self._uow.commit()
            return stored

    def get(self, identifier: str) -> Run:
        with self._uow:
            uid_full = self._uow.ids.resolve_run(identifier)
            run = self._uow.runs.get_by_uid_full(uid_full)
            if run is None:
                raise KeyError(f"No run found for identifier {identifier!r}")
            return run

    def mark_running(
        self, identifier: str, *, progress: Optional[Mapping[str, Any]] = None
    ) -> Run:
        return self._set_status(
            identifier,
            status="running",
            error={},
            progress=progress,
        )

    def mark_done(
        self, identifier: str, *, progress: Optional[Mapping[str, Any]] = None
    ) -> Run:
        return self._set_status(
            identifier,
            status="done",
            error={},
            progress=progress,
        )

    def mark_failed(self, identifier: str, *, error: Mapping[str, Any]) -> Run:
        return self._set_status(identifier, status="failed", error=error)

    def _set_status(
        self,
        identifier: str,
        *,
        status: str,
        error: Optional[Mapping[str, Any]] = None,
        progress: Optional[Mapping[str, Any]] = None,
    ) -> Run:
        with self._uow:
            uid_full = self._uow.ids.resolve_run(identifier)
            run = self._uow.runs.get_by_uid_full(uid_full)
            if run is None:
                raise KeyError(f"No run found for identifier {identifier!r}")

            updated = replace(
                run,
                status=status,
                error=dict(error) if error is not None else run.error,
                progress=dict(progress) if progress is not None else run.progress,
            )

            stored = self._uow.runs.upsert(updated)
            self._uow.commit()
            return stored
