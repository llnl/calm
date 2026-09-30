"""Repository for campaign definitions and run membership."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, insert, select, update

from calm.project.domain.identity_v2 import (
    campaign_run_identity_payload,
    persisted_entity_uid_v2,
)
from calm.serialization.regression import deterministic_json, sha256_hex
from ....domain.models import Campaign, CampaignRun
from ....ports.ids import IdResolver
from ....ports.repos import CampaignRepository
from ..tables import campaign_runs as campaign_runs_t
from ..tables import campaigns as campaigns_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyCampaignRepository(CampaignRepository):
    """Row-focused repository for campaigns and deterministic campaign runs."""

    def __init__(self, conn: Connection, ids: IdResolver) -> None:
        self._conn = conn
        self._ids = ids

    @staticmethod
    def _campaign_from_row(row) -> Campaign:
        return Campaign(
            uid_full=row["uid_full"],
            id_short=row.get("id_short"),
            project_id=row.get("project_id"),
            name=row.get("name"),
            spec=json.loads(row.get("spec_json") or "{}"),
            created_at=_dt_to_str(row.get("created_at")),
        )

    @staticmethod
    def _campaign_run_from_row(row) -> CampaignRun:
        return CampaignRun(
            uid_full=row["uid_full"],
            id_short=row.get("id_short"),
            campaign_uid_full=row.get("campaign_uid_full"),
            run_spec_hash=row.get("run_spec_hash"),
            backend_id=row.get("backend_id"),
            status=row.get("status"),
            started_at=_dt_to_str(row.get("started_at")),
            finished_at=_dt_to_str(row.get("finished_at")),
        )

    def create_campaign(
        self,
        *,
        uid_full: str,
        name: str | None = None,
        project_id: str | None = None,
        spec: dict | None = None,
    ) -> Campaign:
        row = (
            self._conn.execute(
                select(campaigns_t).where(campaigns_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        if row is None:
            id_short = self._ids.ensure_short_id(tag="y", uid_full=uid_full)
            self._conn.execute(
                insert(campaigns_t).values(
                    uid_full=uid_full,
                    id_short=id_short,
                    name=name,
                    project_id=project_id,
                    spec_json=json.dumps(spec or {}, sort_keys=True),
                ),
            )
            row = (
                self._conn.execute(
                    select(campaigns_t).where(campaigns_t.c.uid_full == uid_full),
                )
                .mappings()
                .first()
            )
        if row is None:
            raise RuntimeError("Campaign insert did not produce a persisted row.")
        return self._campaign_from_row(row)

    def get_campaign(self, uid_full: str) -> Campaign | None:
        row = (
            self._conn.execute(
                select(campaigns_t).where(campaigns_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        return None if row is None else self._campaign_from_row(row)

    def list_campaigns(self, *, limit: int | None = None) -> list[Campaign]:
        stmt = select(campaigns_t).order_by(campaigns_t.c.campaign_pk.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = self._conn.execute(stmt).mappings().all()
        return [self._campaign_from_row(row) for row in rows]

    def create_or_get_campaign_run(
        self,
        *,
        campaign_uid_full: str,
        run_spec: dict,
        backend_id: str | None = None,
        status: str | None = None,
    ) -> CampaignRun:
        spec_json = deterministic_json(run_spec or {}, float_ndigits=12)
        run_spec_hash = sha256_hex(spec_json)
        normalized_backend = backend_id or ""
        uid_full = persisted_entity_uid_v2(
            "campaign_run",
            campaign_run_identity_payload(
                campaign_uid_full=campaign_uid_full,
                run_spec_hash=run_spec_hash,
                backend_id=normalized_backend,
            ),
        )

        row = (
            self._conn.execute(
                select(campaign_runs_t).where(campaign_runs_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        if row is None:
            row = (
                self._conn.execute(
                    select(campaign_runs_t).where(
                        campaign_runs_t.c.campaign_uid_full == campaign_uid_full,
                        campaign_runs_t.c.run_spec_hash == run_spec_hash,
                        campaign_runs_t.c.backend_id == normalized_backend,
                    ),
                )
                .mappings()
                .first()
            )
        if row is None:
            id_short = self._ids.ensure_short_id(tag="x", uid_full=uid_full)
            self._conn.execute(
                insert(campaign_runs_t).values(
                    uid_full=uid_full,
                    id_short=id_short,
                    campaign_uid_full=campaign_uid_full,
                    run_spec_hash=run_spec_hash,
                    backend_id=normalized_backend,
                    status=status,
                ),
            )
            row = (
                self._conn.execute(
                    select(campaign_runs_t).where(
                        campaign_runs_t.c.uid_full == uid_full
                    ),
                )
                .mappings()
                .first()
            )
        if row is None:
            raise RuntimeError("Campaign-run insert did not produce a persisted row.")
        return self._campaign_run_from_row(row)

    def get_campaign_run(self, uid_full: str) -> CampaignRun | None:
        row = (
            self._conn.execute(
                select(campaign_runs_t).where(campaign_runs_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        return None if row is None else self._campaign_run_from_row(row)

    def list_campaign_runs(
        self,
        *,
        campaign_uid_full: str | None = None,
        limit: int | None = None,
    ) -> list[CampaignRun]:
        stmt = select(campaign_runs_t).order_by(campaign_runs_t.c.campaign_run_pk.asc())
        if campaign_uid_full is not None:
            stmt = stmt.where(campaign_runs_t.c.campaign_uid_full == campaign_uid_full)
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = self._conn.execute(stmt).mappings().all()
        return [self._campaign_run_from_row(row) for row in rows]

    def mark_campaign_run(self, uid_full: str, *, status: str) -> CampaignRun | None:
        values: dict[str, Any] = {"status": str(status)}
        now = datetime.now(timezone.utc)
        if status == "running":
            values["started_at"] = now
            values["finished_at"] = None
        elif status in {"completed", "partial", "failed", "skipped"}:
            values["finished_at"] = now
        self._conn.execute(
            update(campaign_runs_t)
            .where(campaign_runs_t.c.uid_full == uid_full)
            .values(**values),
        )
        return self.get_campaign_run(uid_full)
