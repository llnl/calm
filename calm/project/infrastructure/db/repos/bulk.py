"""Repository for authoritative exact-current bulk records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Connection, insert, select, update
from sqlalchemy.sql import func

from calm.project.domain.contracts.bulk_record import current_bulk_structure_record
from ....domain.models import Bulk, BulkReferenceRecord, BulkSummary
from ....ports.ids import IdResolver
from ....ports.repos import BulkRepository
from ..tables import bulks as bulks_t
from ..tables import calculators as calculators_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyBulkRepository(BulkRepository):
    def __init__(self, conn: Connection, ids: IdResolver) -> None:
        self._conn = conn
        self._ids = ids

    @staticmethod
    def _calculator_name(row: Mapping[str, Any]) -> str | None:
        family = row.get("calc_family")
        model = row.get("calc_model")
        if isinstance(family, str) and isinstance(model, str) and family and model:
            return f"{family}:{model}"
        return None

    @staticmethod
    def _incoming_payload(bulk: Bulk) -> dict[str, Any]:
        if bulk.payload is None:
            payload: dict[str, Any] = {}
        elif isinstance(bulk.payload, Mapping):
            payload = dict(bulk.payload)
        else:
            raise TypeError("Current persisted bulk payload must be a mapping or None.")
        current_bulk_structure_record(payload)
        return payload

    @staticmethod
    def _stored_payload(row: Mapping[str, Any]) -> dict[str, Any]:
        payload_json = row.get("payload_json")
        if not isinstance(payload_json, str) or not payload_json:
            raise ValueError("Current bulk rows require non-empty payload_json.")
        try:
            decoded = json.loads(payload_json)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Current bulk payload_json contains invalid JSON."
            ) from exc
        if not isinstance(decoded, Mapping):
            raise ValueError("Current bulk payload_json must decode to a mapping.")
        payload = dict(decoded)
        current_bulk_structure_record(payload)
        return payload

    def _from_row(self, row: Mapping[str, Any]) -> Bulk:
        uid_full = row.get("uid_full")
        if (
            not isinstance(uid_full, str)
            or not uid_full
            or uid_full != uid_full.strip()
        ):
            raise ValueError("Current bulk rows require a non-empty uid_full.")
        id_short = row.get("id_short")
        if (
            not isinstance(id_short, str)
            or not id_short
            or id_short != id_short.strip()
        ):
            raise ValueError("Current bulk rows require a non-empty id_short.")

        return Bulk(
            uid_full=uid_full,
            id_short=id_short,
            label=row.get("label"),
            payload=self._stored_payload(row),
            kind=row.get("kind") or "reference",
            optimized_with_calculator_uid_full=row.get(
                "optimized_with_calculator_uid_full"
            ),
            calculator=self._calculator_name(row),
            created_at=_dt_to_str(row.get("created_at")),
            updated_at=_dt_to_str(row.get("updated_at")),
        )

    @staticmethod
    def _row_columns() -> tuple[Any, ...]:
        return (
            bulks_t.c.uid_full,
            bulks_t.c.id_short,
            bulks_t.c.label,
            bulks_t.c.kind,
            bulks_t.c.optimized_with_calculator_uid_full,
            bulks_t.c.payload_json,
            bulks_t.c.created_at,
            bulks_t.c.updated_at,
            calculators_t.c.family.label("calc_family"),
            calculators_t.c.model.label("calc_model"),
        )

    def upsert(self, bulk: Bulk) -> Bulk:
        """Insert or update one valid current bulk without repairing old state.

        Incoming atomistic payloads are checked before any write.  Existing rows
        are hydrated through the same exact-current contract before an update, so
        malformed or incomplete state raises and must be regenerated rather than
        being silently repaired by a later script run.
        """

        payload = self._incoming_payload(bulk)
        existing = self.get_by_uid_full(bulk.uid_full)
        id_short = bulk.id_short or self._ids.ensure_bulk_id(bulk.uid_full)

        mutable_values = {
            "label": bulk.label,
            "kind": bulk.kind or "reference",
            "optimized_with_calculator_uid_full": (
                bulk.optimized_with_calculator_uid_full
            ),
            "payload_json": json.dumps(payload),
            "updated_at": func.current_timestamp(),
        }

        if existing is None:
            self._conn.execute(
                insert(bulks_t).values(
                    uid_full=bulk.uid_full,
                    id_short=id_short,
                    **mutable_values,
                )
            )
        else:
            # Identity-bearing columns are immutable in schema v2. Do not name
            # uid_full in a no-op UPDATE merely because it is also the lookup key.
            self._conn.execute(
                update(bulks_t)
                .where(bulks_t.c.uid_full == bulk.uid_full)
                .values(**mutable_values)
            )

        stored = self.get_by_uid_full(bulk.uid_full)
        assert stored is not None
        return stored

    def get_by_uid_full(self, uid_full: str) -> Bulk | None:
        stmt = (
            select(*self._row_columns())
            .select_from(
                bulks_t.outerjoin(
                    calculators_t,
                    bulks_t.c.optimized_with_calculator_uid_full
                    == calculators_t.c.uid_full,
                )
            )
            .where(bulks_t.c.uid_full == uid_full)
        )
        row = self._conn.execute(stmt).mappings().one_or_none()
        return None if row is None else self._from_row(row)

    def list(self, *, limit: int | None = None) -> list[BulkSummary]:
        stmt = (
            select(*self._row_columns())
            .select_from(
                bulks_t.outerjoin(
                    calculators_t,
                    bulks_t.c.optimized_with_calculator_uid_full
                    == calculators_t.c.uid_full,
                )
            )
            .order_by(bulks_t.c.bulk_pk.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        bulks = [
            self._from_row(row) for row in self._conn.execute(stmt).mappings().all()
        ]
        out: list[BulkSummary] = []
        for bulk in bulks:
            derived = bulk.derived
            formula = (
                derived.get("formula")
                if isinstance(derived.get("formula"), str)
                else None
            )
            natoms = (
                derived.get("n_atoms")
                if isinstance(derived.get("n_atoms"), int)
                else None
            )

            spacegroup = None
            sg = derived.get("spacegroup")
            if isinstance(sg, dict):
                symbol = sg.get("international") or sg.get("symbol")
                number = sg.get("number")
                if isinstance(symbol, str) and symbol.strip():
                    if isinstance(number, int):
                        spacegroup = f"{symbol.strip()} ({number})"
                    elif isinstance(number, str) and number.isdigit():
                        spacegroup = f"{symbol.strip()} ({number})"

            out.append(
                BulkSummary(
                    uid_full=bulk.uid_full,
                    id_short=bulk.id_short,
                    label=bulk.label,
                    created_at=bulk.created_at,
                    kind=bulk.kind,
                    formula=formula,
                    natoms=natoms,
                    spacegroup=spacegroup,
                    calculator=bulk.calculator,
                )
            )
        return out

    def list_reference_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[BulkReferenceRecord]:
        """Return raw bulk identities without hydrating scientific payloads.

        Workspace validation uses this bounded diagnostic projection so malformed
        current rows can be identified and reported through strict point reads.
        Ordinary repository readers continue to hydrate the exact-current payload.
        """

        stmt = select(
            bulks_t.c.uid_full,
            bulks_t.c.id_short,
            bulks_t.c.label,
        ).order_by(bulks_t.c.bulk_pk.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return [
            BulkReferenceRecord(
                uid_full=str(row["uid_full"]),
                id_short=str(row["id_short"]),
                label=(None if row.get("label") is None else str(row["label"])),
            )
            for row in self._conn.execute(stmt).mappings().all()
        ]
