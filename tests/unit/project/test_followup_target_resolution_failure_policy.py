from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.project.application.followups.common import (
    resolve_followup_targets,
    resolve_followup_targets_as_results,
)
from calm.project.application.followups.thermodynamics import (
    ThermodynamicOrchestrator,
)


class _Ids:
    def __init__(self, values):
        self._values = values

    def resolve(self, identifier: str) -> str:
        value = self._values[identifier]
        if isinstance(value, BaseException):
            raise value
        return value


class _Repository:
    def __init__(self, values):
        self._values = values

    def get_by_uid_full(self, uid: str):
        value = self._values.get(uid)
        if isinstance(value, BaseException):
            raise value
        return value


def _uow(*, identifiers, prototypes=None, interfaces=None):
    return SimpleNamespace(
        ids=_Ids(identifiers),
        prototypes=_Repository(prototypes or {}),
        derived_interfaces=_Repository(interfaces or {}),
    )


def test_expected_target_selection_errors_become_skipped_results() -> None:
    uow = _uow(
        identifiers={
            "missing": KeyError("unknown identifier"),
            "wrong-kind": "bulk:one",
        }
    )

    resolved, skipped = resolve_followup_targets_as_results(
        uow,
        ["missing", "wrong-kind"],
    )

    assert resolved == []
    assert [item["reason"] for item in skipped] == [
        "target_not_found",
        "invalid_identifier",
    ]
    assert all(item["status"] == "skipped" for item in skipped)


def test_identifier_repository_failures_are_not_skipped() -> None:
    uow = _uow(identifiers={"target": RuntimeError("database unavailable")})

    with pytest.raises(RuntimeError, match="database unavailable"):
        resolve_followup_targets_as_results(uow, ["target"])


def test_target_repository_failures_are_not_skipped() -> None:
    uow = _uow(
        identifiers={"target": "proto:one"},
        prototypes={"proto:one": RuntimeError("prototype query failed")},
    )

    with pytest.raises(RuntimeError, match="prototype query failed"):
        resolve_followup_targets_as_results(uow, ["target"])


def test_target_repository_value_errors_are_not_skipped() -> None:
    uow = _uow(
        identifiers={"target": "proto:one"},
        prototypes={"proto:one": ValueError("malformed persisted prototype")},
    )

    with pytest.raises(ValueError, match="malformed persisted prototype"):
        resolve_followup_targets_as_results(uow, ["target"])


def test_exact_resolver_rejects_missing_persisted_target() -> None:
    uow = _uow(
        identifiers={"target": "iface:one"},
        interfaces={"iface:one": None},
    )

    with pytest.raises(KeyError, match="No derived interface"):
        resolve_followup_targets(uow, ["target"])


def test_thermodynamic_resolution_preserves_identifier_failures() -> None:
    class Uow:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        ids = SimpleNamespace(
            resolve=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("identifier repository unavailable")
            )
        )

    orchestrator = object.__new__(ThermodynamicOrchestrator)
    orchestrator._uow = Uow()

    with pytest.raises(RuntimeError, match="identifier repository unavailable"):
        orchestrator._resolve_raw_results(["f_raw"])
