from __future__ import annotations

import hashlib
import inspect
from contextlib import closing
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from calm.project.bootstrap import open_workspace
from calm.project.domain.schema import (
    AUTOMATIC_PROJECT_MIGRATION_SUPPORTED,
    IN_PLACE_PROJECT_REPAIR_SUPPORTED,
    PROJECT_COMPATIBILITY_POLICY,
    PROJECT_RELEASE_STAGE,
)
from calm.project.infrastructure.db.schema_version import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_STATE_CORRUPT,
    SCHEMA_STATE_CURRENT,
    SCHEMA_STATE_NEW,
    SCHEMA_STATE_UNSUPPORTED,
    ProjectSchemaError,
    inspect_sqlite_database,
)
from calm.project.infrastructure.db.tables import metadata, schema_version
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from calm.public.errors import ProjectPersistenceError
from calm.public.project import open_project


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_versioned_database(path: Path, version: str) -> None:
    engine = create_engine(f"sqlite:///{path}")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            schema_version.insert().values(
                schema_version=version,
                calm_version="test",
                description="test fixture",
            )
        )
    engine.dispose()


def test_missing_database_is_new_and_initializes_current_schema(tmp_path: Path) -> None:
    path = tmp_path / "calm.sqlite"
    assert inspect_sqlite_database(path).state == SCHEMA_STATE_NEW

    uow = SqlAlchemyUnitOfWork.from_sqlite_path(path)
    uow.engine.dispose()

    report = inspect_sqlite_database(path)
    assert report.state == SCHEMA_STATE_CURRENT
    assert report.schema_version == CURRENT_SCHEMA_VERSION

    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute(
            "SELECT schema_version, description FROM schema_version "
            "ORDER BY version_id"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == CURRENT_SCHEMA_VERSION
    assert "stable project schema" in rows[0][1]
    assert PROJECT_COMPATIBILITY_POLICY in rows[0][1]


def test_current_database_reopens_without_rewriting_schema_history(tmp_path: Path) -> None:
    path = tmp_path / "calm.sqlite"
    first = SqlAlchemyUnitOfWork.from_sqlite_path(path)
    first.engine.dispose()
    before = _sha256(path)

    second = SqlAlchemyUnitOfWork.from_sqlite_path(path)
    second.engine.dispose()

    assert inspect_sqlite_database(path).state == SCHEMA_STATE_CURRENT
    with closing(sqlite3.connect(path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert count == 1
    assert _sha256(path) == before


def test_unversioned_database_is_rejected_without_mutation(tmp_path: Path) -> None:
    path = tmp_path / "calm.sqlite"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE bulks (uid_full TEXT NOT NULL)")
        conn.commit()
    before = _sha256(path)

    report = inspect_sqlite_database(path)
    assert report.state == SCHEMA_STATE_UNSUPPORTED
    with pytest.raises(ProjectSchemaError, match="unversioned"):
        SqlAlchemyUnitOfWork.from_sqlite_path(path)

    assert _sha256(path) == before


def test_noncurrent_schema_is_rejected_without_migration(tmp_path: Path) -> None:
    path = tmp_path / "calm.sqlite"
    _seed_versioned_database(path, "v1.3.0")
    before = _sha256(path)

    report = inspect_sqlite_database(path)
    assert report.state == SCHEMA_STATE_UNSUPPORTED
    with pytest.raises(
        ProjectSchemaError,
        match="historical-project policy is regeneration-only",
    ):
        SqlAlchemyUnitOfWork.from_sqlite_path(path)

    assert _sha256(path) == before
    assert not list(tmp_path.glob("*.bak"))


def test_structurally_incomplete_current_database_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "calm.sqlite"
    _seed_versioned_database(path, CURRENT_SCHEMA_VERSION)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("DROP TABLE slabs")
        conn.commit()

    report = inspect_sqlite_database(path)
    assert report.state == SCHEMA_STATE_CORRUPT
    assert "slabs" in report.missing_tables
    with pytest.raises(ProjectSchemaError, match="structurally incomplete"):
        SqlAlchemyUnitOfWork.from_sqlite_path(path)


def test_project_open_surfaces_current_schema_failure(tmp_path: Path) -> None:
    path = tmp_path / "study.calm"
    path.mkdir()
    _seed_versioned_database(path / "calm.sqlite", "v1.3.0")

    with pytest.raises(
        ProjectPersistenceError,
        match="historical-project policy is regeneration-only",
    ):
        open_project(path)


def test_workspace_open_rejects_schema_before_artifact_mutation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "study.calm"
    path.mkdir()
    _seed_versioned_database(path / "calm.sqlite", "v9.0.0")

    with pytest.raises(ProjectSchemaError, match="unsupported"):
        open_workspace(path)

    assert not (path / "out").exists()


def test_project_open_signatures_have_no_migration_policy() -> None:
    assert "migration_policy" not in inspect.signature(open_project).parameters
    assert "migration_policy" not in inspect.signature(open_workspace).parameters


def test_stable_schema_and_historical_project_policy_are_exact() -> None:
    assert CURRENT_SCHEMA_VERSION == "v2.0.0"
    assert PROJECT_RELEASE_STAGE == "stable"
    assert PROJECT_COMPATIBILITY_POLICY == "exact_current_regeneration_only"
    assert AUTOMATIC_PROJECT_MIGRATION_SUPPORTED is False
    assert IN_PLACE_PROJECT_REPAIR_SUPPORTED is False


def test_current_database_missing_identity_guard_is_rejected(tmp_path: Path) -> None:
    from calm.project.infrastructure.db.identity_guards import identity_guard_names

    path = tmp_path / "calm.sqlite"
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(path)
    uow.engine.dispose()
    missing = identity_guard_names()[0]

    with closing(sqlite3.connect(path)) as conn:
        conn.execute(f'DROP TRIGGER "{missing}"')
        conn.commit()

    report = inspect_sqlite_database(path)
    assert report.state == SCHEMA_STATE_CORRUPT
    assert report.missing_triggers == (missing,)
    with pytest.raises(ProjectSchemaError, match="structurally incomplete"):
        SqlAlchemyUnitOfWork.from_sqlite_path(path)
