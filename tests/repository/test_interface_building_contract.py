from types import SimpleNamespace

import pytest

from calm.project.application.interface_building import (
    build_interface_model_from_prototype,
)


class _FailingIds:
    def resolve_prototype(self, identifier: str) -> str:
        raise RuntimeError(f"resolution failed for {identifier}")


def test_interface_building_requires_entered_uow():
    uow = SimpleNamespace(_depth=0, ids=_FailingIds())
    with pytest.raises(ValueError, match="entered UnitOfWork"):
        build_interface_model_from_prototype(uow, "p_missing")


def test_interface_building_propagates_identifier_failure_before_backend_import():
    uow = SimpleNamespace(_depth=1, ids=_FailingIds())
    with pytest.raises(RuntimeError, match="resolution failed"):
        build_interface_model_from_prototype(uow, "p_missing")
