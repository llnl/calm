from __future__ import annotations

import pytest
from sqlalchemy.exc import ResourceClosedError


def test_repositories_and_resolver_cannot_outlive_their_uow(
    sqlite_uow_factory,
) -> None:
    uow = sqlite_uow_factory()
    with uow as entered:
        artifacts = entered.artifacts
        ids = entered.ids

    with pytest.raises(ResourceClosedError):
        artifacts.list_for_run("run:closed")

    with pytest.raises(ResourceClosedError):
        ids.ensure_short_id(tag="b", uid_full="bulk:closed")
