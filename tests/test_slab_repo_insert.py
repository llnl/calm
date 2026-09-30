import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("ase")
pytest.importorskip("sqlalchemy")

from ase import Atoms

from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from sqlalchemy import select
from calm.project.infrastructure.db.tables import slabs as slabs_t, bulks as bulks_t
from calm.structure.payloads import atoms_to_dict
from calm.project.domain.models import Slab as DomainSlab
from slab_record_fixtures import current_slab_payload, current_slab_uid


def _make_tilted_atoms():
    cell = np.array([[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.5, -0.3, 5.0]])
    return Atoms("Cu", positions=[[0, 0, 0]], cell=cell, pbc=True)


def test_repo_create_many_populates_tilt(tmp_path: Path, persisted_test_uid):
    db = tmp_path / "calm.sqlite"
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(str(db))

    atoms = _make_tilted_atoms()
    atoms_dict = atoms_to_dict(atoms)
    # compute tilt and stamp into atoms_dict
    from calm.slab.oriented.tilt import compute_slab_tilt_metadata

    tilt = compute_slab_tilt_metadata(atoms)
    atoms_dict.setdefault("info", {})["calm:tilt"] = tilt

    bulk_uid = persisted_test_uid("bulk", "bulk:1")
    miller = (0, 0, 1)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        atoms=atoms_dict,
    )
    slab_uid = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=miller,
        payload=payload,
    )

    # Ensure a bulk exists
    with uow as uw:
        uw.connection.execute(
            bulks_t.insert().values(
                uid_full=bulk_uid,
                id_short="b1",
                label="b1",
                payload_json=json.dumps({}),
            )
        )

    slab_domain = DomainSlab(
        uid_full=slab_uid,
        id_short="s_repo_1",
        bulk_uid_full=bulk_uid,
        bulk_id_short="b1",
        miller=miller,
        payload=payload,
    )

    with uow as uw:
        res = uw.slabs.create_many([slab_domain])
        assert len(res) == 1
        # Query raw row
        row = uw.connection.execute(
            select(slabs_t).where(slabs_t.c.uid_full == slab_uid)
        ).mappings().one()
        assert row["tilt_x"] is not None
        assert row["tilt_y"] is not None
        assert row["tilt_magnitude"] is not None
        # has_residual_tilt should be boolean or 0/1
        assert row["has_residual_tilt"] is not None


def test_repo_create_many_sets_orthogonalize_flag_from_payload(
    tmp_path: Path,
    persisted_test_uid,
):
    db = tmp_path / "calm.sqlite"
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(str(db))

    atoms = _make_tilted_atoms()
    atoms_dict = atoms_to_dict(atoms)

    # craft calm:tilt indicating orthogonalization applied and near-zero final tilt
    calm_tilt = {
        "cell_convention": "ase_row_major",
        "cell_generated_3x3": atoms.cell.array.tolist(),
        "tilt_xy": [0.0, 0.0],
        "tilt_magnitude": 0.0,
        "tilt_tolerance": 1e-6,
        "has_residual_tilt": False,
        "orthogonalize_c_applied": True,
        "integer_c_tilt_reduction_applied": False,
        "shear_info": {"F_shear_cart": [[1,0,0],[0,1,0],[0,0,1]], "c_xy_norm_before": 0.6, "c_xy_norm_after": 0.0},
    }
    atoms_dict.setdefault("info", {})["calm:tilt"] = calm_tilt

    bulk_uid = persisted_test_uid("bulk", "bulk:2")
    miller = (0, 0, 1)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        atoms=atoms_dict,
    )
    slab_uid = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=miller,
        payload=payload,
    )

    with uow as uw:
        uw.connection.execute(
            bulks_t.insert().values(
                uid_full=bulk_uid,
                id_short="b2",
                label="b2",
                payload_json=json.dumps({}),
            )
        )

    slab_domain = DomainSlab(
        uid_full=slab_uid,
        id_short="s_repo_2",
        bulk_uid_full=bulk_uid,
        bulk_id_short="b2",
        miller=miller,
        payload=payload,
    )

    with uow as uw:
        res = uw.slabs.create_many([slab_domain])
        row = uw.connection.execute(
            select(slabs_t).where(slabs_t.c.uid_full == slab_uid)
        ).mappings().one()
        assert bool(row["orthogonalize_c_applied"]) is True
        assert row["tilt_magnitude"] == pytest.approx(0.0)
