"""Repository for workflow run records."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import Connection, insert, select, update
from sqlalchemy.sql import func

from ....domain.models import Run
from ....ports.ids import IdResolver
from ....ports.repos import RunRepository
from ..tables import runs as runs_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyRunRepository(RunRepository):
    def __init__(self, conn: Connection, ids: IdResolver) -> None:
        self._conn = conn
        self._ids = ids

    def upsert(self, run: Run) -> Run:
        row = (
            self._conn.execute(select(runs_t).where(runs_t.c.uid_full == run.uid_full))
            .mappings()
            .first()
        )

        if row is None:
            id_short = run.id_short or self._ids.ensure_run_id(run.uid_full)
            spec_json = json.dumps(run.spec or {})
            error_json = json.dumps(run.error) if run.error is not None else None
            if run.progress is not None:
                progress_json = json.dumps(run.progress)
            else:
                progress_json = None

            self._conn.execute(
                insert(runs_t).values(
                    uid_full=run.uid_full,
                    id_short=id_short,
                    run_type=run.run_type,
                    status=run.status,
                    spec_json=spec_json,
                    error_json=error_json,
                    progress_json=progress_json,
                )
            )
            stored = self.get_by_uid_full(run.uid_full)
            assert stored is not None
            return stored

        # Existing row: update only when the caller is moving beyond
        # the default 'queued' state.
        updates: dict[str, Any] = {}
        if run.status and run.status != row["status"] and run.status != "queued":
            updates["status"] = run.status
        if run.error is not None:
            updates["error_json"] = json.dumps(run.error)
        if run.progress is not None:
            updates["progress_json"] = json.dumps(run.progress)
        if updates:
            updates["updated_at"] = func.current_timestamp()
            stmt = update(runs_t).where(runs_t.c.run_pk == row["run_pk"])
            stmt = stmt.values(**updates)
            self._conn.execute(stmt)

        stored = self.get_by_uid_full(run.uid_full)
        assert stored is not None
        return stored

    def get_by_uid_full(self, uid_full: str) -> Optional[Run]:
        stmt = select(runs_t).where(runs_t.c.uid_full == uid_full)
        row = self._conn.execute(stmt).mappings().first()
        if row is None:
            return None

        _spec_json = row.get("spec_json")
        _error_json = row.get("error_json")
        _progress_json = row.get("progress_json")

        spec_val = json.loads(_spec_json) if _spec_json else None
        error_val = json.loads(_error_json) if _error_json else None
        progress_val = json.loads(_progress_json) if _progress_json else None

        return Run(
            uid_full=row["uid_full"],
            id_short=row["id_short"],
            run_type=row["run_type"],
            status=row["status"],
            spec=spec_val,
            error=error_val,
            progress=progress_val,
            created_at=_dt_to_str(row.get("created_at")),
            updated_at=_dt_to_str(row.get("updated_at")),
        )

    def list(
        self,
        *,
        limit: Optional[int] = None,
        run_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[Run]:
        query = select(runs_t).order_by(runs_t.c.created_at.desc())

        if run_type is not None:
            query = query.where(runs_t.c.run_type == run_type)
        if status is not None:
            query = query.where(runs_t.c.status == status)
        if limit is not None:
            query = query.limit(limit)

        rows = self._conn.execute(query).mappings().all()
        out: list[Run] = []
        for row in rows:
            _spec_json = row.get("spec_json")
            _error_json = row.get("error_json")
            _progress_json = row.get("progress_json")

            spec_val = json.loads(_spec_json) if _spec_json else None
            error_val = json.loads(_error_json) if _error_json else None
            progress_val = json.loads(_progress_json) if _progress_json else None

            out.append(
                Run(
                    uid_full=row["uid_full"],
                    id_short=row["id_short"],
                    run_type=row["run_type"],
                    status=row["status"],
                    spec=spec_val,
                    error=error_val,
                    progress=progress_val,
                    created_at=_dt_to_str(row.get("created_at")),
                    updated_at=_dt_to_str(row.get("updated_at")),
                )
            )
        return out
