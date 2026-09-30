from __future__ import annotations

import json

from energy_result_fixtures import failed_raw_energy_payload

from calm.project.application.followups.common import persisted_followup_uid
from calm.project.domain.models import FollowupResult, Slab
from slab_record_fixtures import current_slab_payload, current_slab_uid


def test_followup_repository_roundtrips_failed_status(schema_uow_factory) -> None:
    """Persisted follow-up failures must not reload as successful rows."""

    from calm.project.infrastructure.db.tables import bulks, prototypes, runs

    uow = schema_uow_factory("followup-status.sqlite")
    with uow as active:
        active.connection.execute(
            bulks.insert().values(
                uid_full="bulk:followup-status",
                id_short="b_fstat01",
                payload_json=json.dumps({}),
            )
        )
        slab_rows = []
        for token, short in (
            ("slab:followup-status:a", "s_fstata"),
            ("slab:followup-status:b", "s_fstatb"),
        ):
            payload = current_slab_payload(
                bulk_uid_full="bulk:followup-status",
                user_payload={"fixture_token": token},
            )
            uid = current_slab_uid(
                bulk_uid_full="bulk:followup-status",
                miller=(0, 0, 1),
                payload=payload,
            )
            slab_rows.append(
                Slab(
                    uid_full=uid,
                    id_short=short,
                    bulk_uid_full="bulk:followup-status",
                    bulk_id_short="b_fstat01",
                    miller=(0, 0, 1),
                    payload=payload,
                )
            )
        active.slabs.create_many(slab_rows)
        active.connection.execute(
            runs.insert().values(
                uid_full="run:followup-status",
                id_short="r_fstat01",
                run_type="energy_stage",
                status="failed",
                spec_json=json.dumps({"kind": "energy_stage"}),
            )
        )
        active.connection.execute(
            prototypes.insert().values(
                uid_full="proto:followup-status",
                id_short="p_fstat01",
                run_uid_full="run:followup-status",
                slab_a_uid_full=slab_rows[0].uid_full,
                slab_b_uid_full=slab_rows[1].uid_full,
                payload_json=json.dumps({}),
            )
        )
        followup_uid = persisted_followup_uid(
            run_uid_full="run:followup-status",
            prototype_uid_full="proto:followup-status",
            target_uid_full="proto:followup-status",
            target_kind="prototype",
            kind="energy_stage",
        )
        failure_payload = failed_raw_energy_payload(
            message="energy must be finite",
        )
        failure_payload["failure"] = {
            "exception_type": "ValueError",
            "message": "energy must be finite",
            "module": "builtins",
        }
        active.followups.upsert_many(
            [
                FollowupResult(
                    uid_full=followup_uid,
                    id_short="f_fstat01",
                    run_uid_full="run:followup-status",
                    prototype_uid_full="proto:followup-status",
                    target_uid_full="proto:followup-status",
                    target_kind="prototype",
                    kind="energy_stage",
                    status="failed",
                    payload=failure_payload,
                )
            ]
        )
        active.commit()

    with uow as active:
        row = active.followups.get_by_uid_full(followup_uid)

    assert row is not None
    assert row.status == "failed"
    assert row.payload == failure_payload
