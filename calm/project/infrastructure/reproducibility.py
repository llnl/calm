"""Infrastructure helpers for reproducibility snapshots."""

from __future__ import annotations

import hashlib
import sqlite3
import struct
from pathlib import Path
from typing import Any


SQLITE_LOGICAL_SNAPSHOT_POLICY = "sqlite_logical_content_v1"

_IGNORED_SQLITE_SCHEMA_PREFIXES = ("sqlite_stat",)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _encoded_sqlite_value(value: Any) -> bytes:
    """Encode one SQLite value without depending on SQL text formatting."""

    if value is None:
        return b"N"
    if isinstance(value, int):
        return b"I" + str(value).encode("ascii")
    if isinstance(value, float):
        return b"F" + struct.pack(">d", value)
    if isinstance(value, str):
        return b"T" + value.encode("utf-8")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return b"B" + bytes(value)
    raise TypeError(
        "SQLite reproducibility snapshots support only NULL, integer, real, "
        f"text, and blob values; received {type(value).__name__}."
    )


def _encoded_row(row: tuple[Any, ...]) -> bytes:
    payload = bytearray()
    payload.extend(len(row).to_bytes(8, "big"))
    for value in row:
        encoded = _encoded_sqlite_value(value)
        payload.extend(len(encoded).to_bytes(8, "big"))
        payload.extend(encoded)
    return bytes(payload)


def hash_sqlite_snapshot(path: Path) -> tuple[str, int]:
    """Hash a deterministic logical snapshot of an SQLite database.

    The hash covers persistent schema objects, persistent pragma values, and
    every table row while deliberately excluding physical page layout,
    freelist state, journal/checkpoint state, and query-planner statistics.
    Consequently, checkpointing, ``VACUUM``, and ``REINDEX`` do not invalidate
    a manifest when the authoritative logical database state is unchanged.

    The returned size is the deterministic logical payload size, not the
    physical ``calm.sqlite`` file size.
    """

    if not path.exists():
        raise FileNotFoundError(path)

    digest = hashlib.sha256()
    logical_size = 0

    def emit(label: bytes, payload: bytes) -> None:
        nonlocal logical_size
        digest.update(len(label).to_bytes(4, "big"))
        digest.update(label)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
        logical_size += len(label) + len(payload)

    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        source.execute("PRAGMA query_only = ON")
        source.execute("BEGIN")

        emit(b"policy", SQLITE_LOGICAL_SNAPSHOT_POLICY.encode("ascii"))
        for pragma in ("application_id", "user_version"):
            value = source.execute(f"PRAGMA {pragma}").fetchone()
            encoded = _encoded_row(tuple(value or ()))
            emit(f"pragma:{pragma}".encode("ascii"), encoded)

        schema_rows = source.execute(
            "SELECT type, name, tbl_name, sql "
            "FROM sqlite_schema "
            "ORDER BY type, name, tbl_name"
        ).fetchall()
        tables: list[str] = []
        for object_type, name, table_name, sql in schema_rows:
            normalized_name = str(name or "")
            if normalized_name.startswith(_IGNORED_SQLITE_SCHEMA_PREFIXES):
                continue
            schema_payload = _encoded_row(
                (
                    str(object_type or ""),
                    normalized_name,
                    str(table_name or ""),
                    None if sql is None else str(sql),
                )
            )
            emit(b"schema", schema_payload)
            if object_type == "table":
                tables.append(normalized_name)

        for table_name in sorted(tables):
            quoted = _quote_identifier(table_name)
            cursor = source.execute(f"SELECT * FROM {quoted}")
            columns = tuple(
                str(description[0]) for description in (cursor.description or ())
            )
            emit(
                f"table:{table_name}:columns".encode("utf-8"),
                _encoded_row(columns),
            )

            row_digests: list[bytes] = []
            row_payload_size = 0
            for raw_row in cursor:
                row_payload = _encoded_row(tuple(raw_row))
                row_payload_size += len(row_payload)
                row_digests.append(hashlib.sha256(row_payload).digest())
            row_digests.sort()
            emit(
                f"table:{table_name}:row_count".encode("utf-8"),
                len(row_digests).to_bytes(8, "big"),
            )
            emit(
                f"table:{table_name}:row_payload_size".encode("utf-8"),
                row_payload_size.to_bytes(8, "big"),
            )
            for row_digest in row_digests:
                emit(f"table:{table_name}:row".encode("utf-8"), row_digest)
            logical_size += row_payload_size

        source.rollback()
    finally:
        source.close()

    return digest.hexdigest(), logical_size
