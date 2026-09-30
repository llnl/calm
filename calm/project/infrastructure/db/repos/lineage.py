"""Repository for authoritative lineage edges."""

from __future__ import annotations

import json

from sqlalchemy import Connection, insert, select
from sqlalchemy import text as sa_text

from calm.serialization.regression import sha256_hex
from ....domain.models import Edge
from ....ports.repos import EdgeRepository
from ..payload_helpers import payload_canonical_json_and_hash
from ..tables import edges as edges_t


class SqlAlchemyEdgeRepository(EdgeRepository):
    """SQLAlchemy repository for provenance edges."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def add(
        self,
        *,
        src_uid_full: str,
        dst_uid_full: str,
        kind: str,
        payload: dict | None = None,
    ) -> None:
        payload_json, phash = payload_canonical_json_and_hash(payload)

        stmt = insert(edges_t).values(
            src_uid_full=src_uid_full,
            dst_uid_full=dst_uid_full,
            kind=kind,
            payload_json=payload_json,
            payload_hash=phash,
        )

        # For SQLite, prefer OR IGNORE semantic to avoid raising on duplicate
        if getattr(self._conn.dialect, "name", "") == "sqlite":
            # SQLAlchemy's prefix_with applies literally to generated SQL. For
            # INSERT with OR IGNORE we can emit a raw SQL string instead of
            # relying on prefixing twice (which leads to malformed SQL when the
            # statement already contains a prefix). Use textual INSERT here.
            sql = sa_text(
                "INSERT OR IGNORE INTO edges "
                "(src_uid_full, dst_uid_full, kind, payload_json, payload_hash) "
                "VALUES (:src, :dst, :kind, :payload_json, :payload_hash)"
            )
            params = {
                "src": src_uid_full,
                "dst": dst_uid_full,
                "kind": kind,
                "payload_json": payload_json,
                "payload_hash": phash,
            }
            self._conn.execute(sql, params)
            return

        self._conn.execute(stmt)

    def list(
        self,
        *,
        src_uid_full: str | None = None,
        dst_uid_full: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[Edge]:
        stmt = select(
            edges_t.c.src_uid_full,
            edges_t.c.dst_uid_full,
            edges_t.c.kind,
            edges_t.c.payload_json,
            edges_t.c.payload_hash,
            edges_t.c.created_at,
        )

        if src_uid_full is not None:
            stmt = stmt.where(edges_t.c.src_uid_full == src_uid_full)
        if dst_uid_full is not None:
            stmt = stmt.where(edges_t.c.dst_uid_full == dst_uid_full)
        if kind is not None:
            stmt = stmt.where(edges_t.c.kind == kind)

        stmt = stmt.order_by(edges_t.c.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        rows = self._conn.execute(stmt).mappings().all()
        out: list[Edge] = []
        for r in rows:
            payload_json = r.get("payload_json")
            if not isinstance(payload_json, str) or not payload_json:
                raise ValueError("Current edge rows require canonical payload_json.")
            payload = json.loads(payload_json)
            if not isinstance(payload, dict):
                raise ValueError("Current edge payload_json must decode to a mapping.")
            canonical_json, expected_hash = payload_canonical_json_and_hash(payload)
            if payload_json != canonical_json:
                raise ValueError("Current edge payload_json must be canonical.")
            if r.get("payload_hash") != expected_hash:
                raise ValueError(
                    "Current edge payload_hash does not match payload_json."
                )

            src = str(r["src_uid_full"])
            dst = str(r["dst_uid_full"])
            k = str(r["kind"])
            identity_json = json.dumps(
                {
                    "src_uid_full": src,
                    "dst_uid_full": dst,
                    "kind": k,
                    "payload_hash": expected_hash,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            uid_full = "edge:" + sha256_hex(identity_json)

            out.append(
                Edge(
                    uid_full=uid_full,
                    src_uid_full=src,
                    dst_uid_full=dst,
                    kind=k,
                    payload=payload,
                    created_at=(
                        str(r.get("created_at"))
                        if r.get("created_at") is not None
                        else None
                    ),
                )
            )

        return out
