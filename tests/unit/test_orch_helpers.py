from __future__ import annotations

import json
from pathlib import Path

import pytest

from calm.project.application.artifacts import ArtifactsService
from calm.project.application.followups.orch_helpers import (
    load_existing_followups,
    persist_artifact_payloads,
    persist_followups_with_edges,
)
from calm.project.domain.models import FollowupResult
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.infrastructure.db.tables import (
    prototypes as prototypes_t,
    runs as runs_t,
)


def _insert_scaffold(uow, *, run_uid: str = "run:1", run_id: str = "r1") -> None:
    uow.connection.execute(
        runs_t.insert().values(
            uid_full=run_uid,
            id_short=run_id,
            run_type="test",
            status="done",
            spec_json=json.dumps({}),
        )
    )
    if uow.prototypes.get_by_uid_full("proto:x") is None:
        uow.connection.execute(
            prototypes_t.insert().values(
                uid_full="proto:x",
                id_short="p_x",
                run_uid_full=run_uid,
                slab_a_uid_full="slab:a",
                slab_b_uid_full="slab:b",
                payload_json=json.dumps({}),
            )
        )


def _artifact_service(schema_uow_factory, tmp_path: Path) -> ArtifactsService:
    return ArtifactsService(
        uow_factory=schema_uow_factory,
        store=FSArtifactStore(tmp_path / "artifacts"),
    )


def _followup(*, uid: str, run_uid: str, kind: str = "test_followup") -> FollowupResult:
    return FollowupResult(
        uid_full=uid,
        id_short=uid.replace(":", "_"),
        run_uid_full=run_uid,
        prototype_uid_full="proto:x",
        target_uid_full="proto:x",
        target_kind="prototype",
        kind=kind,
        status="done",
        best_energy=0.0,
        param1=0.0,
        param2=0.0,
        n_points=0,
        payload={"value": 1},
    )


def test_load_existing_followups_empty(schema_uow_factory) -> None:
    uow = schema_uow_factory()
    with uow as entered:
        result = load_existing_followups(
            entered,
            run_uid_full="run:missing",
            kind="test_followup",
            targets=[],
        )
    assert result == {}


def test_existing_followups_are_scoped_to_run_and_kind(schema_uow_factory) -> None:
    uow = schema_uow_factory()
    with uow as entered:
        _insert_scaffold(entered)
        _insert_scaffold(entered, run_uid="run:2", run_id="r2")
        persist_followups_with_edges(
            entered,
            [_followup(uid="followup:1", run_uid="run:1")],
        )
        persist_followups_with_edges(
            entered,
            [_followup(uid="followup:2", run_uid="run:2")],
        )
        persist_followups_with_edges(
            entered,
            [
                _followup(
                    uid="followup:other",
                    run_uid="run:1",
                    kind="other_followup",
                )
            ],
        )
        existing = load_existing_followups(
            entered,
            run_uid_full="run:1",
            kind="test_followup",
            targets=[{"prototype_uid_full": "proto:x"}],
        )

    assert list(existing) == [("proto:x", "proto:x")]
    assert existing[("proto:x", "proto:x")].uid_full == "followup:1"


def test_persist_artifact_payloads_and_followups(
    schema_uow_factory,
    tmp_path: Path,
) -> None:
    uow = schema_uow_factory()
    with uow as entered:
        _insert_scaffold(entered)

    artifact_service = _artifact_service(schema_uow_factory, tmp_path)
    with uow as entered:
        artifacts = persist_artifact_payloads(
            uow=entered,
            run_uid="run:1",
            proto_uid="proto:x",
            target_uid="t:1",
            artifact_payloads=[{"foo": "bar"}],
            artifacts=artifact_service,
        )
        assert len(artifacts) == 1
        stored_artifacts = entered.artifacts.list_for_run("run:1")
        assert any(item.uid_full == artifacts[0] for item in stored_artifacts)
        artifact_edges = entered.edges.list(
            src_uid_full="run:1",
            kind="run_to_artifact",
        )
        assert any(edge.dst_uid_full == artifacts[0] for edge in artifact_edges)

        followup = _followup(uid="followup:1", run_uid="run:1", kind="test")
        stored = persist_followups_with_edges(entered, [followup])
        assert [item.uid_full for item in stored] == [followup.uid_full]
        rows = entered.followups.list(run_uid_full="run:1")
        assert any(item.uid_full == followup.uid_full for item in rows)
        edges = entered.edges.list(src_uid_full="run:1", kind="run_to_followup")
        assert any(edge.dst_uid_full == followup.uid_full for edge in edges)


def test_artifact_identity_includes_target_context(
    schema_uow_factory,
    tmp_path: Path,
) -> None:
    uow = schema_uow_factory()
    artifact_service = _artifact_service(schema_uow_factory, tmp_path)
    with uow as entered:
        _insert_scaffold(entered)
        first = persist_artifact_payloads(
            entered,
            "run:1",
            "proto:x",
            "target:1",
            [{"value": 1}],
            artifacts=artifact_service,
        )
        second = persist_artifact_payloads(
            entered,
            "run:1",
            "proto:x",
            "target:2",
            [{"value": 1}],
            artifacts=artifact_service,
        )
    assert first != second


def test_followup_and_edges_roll_back_together(
    schema_uow_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uow = schema_uow_factory()
    with uow as entered:
        _insert_scaffold(entered)

    with pytest.raises(RuntimeError, match="edge failure"):
        with uow as entered:
            def fail_edge(**_kwargs) -> None:
                raise RuntimeError("edge failure")

            monkeypatch.setattr(entered.edges, "add", fail_edge)
            persist_followups_with_edges(
                entered,
                [_followup(uid="followup:rollback", run_uid="run:1")],
            )

    with uow as entered:
        assert entered.followups.get_by_uid_full("followup:rollback") is None


def test_helpers_require_an_entered_uow(schema_uow_factory) -> None:
    uow = schema_uow_factory()
    with pytest.raises(ValueError, match="entered UnitOfWork"):
        persist_artifact_payloads(
            uow,
            "run:1",
            "proto:x",
            "target:1",
            [],
            artifacts=None,
        )
