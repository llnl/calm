"""Repository for dataset definitions and item membership."""

from __future__ import annotations

import json

from sqlalchemy import Connection, insert, select
from sqlalchemy.engine import RowMapping

from ....domain.models import Dataset, DatasetItem
from ....ports.ids import IdResolver
from ....ports.repos import DatasetRepository
from ..tables import dataset_items as dataset_items_t
from ..tables import datasets as datasets_t
from ._common import datetime_to_text as _dt_to_str


class SqlAlchemyDatasetRepository(DatasetRepository):
    """Persist and query authoritative dataset rows without orchestration."""

    def __init__(self, conn: Connection, *, ids: IdResolver):
        self._conn = conn
        self._ids = ids

    @staticmethod
    def _dataset_from_row(row: RowMapping) -> Dataset:
        return Dataset(
            uid_full=row["uid_full"],
            id_short=row.get("id_short"),
            project_id=row.get("project_id"),
            name=row.get("name"),
            description=row.get("description"),
            metadata=(
                json.loads(row.get("metadata_json") or "{}")
                if row.get("metadata_json")
                else None
            ),
            created_at=_dt_to_str(row.get("created_at")),
        )

    @staticmethod
    def _dataset_item_from_row(row: RowMapping) -> DatasetItem:
        return DatasetItem(
            uid_full=row["uid_full"],
            dataset_uid_full=row.get("dataset_uid_full"),
            id_short=row.get("id_short"),
            index=row.get("dataset_index"),
            metadata=(
                json.loads(row.get("metadata_json") or "{}")
                if row.get("metadata_json")
                else None
            ),
            artifact_refs=(
                json.loads(row.get("artifact_refs_json") or "[]")
                if row.get("artifact_refs_json")
                else None
            ),
            created_at=_dt_to_str(row.get("created_at")),
        )

    def create_dataset(
        self,
        *,
        uid_full: str,
        name: str | None = None,
        project_id: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Dataset:
        id_short = self._ids.ensure_short_id(tag="d", uid_full=uid_full)
        self._conn.execute(
            insert(datasets_t).values(
                uid_full=uid_full,
                id_short=id_short,
                project_id=project_id,
                name=name,
                description=description,
                metadata_json=(json.dumps(metadata) if metadata is not None else None),
            ),
        )
        row = (
            self._conn.execute(
                select(datasets_t).where(datasets_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        if row is None:
            raise RuntimeError("Dataset row was not readable after insertion.")
        return self._dataset_from_row(row)

    def get_dataset(self, uid_full: str) -> Dataset | None:
        row = (
            self._conn.execute(
                select(datasets_t).where(datasets_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        return None if row is None else self._dataset_from_row(row)

    def list_datasets(self, *, limit: int | None = None) -> list[Dataset]:
        stmt = select(datasets_t).order_by(datasets_t.c.created_at.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        rows = self._conn.execute(stmt).mappings().all()
        return [self._dataset_from_row(row) for row in rows]

    def add_dataset_item(
        self,
        *,
        uid_full: str,
        dataset_uid_full: str,
        index: int | None = None,
        metadata: dict | None = None,
        artifact_refs: list | None = None,
    ) -> DatasetItem:
        id_short = self._ids.ensure_short_id(tag="t", uid_full=uid_full)
        self._conn.execute(
            insert(dataset_items_t).values(
                uid_full=uid_full,
                id_short=id_short,
                dataset_uid_full=dataset_uid_full,
                dataset_index=index,
                metadata_json=(json.dumps(metadata) if metadata is not None else None),
                artifact_refs_json=(
                    json.dumps(artifact_refs) if artifact_refs is not None else None
                ),
            ),
        )
        row = (
            self._conn.execute(
                select(dataset_items_t).where(dataset_items_t.c.uid_full == uid_full),
            )
            .mappings()
            .first()
        )
        if row is None:
            raise RuntimeError("Dataset-item row was not readable after insertion.")
        return self._dataset_item_from_row(row)

    def list_dataset_items(self, dataset_uid_full: str) -> list[DatasetItem]:
        rows = (
            self._conn.execute(
                select(dataset_items_t)
                .where(dataset_items_t.c.dataset_uid_full == dataset_uid_full)
                .order_by(dataset_items_t.c.dataset_index.asc()),
            )
            .mappings()
            .all()
        )
        return [self._dataset_item_from_row(row) for row in rows]
