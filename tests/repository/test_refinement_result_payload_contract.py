"""Repository enforcement for exact-current refinement results."""

from __future__ import annotations

import json

import pytest

from calm.project.domain.identity_v2 import (
    followup_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import FollowupResult
from calm.project.infrastructure.db.tables import (
    followup_results as followups_t,
    prototypes as prototypes_t,
    runs as runs_t,
)
from test_helpers import make_current_strain_result_payload


def _insert_scaffold(uow) -> None:
    uow.connection.execute(
        runs_t.insert().values(
            uid_full="run:refinement",
            id_short="r_refinement",
            run_type="strain_partition_scan",
            status="done",
            spec_json=json.dumps({"targets": []}),
        )
    )
    uow.connection.execute(
        prototypes_t.insert().values(
            uid_full="proto:refinement",
            id_short="p_refinement",
            run_uid_full="run:refinement",
            slab_a_uid_full="slab:a",
            slab_b_uid_full="slab:b",
            payload_json=json.dumps({}),
        )
    )


def _result(payload: dict | None = None) -> FollowupResult:
    current = payload or make_current_strain_result_payload(alpha=0.25, value=0.1)
    uid = persisted_entity_uid_v2(
        "followup_result",
        followup_identity_payload(
            run_uid_full="run:refinement",
            prototype_uid_full="proto:refinement",
            target_uid_full="proto:refinement",
            target_kind="prototype",
            kind="strain_partition_scan",
        ),
    )
    return FollowupResult(
        uid_full=uid,
        id_short="f_refinement",
        run_uid_full="run:refinement",
        prototype_uid_full="proto:refinement",
        target_uid_full="proto:refinement",
        target_kind="prototype",
        kind="strain_partition_scan",
        status="done",
        best_energy=current["selection"]["value"],
        param1=current["selection"]["alpha"],
        param2=None,
        n_points=len(current["points"]),
        payload=current,
    )


def test_refinement_result_roundtrips_with_verified_payload_and_identity(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _result()
        stored = uow.followups.upsert_many([requested])
        assert stored == [requested]

    with schema_uow_factory() as uow:
        reopened = uow.followups.get_by_uid_full(requested.uid_full)

    assert reopened is not None
    assert reopened.uid_full == requested.uid_full
    assert reopened.payload == requested.payload
    point = reopened.payload["points"][0]
    assert point["side_a_principal_log_strains"] == [-0.005, 0.01]
    assert point["side_b_principal_log_strains"] == [-0.03, 0.015]
    assert point["side_a_airm_distance"] + point[
        "side_b_airm_distance"
    ] == pytest.approx(2.0 * (0.02**2 + 0.04**2) ** 0.5)
    assert point["interface_area_A2"] == pytest.approx(10.0)
    assert reopened.best_energy == requested.best_energy
    assert reopened.param1 == requested.param1


def test_refinement_result_writer_rejects_wrong_identity_and_historical_payload(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        with pytest.raises(ValueError, match="identity does not match"):
            uow.followups.upsert_many(
                [
                    _result().__class__(
                        **{**_result().__dict__, "uid_full": "followup:wrong"}
                    )
                ]
            )

        payload = make_current_strain_result_payload()
        payload["target_uid_full"] = "proto:refinement"
        with pytest.raises(ValueError, match="unsupported or historical"):
            uow.followups.upsert_many([_result(payload)])


def test_refinement_result_reopen_fails_closed_on_tampered_payload(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _result()
        uow.followups.upsert_many([requested])
        raw = (
            uow.connection.execute(
                followups_t.select().where(followups_t.c.uid_full == requested.uid_full)
            )
            .mappings()
            .one()
        )
        payload = json.loads(raw["payload_json"])
        payload["selection"]["alpha"] = 0.5
        uow.connection.execute(
            followups_t.update()
            .where(followups_t.c.uid_full == requested.uid_full)
            .values(payload_json=json.dumps(payload))
        )

    with schema_uow_factory() as uow:
        with pytest.raises(ValueError, match="selection alpha"):
            uow.followups.get_by_uid_full(requested.uid_full)


def test_refinement_upsert_rejects_conflicting_result_for_same_identity(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        first = _result()
        uow.followups.upsert_many([first])

        payload = make_current_strain_result_payload(alpha=0.5, value=0.2)
        conflicting = _result(payload)
        with pytest.raises(ValueError, match="different scientific results"):
            uow.followups.upsert_many([conflicting])
