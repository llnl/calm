"""Current persisted-identity constraints for CALM project databases.

CALM stable writes one canonical version-2 UID form for every persisted entity.
These SQLite triggers reject malformed inserts and prevent in-place mutation of
identity-bearing primary UIDs.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from sqlalchemy import Connection, text

_ENTITY_TABLE_PREFIXES: dict[str, str] = {
    "artifacts": "artifact",
    "bulks": "bulk",
    "calculators": "calc",
    "campaign_runs": "campaign_run",
    "campaigns": "campaign",
    "dataset_items": "dataset_item",
    "datasets": "dataset",
    "derived_interfaces": "iface",
    "followup_results": "followup",
    "prototypes": "proto",
    "runs": "run",
    "slabs": "slab",
}


def identity_guard_names() -> tuple[str, ...]:
    """Return the complete current trigger-name set."""

    names: list[str] = []
    for table in sorted(_ENTITY_TABLE_PREFIXES):
        names.append(f"trg_identity_v2_{table}_insert")
        names.append(f"trg_identity_v2_{table}_update")
    return tuple(names)


def _guard_statements() -> Iterable[str]:
    for table, entity_prefix in sorted(_ENTITY_TABLE_PREFIXES.items()):
        uid_prefix = f"{entity_prefix}:v2:"
        digest_start = len(uid_prefix) + 1
        expected_length = len(uid_prefix) + 64
        entity_label = entity_prefix.replace("_", " ")
        yield f'''
            CREATE TRIGGER IF NOT EXISTS "trg_identity_v2_{table}_insert"
            BEFORE INSERT ON "{table}"
            BEGIN
                SELECT RAISE(ABORT, 'CALM requires a canonical {entity_label} UID')
                WHERE NEW.uid_full IS NULL
                   OR substr(NEW.uid_full, 1, {len(uid_prefix)}) <> '{uid_prefix}'
                   OR length(NEW.uid_full) <> {expected_length}
                   OR substr(NEW.uid_full, {digest_start}) GLOB '*[^0-9a-f]*';
            END
        '''
        yield f'''
            CREATE TRIGGER IF NOT EXISTS "trg_identity_v2_{table}_update"
            BEFORE UPDATE OF uid_full ON "{table}"
            BEGIN
                SELECT RAISE(ABORT, 'CALM canonical {entity_label} UIDs are immutable');
            END
        '''


def initialize_identity_guards(conn: Connection) -> None:
    """Create all current persisted-identity triggers."""

    for statement in _guard_statements():
        conn.execute(text(statement))


def missing_identity_guards(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Return required identity triggers absent from a SQLite database."""

    present = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).fetchall()
    }
    return tuple(name for name in identity_guard_names() if name not in present)


__all__ = [
    "identity_guard_names",
    "initialize_identity_guards",
    "missing_identity_guards",
]
