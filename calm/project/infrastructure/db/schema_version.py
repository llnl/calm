"""Current CALM stable project-database schema contract.

CALM opens only the exact schema written by the current codebase. Existing
databases are inspected read-only before use; older, newer, unversioned, or
structurally incomplete databases are rejected rather than migrated, repaired,
or reinterpreted. Historical projects follow the regeneration-only policy.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Connection, select

from calm.project.domain.schema import (
    CURRENT_SCHEMA_VERSION,
    PROJECT_COMPATIBILITY_POLICY,
    PROJECT_RELEASE_STAGE,
)

from .identity_guards import missing_identity_guards
from .tables import metadata, schema_version as schema_version_table

SCHEMA_STATE_NEW = "new"
SCHEMA_STATE_CURRENT = "current"
SCHEMA_STATE_INVALID = "invalid"
SCHEMA_STATE_UNSUPPORTED = "unsupported"
SCHEMA_STATE_CORRUPT = "corrupt"


class ProjectSchemaError(RuntimeError):
    """Raised when an existing project does not match the current schema."""


@dataclass(frozen=True)
class DatabaseSchemaInspection:
    """Read-only assessment of a SQLite project database."""

    path: Path
    state: str
    schema_version: str | None
    missing_tables: tuple[str, ...] = ()
    missing_columns: tuple[tuple[str, tuple[str, ...]], ...] = ()
    missing_triggers: tuple[str, ...] = ()
    message: str = ""

    @property
    def can_open(self) -> bool:
        return self.state in {SCHEMA_STATE_NEW, SCHEMA_STATE_CURRENT}

    def raise_for_open(self) -> None:
        if not self.can_open:
            raise ProjectSchemaError(self.message)


def initialize_schema_version(conn: Connection, calm_version: str) -> None:
    """Write the current schema marker for a newly created database."""

    existing = conn.execute(
        select(schema_version_table.c.version_id).limit(1)
    ).fetchone()
    if existing is None:
        conn.execute(
            schema_version_table.insert().values(
                schema_version=CURRENT_SCHEMA_VERSION,
                calm_version=calm_version,
                description=(
                    f"Initial CALM {PROJECT_RELEASE_STAGE} project schema "
                    f"{CURRENT_SCHEMA_VERSION} ({PROJECT_COMPATIBILITY_POLICY})"
                ),
            )
        )


def _sqlite_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {
        str(row[0]) for row in rows if row and not str(row[0]).startswith("sqlite_")
    }


def _schema_shape_issues(
    conn: sqlite3.Connection,
) -> tuple[tuple[str, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    tables = _sqlite_table_names(conn)
    missing_tables: list[str] = []
    missing_columns: list[tuple[str, tuple[str, ...]]] = []

    for table_name, table in sorted(metadata.tables.items()):
        if table_name not in tables:
            missing_tables.append(table_name)
            continue
        actual = {
            str(row[1])
            for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        }
        required = {column.name for column in table.columns}
        absent = tuple(sorted(required - actual))
        if absent:
            missing_columns.append((table_name, absent))

    return tuple(missing_tables), tuple(missing_columns)


def inspect_sqlite_database(database_path: str | Path) -> DatabaseSchemaInspection:
    """Inspect whether a database is new or exactly matches the current schema."""

    path = Path(database_path)
    if not path.exists() or path.stat().st_size == 0:
        return DatabaseSchemaInspection(
            path=path,
            state=SCHEMA_STATE_NEW,
            schema_version=None,
            message="No initialized CALM database exists yet.",
        )

    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return DatabaseSchemaInspection(
            path=path,
            state=SCHEMA_STATE_INVALID,
            schema_version=None,
            message=f"Could not open SQLite database: {exc}",
        )

    try:
        try:
            tables = _sqlite_table_names(conn)
        except sqlite3.Error as exc:
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_INVALID,
                schema_version=None,
                message=f"Could not inspect SQLite tables: {exc}",
            )

        if not tables:
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_NEW,
                schema_version=None,
                message="The SQLite file is empty and can be initialized.",
            )

        if "schema_version" not in tables:
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_UNSUPPORTED,
                schema_version=None,
                message=(
                    "Existing project databases must use the current CALM schema "
                    f"{CURRENT_SCHEMA_VERSION}; unversioned databases are unsupported."
                ),
            )

        try:
            row = conn.execute(
                "SELECT schema_version FROM schema_version "
                "ORDER BY version_id DESC LIMIT 1"
            ).fetchone()
        except sqlite3.Error as exc:
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_INVALID,
                schema_version=None,
                message=f"Could not read schema version: {exc}",
            )

        raw_version = None if row is None else str(row[0])
        if raw_version is None:
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_UNSUPPORTED,
                schema_version=None,
                message=(
                    "Existing project databases must contain the current schema "
                    f"marker {CURRENT_SCHEMA_VERSION}."
                ),
            )

        if raw_version != CURRENT_SCHEMA_VERSION:
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_UNSUPPORTED,
                schema_version=raw_version,
                message=(
                    f"Database schema {raw_version} is unsupported. CALM stable "
                    f"opens only the current schema {CURRENT_SCHEMA_VERSION}. "
                    "The historical-project policy is regeneration-only: automatic "
                    "migration and in-place repair are not provided. Preserve the "
                    "old project directory and recreate the workflow in a new "
                    "current-format project."
                ),
            )

        missing_tables, missing_columns = _schema_shape_issues(conn)
        missing_triggers = missing_identity_guards(conn)
        if missing_tables or missing_columns or missing_triggers:
            details: list[str] = []
            if missing_tables:
                details.append(f"missing tables: {', '.join(missing_tables)}")
            if missing_columns:
                details.append(
                    "missing columns: "
                    + "; ".join(
                        f"{table}({', '.join(columns)})"
                        for table, columns in missing_columns
                    )
                )
            if missing_triggers:
                details.append(f"missing triggers: {', '.join(missing_triggers)}")
            return DatabaseSchemaInspection(
                path=path,
                state=SCHEMA_STATE_CORRUPT,
                schema_version=raw_version,
                missing_tables=missing_tables,
                missing_columns=missing_columns,
                missing_triggers=missing_triggers,
                message=(
                    f"Database claims schema {CURRENT_SCHEMA_VERSION} but is "
                    f"structurally incomplete: {'; '.join(details)}."
                ),
            )

        return DatabaseSchemaInspection(
            path=path,
            state=SCHEMA_STATE_CURRENT,
            schema_version=raw_version,
            message=f"Database matches current schema {CURRENT_SCHEMA_VERSION}.",
        )
    finally:
        conn.close()
