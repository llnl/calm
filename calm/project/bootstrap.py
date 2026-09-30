"""Bootstrap and factory helpers for the v2 (layered) project/workspace API."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def open_workspace(
    root: str | Path,
    *,
    db_name: str = "calm.sqlite",
    out_dir: str = "out",
) -> Any:
    """Open (or create) a v2 workspace rooted at ``root``.

    The workspace uses a SQLAlchemy-backed unit-of-work implementation and a
    filesystem artifact store located at ``<root>/<out_dir>``.
    """

    root_p = Path(root).resolve()

    # Import and validate storage before importing the heavier workspace and
    # optional scientific layers.
    from .infrastructure.db.uow import SqlAlchemyUnitOfWork

    # Validate the database before creating artifact directories. Existing
    # projects must match the current schema exactly. This inspection is
    # read-only and avoids constructing a discarded shared Unit of Work.
    db_path = root_p / db_name
    from .infrastructure.db.schema_version import inspect_sqlite_database

    inspect_sqlite_database(db_path).raise_for_open()

    def uow_factory():
        return SqlAlchemyUnitOfWork.from_sqlite_path(str(db_path))

    from .infrastructure.artifacts.fs_store import FSArtifactStore  # type: ignore
    from .runtime.workspace import Workspace  # type: ignore

    artifact_root = root_p / out_dir
    artifact_store = FSArtifactStore(root=artifact_root)

    # The public workflow is calculator-backed by default.  The synthetic
    # backend remains available only through an explicit backend selection.
    ws = Workspace(
        out_dir=artifact_root,
        artifact_store=artifact_store,
        uow_factory=uow_factory,
        default_relaxation_backend="real",
    )

    return ws


def reproducibility_file_inventory(
    root: str | Path,
    *,
    exclude_paths=(),
):
    """Hash stable project files through the infrastructure SQLite snapshot port."""

    from .infrastructure.reproducibility import (
        SQLITE_LOGICAL_SNAPSHOT_POLICY,
        hash_sqlite_snapshot,
    )
    from .reproducibility import project_file_inventory

    return project_file_inventory(
        Path(root),
        database_snapshot_hasher=hash_sqlite_snapshot,
        database_snapshot_policy=SQLITE_LOGICAL_SNAPSHOT_POLICY,
        exclude_paths=exclude_paths,
    )
