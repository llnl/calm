"""Repository enforcement for exact-current energy result payloads."""

from __future__ import annotations

import json

import pytest

from calm.project.application.followups.common import persisted_followup_uid
from calm.project.domain.models import FollowupResult
from calm.project.infrastructure.db.tables import (
    followup_results as followups_t,
    prototypes as prototypes_t,
    runs as runs_t,
)
from energy_result_fixtures import (
    raw_energy_payload,
    reference_energy_payload,
    thermodynamic_payload,
)


def _insert_scaffold(uow) -> None:
    uow.connection.execute(
        runs_t.insert().values(
            uid_full="run:energy-contract",
            id_short="r_energy_contract",
            run_type="energy_stage",
            status="done",
            spec_json=json.dumps({"targets": []}),
        )
    )
    uow.connection.execute(
        runs_t.insert().values(
            uid_full="run:reference-contract",
            id_short="r_reference_contract",
            run_type="reference_energy",
            status="done",
            spec_json=json.dumps({"targets": []}),
        )
    )
    uow.connection.execute(
        runs_t.insert().values(
            uid_full="run:thermo-contract",
            id_short="r_thermo_contract",
            run_type="thermodynamic_derivation",
            status="done",
            spec_json=json.dumps({"targets": []}),
        )
    )
    uow.connection.execute(
        prototypes_t.insert().values(
            uid_full="proto:energy-contract",
            id_short="p_energy_contract",
            run_uid_full="run:energy-contract",
            slab_a_uid_full="slab:a",
            slab_b_uid_full="slab:b",
            payload_json=json.dumps({}),
        )
    )


def _raw_result(*, energy: float = -2.0) -> FollowupResult:
    uid = persisted_followup_uid(
        run_uid_full="run:energy-contract",
        prototype_uid_full="proto:energy-contract",
        target_uid_full="proto:energy-contract",
        target_kind="prototype",
        kind="energy_stage",
    )
    return FollowupResult(
        uid_full=uid,
        id_short="f_energy_contract",
        run_uid_full="run:energy-contract",
        prototype_uid_full="proto:energy-contract",
        target_uid_full="proto:energy-contract",
        target_kind="prototype",
        kind="energy_stage",
        status="done",
        best_energy=energy,
        param1=None,
        param2=None,
        n_points=1,
        payload=raw_energy_payload(energy, interface_area_A2=None),
    )


def _reference_result() -> FollowupResult:
    uid = persisted_followup_uid(
        run_uid_full="run:reference-contract",
        prototype_uid_full="proto:energy-contract",
        target_uid_full="iface:energy-contract",
        target_kind="interface",
        kind="reference_energy",
        qualifiers={"reference_kind": "strained_bulk_a"},
    )
    return FollowupResult(
        uid_full=uid,
        id_short="f_reference_contract",
        run_uid_full="run:reference-contract",
        prototype_uid_full="proto:energy-contract",
        target_uid_full="iface:energy-contract",
        target_kind="interface",
        kind="reference_energy",
        status="done",
        best_energy=-4.0,
        param1=-2.0,
        param2=2.0,
        n_points=0,
        payload=reference_energy_payload(
            reference_uid_full="reference:contract:a",
            reference_kind="strained_bulk_a",
            formula_id="interface_excess_strained_bulk",
            energy_eV=-4.0,
            energy_eV_per_formula_unit=-2.0,
            reference_formula_units=2,
            interface_formula_units=2,
        ),
    )


def _thermodynamic_result() -> FollowupResult:
    raw_uid = "followup:raw-contract"
    uid = persisted_followup_uid(
        run_uid_full="run:thermo-contract",
        prototype_uid_full="proto:energy-contract",
        target_uid_full="iface:energy-contract",
        target_kind="interface",
        kind="thermodynamic_quantity",
        qualifiers={"raw_energy_followup_uid": raw_uid},
    )
    payload = thermodynamic_payload(
        raw_energy_followup_uid=raw_uid,
        value_eV_per_A2=0.125,
        area_A2=8.0,
        n_interfaces=2,
    )
    return FollowupResult(
        uid_full=uid,
        id_short="f_thermo_contract",
        run_uid_full="run:thermo-contract",
        prototype_uid_full="proto:energy-contract",
        target_uid_full="iface:energy-contract",
        target_kind="interface",
        kind="thermodynamic_quantity",
        status="done",
        best_energy=0.125,
        param1=8.0,
        param2=2.0,
        n_points=1,
        payload=payload,
    )


def test_energy_result_roundtrips_with_verified_payload_and_identity(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _raw_result()
        assert uow.followups.upsert_many([requested]) == [requested]

    with schema_uow_factory() as uow:
        reopened = uow.followups.get_by_uid_full(requested.uid_full)

    assert reopened is not None
    assert reopened.payload == requested.payload
    assert reopened.best_energy == requested.best_energy
    assert reopened.n_points == requested.n_points


def test_energy_result_writer_rejects_wrong_identity_and_historical_payload(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _raw_result()
        wrong = requested.__class__(
            **{**requested.__dict__, "uid_full": "followup:wrong"}
        )
        with pytest.raises(ValueError, match="identity does not match"):
            uow.followups.upsert_many([wrong])

        historical_payload = dict(requested.payload)
        historical_payload["energy_backend"] = "deterministic"
        historical = requested.__class__(
            **{**requested.__dict__, "payload": historical_payload}
        )
        with pytest.raises(ValueError, match="unsupported or historical"):
            uow.followups.upsert_many([historical])


def test_energy_result_reopen_fails_closed_on_tampered_payload(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _raw_result()
        uow.followups.upsert_many([requested])
        raw = uow.connection.execute(
            followups_t.select().where(followups_t.c.uid_full == requested.uid_full)
        ).mappings().one()
        payload = json.loads(raw["payload_json"])
        payload["energy_eV"] = -3.0
        uow.connection.execute(
            followups_t.update()
            .where(followups_t.c.uid_full == requested.uid_full)
            .values(payload_json=json.dumps(payload))
        )

    with schema_uow_factory() as uow:
        with pytest.raises(ValueError, match="best_energy"):
            uow.followups.get_by_uid_full(requested.uid_full)


def test_energy_upsert_rejects_conflicting_result_for_same_identity(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        first = _raw_result()
        uow.followups.upsert_many([first])

        with pytest.raises(ValueError, match="different scientific results"):
            uow.followups.upsert_many([_raw_result(energy=-3.0)])


def test_reference_result_identity_includes_reference_kind(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _reference_result()
        stored = uow.followups.upsert_many([requested])
        assert stored == [requested]

        wrong_uid = persisted_followup_uid(
            run_uid_full=requested.run_uid_full,
            prototype_uid_full=requested.prototype_uid_full,
            target_uid_full=requested.target_uid_full,
            target_kind=requested.target_kind,
            kind=requested.kind,
            qualifiers={"reference_kind": "strained_bulk_b"},
        )
        wrong = requested.__class__(
            **{**requested.__dict__, "uid_full": wrong_uid}
        )
        with pytest.raises(ValueError, match="identity does not match"):
            uow.followups.upsert_many([wrong])


def test_thermodynamic_reopen_rejects_tampered_reference_values(
    schema_uow_factory,
) -> None:
    with schema_uow_factory() as uow:
        _insert_scaffold(uow)
        requested = _thermodynamic_result()
        uow.followups.upsert_many([requested])
        raw = uow.connection.execute(
            followups_t.select().where(
                followups_t.c.uid_full == requested.uid_full
            )
        ).mappings().one()
        payload = json.loads(raw["payload_json"])
        payload["references"]["values"][
            "bulk_a_eV_per_formula_unit"
        ] = -3.0
        uow.connection.execute(
            followups_t.update()
            .where(followups_t.c.uid_full == requested.uid_full)
            .values(payload_json=json.dumps(payload))
        )

    with schema_uow_factory() as uow:
        with pytest.raises(ValueError, match="authoritative calculation|does not match"):
            uow.followups.get_by_uid_full(requested.uid_full)
