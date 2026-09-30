from __future__ import annotations

from copy import deepcopy
import json

import pytest
from sqlalchemy import select, update

from calm.project.domain.models import Slab
from calm.project.infrastructure.db.tables import bulks as bulks_t
from calm.project.infrastructure.db.tables import slabs as slabs_t
from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from slab_record_fixtures import current_atoms, current_slab_payload, current_slab_uid


def _insert_bulk(uow, *, uid_full: str, id_short: str) -> int:
    result = uow.connection.execute(
        bulks_t.insert().values(
            uid_full=uid_full,
            id_short=id_short,
            label=id_short,
            payload_json="{}",
        )
    )
    return int(result.inserted_primary_key[0])


def _slab(*, bulk_uid_full: str, payload: dict, uid_full: str | None = None) -> Slab:
    miller = (1, 0, 0)
    return Slab(
        uid_full=(
            uid_full
            or current_slab_uid(
                bulk_uid_full=bulk_uid_full,
                miller=miller,
                payload=payload,
            )
        ),
        id_short="s_contract",
        bulk_uid_full=bulk_uid_full,
        bulk_id_short="b_contract",
        miller=miller,
        payload=payload,
    )


def test_slab_repository_roundtrips_one_exact_current_record(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        atoms=current_atoms(),
        params={"layers": 4, "vacuum": 12.0},
        user_payload={"campaign": "roundtrip"},
        layers=4,
        vacuum_A=12.0,
    )
    slab = _slab(bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
        created = entered.slabs.create_many([slab])[0]

    with uow as entered:
        reopened = entered.slabs.get_by_uid_full(slab.uid_full)
        row = entered.connection.execute(
            select(slabs_t).where(slabs_t.c.uid_full == slab.uid_full)
        ).mappings().one()

    assert created.payload == payload
    assert reopened is not None
    assert reopened.payload == payload
    assert reopened.bulk_uid_full == bulk_uid
    assert reopened.miller == (1, 0, 0)
    assert row["payload_json"] == json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def test_slab_repository_rejects_incomplete_current_transform_provenance_on_write(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        atoms=current_atoms(),
    )
    payload["structure"]["atoms"]["info"][
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY
    ].pop("construction_controls")
    slab = _slab(
        bulk_uid_full=bulk_uid,
        payload=payload,
        uid_full=persisted_test_uid("slab", "incomplete-provenance"),
    )

    with pytest.raises(ValueError, match="construction_controls provenance"):
        with uow as entered:
            _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
            entered.slabs.create_many([slab])


def test_slab_repository_rejects_incomplete_current_transform_provenance_on_read(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        atoms=current_atoms(),
    )
    slab = _slab(bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
        entered.slabs.create_many([slab])
        incomplete = deepcopy(payload)
        incomplete["structure"]["atoms"]["info"][
            ORIENTED_SLAB_TRANSFORMS_INFO_KEY
        ].pop("construction_controls")
        entered.connection.execute(
            update(slabs_t)
            .where(slabs_t.c.uid_full == slab.uid_full)
            .values(
                payload_json=json.dumps(
                    incomplete,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
            )
        )

    with pytest.raises(ValueError, match="construction_controls provenance"):
        with uow as entered:
            entered.slabs.get_by_uid_full(slab.uid_full)


def test_slab_repository_rejects_uid_tampering(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    payload = current_slab_payload(bulk_uid_full=bulk_uid)
    slab = _slab(bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
        entered.slabs.create_many([slab])
        entered.connection.execute(
            update(slabs_t)
            .where(slabs_t.c.uid_full == slab.uid_full)
            .values(uid_full=persisted_test_uid("slab", "tampered"))
        )

    with pytest.raises(ValueError, match="identity does not match"):
        with uow as entered:
            entered.slabs.get_by_uid_full(
                persisted_test_uid("slab", "tampered")
            )


def test_slab_repository_rejects_parent_or_miller_tampering(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    other_uid = persisted_test_uid("bulk", "slab-contract-other-parent")
    payload = current_slab_payload(bulk_uid_full=bulk_uid)
    slab = _slab(bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
        other_pk = _insert_bulk(entered, uid_full=other_uid, id_short="b_other")
        entered.slabs.create_many([slab])
        entered.connection.execute(
            update(slabs_t)
            .where(slabs_t.c.uid_full == slab.uid_full)
            .values(bulk_pk=other_pk)
        )

    with pytest.raises(ValueError, match="identity does not match"):
        with uow as entered:
            entered.slabs.get_by_uid_full(slab.uid_full)

    with uow as entered:
        entered.connection.execute(
            update(slabs_t)
            .where(slabs_t.c.uid_full == slab.uid_full)
            .values(bulk_pk=select(bulks_t.c.bulk_pk).where(bulks_t.c.uid_full == bulk_uid).scalar_subquery(), miller_h=2)
        )

    with pytest.raises(ValueError, match="identity does not match"):
        with uow as entered:
            entered.slabs.get_by_uid_full(slab.uid_full)


def test_slab_repository_rejects_noncanonical_json_and_tilt_projection_tampering(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        atoms=current_atoms(),
    )
    slab = _slab(bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
        entered.slabs.create_many([slab])
        entered.connection.execute(
            update(slabs_t)
            .where(slabs_t.c.uid_full == slab.uid_full)
            .values(payload_json=json.dumps(payload, indent=2))
        )

    with pytest.raises(ValueError, match="must be canonical"):
        with uow as entered:
            entered.slabs.get_by_uid_full(slab.uid_full)

    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    with uow as entered:
        entered.connection.execute(
            update(slabs_t)
            .where(slabs_t.c.uid_full == slab.uid_full)
            .values(payload_json=canonical_json, tilt_x=9.0)
        )

    with pytest.raises(ValueError, match="tilt_x projection does not match"):
        with uow as entered:
            entered.slabs.get_by_uid_full(slab.uid_full)


def test_slab_repository_rejects_conflicting_idempotent_reuse(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "slab-contract-parent")
    payload = current_slab_payload(bulk_uid_full=bulk_uid)
    slab = _slab(bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        _insert_bulk(entered, uid_full=bulk_uid, id_short="b_contract")
        entered.slabs.create_many([slab])
        reused = entered.slabs.create_many([slab])[0]

    assert reused.uid_full == slab.uid_full
    assert reused.payload == payload

    conflicting_payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        params={"layers": 8},
    )
    conflicting = _slab(
        bulk_uid_full=bulk_uid,
        payload=conflicting_payload,
        uid_full=slab.uid_full,
    )
    with pytest.raises(ValueError, match="does not match"):
        with uow as entered:
            entered.slabs.create_many([conflicting])
