"""Lightweight SQLite-based unit-of-work used by tests and minimal workspaces.

This module provides a thin SqlAlchemy-backed unit-of-work implementation used
by the project's workspace layer. The implementation is intentionally small and
keeps imports local where appropriate to avoid heavy runtime dependencies for
simple tasks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import Connection

from calm._version import get_version

from ...ports.uow import UnitOfWork
from .repos import (
    SqlAlchemyArtifactRepository,
    SqlAlchemyBulkRepository,
    SqlAlchemyCalculatorRepository,
    SqlAlchemyCampaignRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyDerivedInterfaceRepository,
    SqlAlchemyEdgeRepository,
    SqlAlchemyFollowupResultRepository,
    ProjectConfigurationRepository,
    SqlAlchemyInterfaceSearchRepository,
    SqlAlchemyPrototypeRepository,
    SqlAlchemyRunRepository,
    SqlAlchemySlabRepository,
)
from .identity_guards import initialize_identity_guards
from .schema_version import (
    SCHEMA_STATE_CURRENT,
    SCHEMA_STATE_NEW,
    ProjectSchemaError,
    initialize_schema_version,
    inspect_sqlite_database,
)
from .tables import metadata


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy-backed unit-of-work.

    Notes
    -----
    This unit-of-work is intentionally *re-entrant*: nested ``with uow:`` blocks
    share a single connection and only commit/rollback/close at the outermost
    exit. This prevents accidental connection closure when application services
    compose other services that also open a unit-of-work.
    """

    def __init__(
        self,
        engine: Engine,
        *,
        connection: Optional[Connection] = None,
        leave_open: bool = False,
        owns_engine: bool = False,
    ) -> None:
        self.engine = engine
        self.connection = connection
        self.leave_open = leave_open
        self.owns_engine = owns_engine

        # Internal state for safe nested usage.
        self._depth: int = 0
        self._rollback_only: bool = False

        # Repos (populated on __enter__)
        self.ids: Any = None
        self.bulks: Any = None
        self.slabs: Any = None
        self.calculators: Any = None
        self.runs: Any = None
        self.interface_searches: Any = None
        self.artifacts: Any = None
        self.prototypes: Any = None
        self.followups: Any = None
        self.edges: Any = None
        self.derived_interfaces: Any = None
        self.datasets: Any = None
        self.campaigns: Any = None
        self.project_configuration: Any = None

    @classmethod
    def from_sqlite_path(
        cls,
        path: str | Path,
    ) -> "SqlAlchemyUnitOfWork":
        """Open a new or current-schema SQLite project.

        CALM stable supports only the exact schema written by the current
        codebase. Existing databases are validated before opening and are never
        migrated, reinterpreted, or silently repaired.
        """

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        inspection = inspect_sqlite_database(p)
        inspection.raise_for_open()

        if inspection.state == SCHEMA_STATE_NEW:
            engine = create_engine(f"sqlite:///{p}")
            try:
                metadata.create_all(engine)
                with engine.begin() as conn:
                    initialize_schema_version(conn, get_version())
                    initialize_identity_guards(conn)
            except Exception:
                engine.dispose()
                raise
        elif inspection.state == SCHEMA_STATE_CURRENT:
            engine = create_engine(f"sqlite:///{p}")
        else:  # pragma: no cover - guarded by raise_for_open
            raise ProjectSchemaError(inspection.message)

        return cls(engine, owns_engine=True)

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        # Only initialize connection + repositories on the outermost enter.
        if self._depth == 0:
            if self.connection is None:
                self.connection = self.engine.connect()

            conn = self.connection

            # IdResolver must be constructed before repositories that depend on
            # short-id formatting / resolution. Use the extracted implementation
            # so it can be tested independently.
            from .id_resolver import SqlAlchemyIdResolver

            ids = SqlAlchemyIdResolver(conn)
            self.ids = ids

            # Repositories that emit/resolve short ids require the IdResolver.
            self.bulks = SqlAlchemyBulkRepository(conn, ids=ids)
            self.slabs = SqlAlchemySlabRepository(conn, ids=ids)
            self.calculators = SqlAlchemyCalculatorRepository(conn, ids=ids)
            self.runs = SqlAlchemyRunRepository(conn, ids=ids)
            self.interface_searches = SqlAlchemyInterfaceSearchRepository(conn)
            self.artifacts = SqlAlchemyArtifactRepository(conn, ids=ids)
            self.derived_interfaces = SqlAlchemyDerivedInterfaceRepository(
                conn, ids=ids
            )
            # Repositories that operate purely on stored records do not.
            self.prototypes = SqlAlchemyPrototypeRepository(conn)
            self.followups = SqlAlchemyFollowupResultRepository(conn)
            self.edges = SqlAlchemyEdgeRepository(conn)
            self.project_configuration = ProjectConfigurationRepository(conn)
            self.campaigns = SqlAlchemyCampaignRepository(conn, ids=ids)
            # Dataset persistence is a required current-schema capability.
            self.datasets = SqlAlchemyDatasetRepository(conn, ids=ids)

        self._depth += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        # Mark rollback-only if *any* nested block exits with an exception.
        if exc is not None:
            self._rollback_only = True

        if self._depth > 0:
            self._depth -= 1

        # Only finalize on the outermost exit.
        if self._depth > 0:
            return

        try:
            if exc is None and not self._rollback_only:
                self.commit()
            else:
                self.rollback()
        finally:
            self._rollback_only = False
            if not self.leave_open and self.connection is not None:
                self.connection.close()
                self.connection = None
            if not self.leave_open and self.owns_engine:
                self.engine.dispose()

    def commit(self) -> None:
        if self.connection is not None:
            self.connection.commit()

    def rollback(self) -> None:
        if self.connection is not None:
            self.connection.rollback()
