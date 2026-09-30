"""Repository for project artifact references."""

from __future__ import annotations

import json

from sqlalchemy import Connection, insert, select
from sqlalchemy.engine import RowMapping

from calm.project.domain.identity_v2 import artifact_user_metadata
from ....domain.models import ArtifactRef
from ....ports.ids import IdResolver
from ....ports.repos import ArtifactRepository
from ..tables import artifacts as artifacts_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyArtifactRepository(ArtifactRepository):
    def __init__(self, conn: Connection, ids: IdResolver) -> None:
        self._conn = conn
        self._ids = ids

    def add(self, artifact: ArtifactRef) -> ArtifactRef:
        stmt = select(artifacts_t).where(artifacts_t.c.uid_full == artifact.uid_full)
        row = self._conn.execute(stmt).mappings().first()
        if row is not None:
            return self._row_to_artifact(row)

        id_short = artifact.id_short or self._ids.ensure_artifact_id(artifact.uid_full)

        metadata_json = (
            json.dumps(artifact.metadata) if artifact.metadata is not None else None
        )
        insert_stmt = insert(artifacts_t).values(
            uid_full=artifact.uid_full,
            id_short=id_short,
            run_uid_full=artifact.run_uid_full,
            kind=artifact.kind,
            uri=artifact.uri,
            metadata_json=metadata_json,
        )
        self._conn.execute(insert_stmt)

        stored_stmt = select(artifacts_t).where(
            artifacts_t.c.uid_full == artifact.uid_full
        )
        stored = self._conn.execute(stored_stmt).mappings().one()
        return self._row_to_artifact(stored)

    def list_for_run(self, run_uid_full: str) -> list[ArtifactRef]:
        stmt = (
            select(artifacts_t)
            .where(artifacts_t.c.run_uid_full == run_uid_full)
            .order_by(artifacts_t.c.artifact_pk.asc())
        )
        rows = self._conn.execute(stmt).mappings().all()
        return [self._row_to_artifact(r) for r in rows]

    def get_by_uid_full(self, uid_full: str) -> ArtifactRef | None:
        stmt = select(artifacts_t).where(artifacts_t.c.uid_full == uid_full)
        row = self._conn.execute(stmt).mappings().first()
        return self._row_to_artifact(row) if row is not None else None

    @staticmethod
    def _row_to_artifact(row: RowMapping) -> ArtifactRef:
        _meta_json = row.get("metadata_json")
        stored_metadata = json.loads(_meta_json) if _meta_json else None
        metadata = (
            artifact_user_metadata(stored_metadata)
            if stored_metadata is not None
            else None
        )

        return ArtifactRef(
            uid_full=row["uid_full"],
            id_short=row["id_short"],
            run_uid_full=row.get("run_uid_full"),
            kind=row.get("kind"),
            uri=row.get("uri"),
            metadata=metadata,
            created_at=_dt_to_str(row.get("created_at")),
        )
