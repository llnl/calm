import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("sqlalchemy")

from ase import Atoms
from calm.structure.payloads import atoms_to_dict
from calm.slab.oriented.tilt import compute_slab_tilt_metadata
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from calm.project.infrastructure.db.tables import slabs as slabs_t, bulks as bulks_t
from sqlalchemy import select
from slab_record_fixtures import current_slab_payload, current_slab_uid


def _make_atoms_with_tilt(tx, ty):
    cell = np.array([[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [tx, ty, 5.0]])
    return Atoms("Cu", positions=[[0.0, 0.0, 0.0]], cell=cell, pbc=True)


def test_slab_tilt_magnitude_filter_and_ordering(
    tmp_path: Path,
    persisted_test_uid,
):
    db = tmp_path / "order.sqlite"
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(str(db))

    # Create two slabs with different tilt magnitudes
    a_low = _make_atoms_with_tilt(0.05, 0.02)
    a_high = _make_atoms_with_tilt(0.5, -0.3)

    ad_low = atoms_to_dict(a_low)
    ad_low.setdefault("info", {})["calm:tilt"] = compute_slab_tilt_metadata(a_low)
    bulk_uid = persisted_test_uid("bulk", "bulk:o")
    miller = (0, 0, 1)
    payload_low = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        atoms=ad_low,
        user_payload={"fixture": "low"},
    )

    ad_high = atoms_to_dict(a_high)
    ad_high.setdefault("info", {})["calm:tilt"] = compute_slab_tilt_metadata(a_high)
    payload_high = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        atoms=ad_high,
        user_payload={"fixture": "high"},
    )
    low_uid = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=miller,
        payload=payload_low,
    )
    high_uid = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=miller,
        payload=payload_high,
    )

    with uow as uw:
        uw.connection.execute(
            bulks_t.insert().values(
                uid_full=bulk_uid,
                id_short="bo",
                payload_json=json.dumps({}),
            )
        )

    slab_low = {
        "uid_full": low_uid,
        "id_short": "s_low",
        "bulk_uid_full": bulk_uid,
        "bulk_id_short": "bo",
        "miller": miller,
        "payload": payload_low,
    }
    slab_high = {
        "uid_full": high_uid,
        "id_short": "s_high",
        "bulk_uid_full": bulk_uid,
        "bulk_id_short": "bo",
        "miller": miller,
        "payload": payload_high,
    }

    # Insert via repository so normalized columns are created
    from calm.project.domain.models import Slab as DomainSlab

    s_low = DomainSlab(uid_full=slab_low["uid_full"], id_short=slab_low["id_short"], bulk_uid_full=slab_low["bulk_uid_full"], bulk_id_short=slab_low["bulk_id_short"], miller=slab_low["miller"], payload=slab_low["payload"])
    s_high = DomainSlab(uid_full=slab_high["uid_full"], id_short=slab_high["id_short"], bulk_uid_full=slab_high["bulk_uid_full"], bulk_id_short=slab_high["bulk_id_short"], miller=slab_high["miller"], payload=slab_high["payload"])

    with uow as uw:
        uw.slabs.create_many([s_high, s_low])
        # Order by tilt_magnitude ascending should return low first
        rows = uw.connection.execute(select(slabs_t.c.uid_full, slabs_t.c.tilt_magnitude).order_by(slabs_t.c.tilt_magnitude.asc())).mappings().all()
        assert rows[0]["uid_full"] == low_uid
        # Threshold filter
        threshold = 0.1
        filtered = uw.connection.execute(select(slabs_t.c.uid_full).where(slabs_t.c.tilt_magnitude <= threshold)).mappings().all()
        uids = {r["uid_full"] for r in filtered}
        assert low_uid in uids
        assert high_uid not in uids
