"""Repository for named interface-search records."""

from __future__ import annotations

import json

from sqlalchemy import Connection, insert, select
from sqlalchemy.engine import RowMapping

from ....domain.models import InterfaceSearch
from ....ports.repos import InterfaceSearchRepository
from ..tables import interface_searches as interface_searches_t
from ..tables import runs as runs_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyInterfaceSearchRepository(InterfaceSearchRepository):
    """Persist unique public names for authoritative interface-search runs."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    @staticmethod
    def _select():
        return select(
            interface_searches_t.c.name,
            interface_searches_t.c.search_identity,
            interface_searches_t.c.run_uid_full,
            interface_searches_t.c.created_at.label("search_created_at"),
            runs_t.c.id_short.label("run_id_short"),
            runs_t.c.status,
            runs_t.c.spec_json,
            runs_t.c.error_json,
            runs_t.c.progress_json,
            runs_t.c.updated_at.label("run_updated_at"),
        ).select_from(
            interface_searches_t.join(
                runs_t,
                interface_searches_t.c.run_uid_full == runs_t.c.uid_full,
            )
        )

    @staticmethod
    def _row_to_search(row: RowMapping) -> InterfaceSearch:
        spec_json = row.get("spec_json")
        error_json = row.get("error_json")
        progress_json = row.get("progress_json")
        error = json.loads(error_json) if error_json else None
        return InterfaceSearch(
            name=str(row["name"]),
            search_identity=str(row["search_identity"]),
            run_uid_full=str(row["run_uid_full"]),
            run_id_short=str(row["run_id_short"]),
            status=str(row["status"]),
            spec=json.loads(spec_json) if spec_json else {},
            error=error or None,
            progress=json.loads(progress_json) if progress_json else None,
            created_at=_dt_to_str(row.get("search_created_at")),
            updated_at=_dt_to_str(row.get("run_updated_at")),
        )

    def create(
        self,
        *,
        name: str,
        search_identity: str,
        run_uid_full: str,
    ) -> InterfaceSearch:
        by_name = self.get_by_name(name)
        by_identity = self.get_by_search_identity(search_identity)
        by_run = self.get_by_run_uid_full(run_uid_full)
        existing = by_name or by_identity or by_run
        if existing is not None:
            if (
                existing.name == name
                and existing.search_identity == search_identity
                and existing.run_uid_full == run_uid_full
                and all(
                    candidate is None or candidate == existing
                    for candidate in (by_name, by_identity, by_run)
                )
            ):
                return existing
            raise ValueError(
                "Interface-search name, scientific identity, and run must form "
                "one unique authoritative relation."
            )

        run_exists = self._conn.execute(
            select(runs_t.c.uid_full).where(runs_t.c.uid_full == run_uid_full)
        ).first()
        if run_exists is None:
            raise KeyError(
                f"Cannot bind interface search to missing run {run_uid_full!r}."
            )

        self._conn.execute(
            insert(interface_searches_t).values(
                name=name,
                search_identity=search_identity,
                run_uid_full=run_uid_full,
            )
        )
        stored = self.get_by_name(name)
        assert stored is not None
        return stored

    def get_by_name(self, name: str) -> InterfaceSearch | None:
        row = (
            self._conn.execute(
                self._select().where(interface_searches_t.c.name == name)
            )
            .mappings()
            .first()
        )
        return None if row is None else self._row_to_search(row)

    def get_by_search_identity(
        self,
        search_identity: str,
    ) -> InterfaceSearch | None:
        row = (
            self._conn.execute(
                self._select().where(
                    interface_searches_t.c.search_identity == search_identity
                )
            )
            .mappings()
            .first()
        )
        return None if row is None else self._row_to_search(row)

    def get_by_run_uid_full(
        self,
        run_uid_full: str,
    ) -> InterfaceSearch | None:
        row = (
            self._conn.execute(
                self._select().where(
                    interface_searches_t.c.run_uid_full == run_uid_full
                )
            )
            .mappings()
            .first()
        )
        return None if row is None else self._row_to_search(row)

    def get_by_run_id_short(
        self,
        run_id_short: str,
    ) -> InterfaceSearch | None:
        row = (
            self._conn.execute(self._select().where(runs_t.c.id_short == run_id_short))
            .mappings()
            .first()
        )
        return None if row is None else self._row_to_search(row)

    def list(self, *, limit: int | None = None) -> list[InterfaceSearch]:
        stmt = self._select().order_by(interface_searches_t.c.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = self._conn.execute(stmt).mappings().all()
        return [self._row_to_search(row) for row in rows]
