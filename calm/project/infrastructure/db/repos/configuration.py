"""Repository for project configuration values."""

from __future__ import annotations

import json

from sqlalchemy import Connection, insert, select, update
from sqlalchemy.sql import func

from ..tables import project_configuration as project_configuration_t


class ProjectConfigurationRepository:
    """Simple repository to get/set the single project_configuration row.

    This repo intentionally exposes only get() and upsert() with semantic
    constraints left to the application layer.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get(self) -> dict | None:
        stmt = select(project_configuration_t).limit(1)
        row = self._conn.execute(stmt).mappings().first()
        if row is None:
            return None
        out = {
            "default_mlip": row.get("default_mlip"),
            "default_calculator_uid_full": row.get("default_calculator_uid_full"),
        }
        workflow_defaults_json = row.get("workflow_defaults_json")
        if workflow_defaults_json:
            workflow_defaults = json.loads(workflow_defaults_json)
            if not isinstance(workflow_defaults, dict):
                raise ValueError(
                    "Current project workflow defaults must decode to a mapping."
                )
            out["workflow_defaults"] = workflow_defaults
        else:
            out["workflow_defaults"] = None
        return out

    def upsert(
        self,
        *,
        default_mlip: str | None = None,
        default_calculator_uid_full: str | None = None,
        workflow_defaults: dict | None = None,
    ) -> dict:
        # Ensure a single row exists: insert when empty, otherwise update the first row.
        existing = self.get()
        values = {
            "default_mlip": default_mlip,
            "default_calculator_uid_full": default_calculator_uid_full,
            "workflow_defaults_json": (
                json.dumps(workflow_defaults) if workflow_defaults is not None else None
            ),
            "updated_at": func.current_timestamp(),
        }
        if existing is None:
            ins = insert(project_configuration_t).values(**values)
            self._conn.execute(ins)
        else:
            # Update the first row (no WHERE to allow single-row semantics)
            # Use a simple update that affects existing rows deterministically.
            upd = update(project_configuration_t).values(**values)
            self._conn.execute(upd)

        return self.get() or {}
