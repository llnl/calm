"""Repository for calculator specifications and identities."""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import Connection, insert, select

from calm.calculators.spec import CalculatorSpec
from ....domain.models import Calculator, CalculatorSummary
from ....ports.ids import IdResolver
from ....ports.repos import CalculatorRepository
from ..tables import calculators as calculators_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyCalculatorRepository(CalculatorRepository):
    def __init__(self, conn: Connection, ids: IdResolver) -> None:
        self._conn = conn
        self._ids = ids

    def upsert(self, calc: Calculator) -> Calculator:
        existing = self.get_by_uid_full(calc.uid_full)
        if existing is not None:
            return existing

        id_short = calc.id_short or self._ids.ensure_short_id(
            tag="c", uid_full=calc.uid_full
        )

        canonical_spec = CalculatorSpec.from_dict(calc.spec).to_dict()
        if canonical_spec["family"] != calc.family:
            raise ValueError("Calculator family does not match its canonical spec.")
        if canonical_spec["model"] != calc.model:
            raise ValueError("Calculator model does not match its canonical spec.")
        expected_device = canonical_spec["device"] or "cpu"
        if expected_device != calc.device:
            raise ValueError("Calculator device does not match its canonical spec.")
        spec_json = json.dumps(canonical_spec)

        self._conn.execute(
            insert(calculators_t).values(
                uid_full=calc.uid_full,
                id_short=id_short,
                family=calc.family,
                model=calc.model,
                device=calc.device,
                spec_json=spec_json,
            )
        )

        stored = self.get_by_uid_full(calc.uid_full)
        assert stored is not None
        return stored

    def get_by_uid_full(self, uid_full: str) -> Optional[Calculator]:
        stmt = select(calculators_t).where(calculators_t.c.uid_full == uid_full)
        row = self._conn.execute(stmt).mappings().first()
        if row is None:
            return None
        spec_json = row.get("spec_json")
        if not isinstance(spec_json, str) or not spec_json:
            raise ValueError("Current calculator rows require canonical spec_json.")
        canonical_spec = CalculatorSpec.from_json(spec_json).to_dict()
        if canonical_spec["family"] != row["family"]:
            raise ValueError("Calculator row family does not match spec_json.")
        if canonical_spec["model"] != row["model"]:
            raise ValueError("Calculator row model does not match spec_json.")
        expected_device = canonical_spec["device"] or "cpu"
        if expected_device != row.get("device"):
            raise ValueError("Calculator row device does not match spec_json.")
        return Calculator(
            uid_full=row["uid_full"],
            id_short=row["id_short"],
            family=row["family"],
            model=row["model"],
            device=expected_device,
            spec=canonical_spec,
            created_at=_dt_to_str(row.get("created_at")),
        )

    def list(self, *, limit: int | None = None) -> list[CalculatorSummary]:
        q = select(calculators_t).order_by(calculators_t.c.calculator_pk.asc())
        if limit is not None:
            q = q.limit(limit)
        rows = self._conn.execute(q).mappings().all()
        return [
            CalculatorSummary(
                uid_full=r["uid_full"],
                id_short=r["id_short"],
                family=r["family"],
                model=r["model"],
                device=r.get("device", "cpu"),  # Default to 'cpu' if device is None
                created_at=_dt_to_str(r.get("created_at")),
            )
            for r in rows
        ]
