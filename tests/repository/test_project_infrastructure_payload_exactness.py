from __future__ import annotations

import json

import pytest
from sqlalchemy import func, select

from calm.project.domain.models import Slab
from calm.project.infrastructure.db.tables import bulks as bulks_t
from calm.project.infrastructure.db.tables import edges as edges_t
from calm.project.infrastructure.db.tables import slabs as slabs_t
from slab_record_fixtures import (
    current_atoms,
    current_slab_payload,
    current_slab_uid,
)


def _insert_bulk(uow, *, uid_full: str, id_short: str) -> None:
    with uow as entered:
        entered.connection.execute(
            bulks_t.insert().values(
                uid_full=uid_full,
                id_short=id_short,
                label=id_short,
                payload_json=json.dumps({}),
            )
        )


def _slab(
    *,
    uid_full: str,
    bulk_uid_full: str,
    payload: dict,
    id_short: str = "s_exact",
) -> Slab:
    return Slab(
        uid_full=uid_full,
        id_short=id_short,
        bulk_uid_full=bulk_uid_full,
        bulk_id_short="b_exact",
        miller=(1, 0, 0),
        payload=payload,
    )



def test_edge_repository_rejects_invalid_payload_without_writing(
    schema_uow_factory,
) -> None:
    uow = schema_uow_factory()

    with pytest.raises(TypeError, match="JSON-native"):
        with uow as entered:
            entered.edges.add(
                src_uid_full="source:one",
                dst_uid_full="target:one",
                kind="exact_payload",
                payload={"invalid": {1, 2}},
            )

    with uow as entered:
        count = entered.connection.execute(
            select(func.count()).select_from(edges_t)
        ).scalar_one()
    assert count == 0


def test_edge_identity_distinguishes_payload_variants(
    schema_uow_factory,
) -> None:
    uow = schema_uow_factory()

    with uow as entered:
        entered.edges.add(
            src_uid_full="source:one",
            dst_uid_full="target:one",
            kind="included_in_dataset",
            payload={"dataset_index": 0},
        )
        entered.edges.add(
            src_uid_full="source:one",
            dst_uid_full="target:one",
            kind="included_in_dataset",
            payload={"dataset_index": 1},
        )
        entered.edges.add(
            src_uid_full="source:one",
            dst_uid_full="target:one",
            kind="included_in_dataset",
            payload={"dataset_index": 1},
        )

    with uow as entered:
        edges = entered.edges.list(
            src_uid_full="source:one",
            kind="included_in_dataset",
        )

    assert {edge.payload["dataset_index"] for edge in edges} == {0, 1}
    assert len({edge.uid_full for edge in edges}) == 2


def test_edge_repository_rejects_payload_hash_mismatch(
    schema_uow_factory,
) -> None:
    uow = schema_uow_factory()

    with uow as entered:
        entered.connection.execute(
            edges_t.insert().values(
                src_uid_full="source:corrupt",
                dst_uid_full="target:corrupt",
                kind="corrupt_payload",
                payload_json='{"value":1}',
                payload_hash="not-the-payload-hash",
            )
        )

    with pytest.raises(ValueError, match="payload_hash does not match"):
        with uow as entered:
            entered.edges.list(kind="corrupt_payload")


def test_atomistic_slab_requires_writer_owned_canonical_tilt_metadata(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "payload-exactness-bulk")
    _insert_bulk(uow, uid_full=bulk_uid, id_short="b_exact")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        atoms=current_atoms(with_tilt=False),
    )
    slab_uid = current_slab_uid(
        bulk_uid_full=bulk_uid, miller=(1, 0, 0), payload=payload
    )
    slab = _slab(uid_full=slab_uid, bulk_uid_full=bulk_uid, payload=payload)

    with pytest.raises(ValueError, match="missing canonical"):
        with uow as entered:
            entered.slabs.create_many([slab])

    with uow as entered:
        count = entered.connection.execute(
            select(func.count()).select_from(slabs_t)
        ).scalar_one()
    assert count == 0


def test_atomistic_slab_projects_only_canonical_tilt_metadata(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "payload-exactness-bulk")
    _insert_bulk(uow, uid_full=bulk_uid, id_short="b_exact")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        atoms=current_atoms(),
    )
    slab_uid = current_slab_uid(
        bulk_uid_full=bulk_uid, miller=(1, 0, 0), payload=payload
    )
    slab = _slab(uid_full=slab_uid, bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        stored = entered.slabs.create_many([slab])
        row = entered.connection.execute(
            select(slabs_t).where(slabs_t.c.uid_full == slab_uid)
        ).mappings().one()

    assert stored[0].uid_full == slab_uid
    assert row["tilt_x"] == pytest.approx(0.25)
    assert row["tilt_y"] == pytest.approx(-0.5)
    assert row["tilt_magnitude"] == pytest.approx(0.5590169943749475)
    assert bool(row["has_residual_tilt"]) is True
    assert bool(row["orthogonalize_c_applied"]) is False
    assert bool(row["integer_c_tilt_reduction_applied"]) is True
    assert row["c_tilt_m"] == 1
    assert row["c_tilt_n"] == -2


def test_spec_only_slab_does_not_invent_tilt_metadata(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "payload-exactness-bulk")
    _insert_bulk(uow, uid_full=bulk_uid, id_short="b_exact")
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        params={"layers": 4},
    )
    slab_uid = current_slab_uid(
        bulk_uid_full=bulk_uid, miller=(1, 0, 0), payload=payload
    )
    slab = _slab(uid_full=slab_uid, bulk_uid_full=bulk_uid, payload=payload)

    with uow as entered:
        entered.slabs.create_many([slab])
        row = entered.connection.execute(
            select(slabs_t).where(slabs_t.c.uid_full == slab_uid)
        ).mappings().one()

    assert row["tilt_x"] is None
    assert row["tilt_y"] is None
    assert row["tilt_magnitude"] is None
    assert row["has_residual_tilt"] is None


def test_slab_reader_rejects_missing_parent_bulk(
    schema_uow_factory,
    persisted_test_uid,
) -> None:
    uow = schema_uow_factory()
    bulk_uid = persisted_test_uid("bulk", "deleted-parent")
    _insert_bulk(uow, uid_full=bulk_uid, id_short="b_deleted")
    payload = current_slab_payload(bulk_uid_full=bulk_uid)
    slab_uid = current_slab_uid(
        bulk_uid_full=bulk_uid, miller=(1, 0, 0), payload=payload
    )
    slab = _slab(
        uid_full=slab_uid,
        bulk_uid_full=bulk_uid,
        id_short="s_deleted",
        payload=payload,
    )
    with uow as entered:
        entered.slabs.create_many([slab])
        entered.connection.execute(
            bulks_t.delete().where(bulks_t.c.uid_full == bulk_uid)
        )

    with pytest.raises(ValueError, match="live authoritative parent bulk"):
        with uow as entered:
            entered.slabs.get_by_uid_full(slab_uid)
