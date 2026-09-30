"""Connection-pool ownership contracts for the SQLAlchemy unit of work."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine

from calm.project.infrastructure.db.tables import metadata
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork


def test_path_owned_uow_disposes_its_engine(tmp_path) -> None:
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(tmp_path / "owned.sqlite")
    with patch.object(uow.engine, "dispose", wraps=uow.engine.dispose) as dispose:
        with uow:
            pass
        dispose.assert_called_once_with()


def test_externally_owned_engine_is_not_disposed(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'external.sqlite'}")
    metadata.create_all(engine)
    try:
        uow = SqlAlchemyUnitOfWork(engine)
        with patch.object(engine, "dispose", wraps=engine.dispose) as dispose:
            with uow:
                pass
            dispose.assert_not_called()
    finally:
        engine.dispose()
