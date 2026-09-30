import json
from pathlib import Path


from calm.project.infrastructure.db.tables import bulks as bulks_t

from calm.project.application.buildability import check_prototype_buildability


def test_buildability_ok(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    payload = hydrogen_atoms_payload_factory()
    uow = prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    with uow as uw:
        res = check_prototype_buildability(
            uw,
            persisted_test_uid("prototype", "proto:x"),
        )
        assert res.reconstructable is True
        assert res.buildable is True
        assert res.reasons == ["ok"]
        assert res.slab_a_id_short == "s_a"
        assert res.slab_b_id_short == "s_b"


def test_prototype_not_found(
    tmp_path: Path,
    sqlite_uow_factory,
    persisted_test_uid,
):
    uow = sqlite_uow_factory()
    with uow as uw:
        uw.connection.execute(
            bulks_t.insert().values(
                uid_full=persisted_test_uid("bulk", "bulk:1"),
                id_short="b1",
                payload_json=json.dumps({}),
            )
        )

    with uow as uw:
        res = check_prototype_buildability(uw, "proto:missing")
        assert res.reconstructable is False
        assert res.buildable is False
        assert "prototype_not_found" in res.reasons


def test_missing_slab_a(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    persisted_test_uid,
):
    payload = hydrogen_atoms_payload_factory()
    uow = prototype_graph_factory(
        slab_a_uid_full="slab:missing",
        create_slab_a=False,
        slab_b_payload=payload,
        prototype_uid_full="proto:y",
        prototype_id_short="p_y",
    )

    with uow as uw:
        res = check_prototype_buildability(
            uw,
            persisted_test_uid("prototype", "proto:y"),
        )
        assert res.reconstructable is False
        assert res.buildable is False
        assert "slab_a_not_found" in res.reasons


def test_slab_missing_atoms(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    persisted_test_uid,
):
    payload = hydrogen_atoms_payload_factory()
    uow = prototype_graph_factory(
        slab_a_payload={},
        slab_b_payload=payload,
        prototype_uid_full="proto:z",
        prototype_id_short="p_z",
        prototype_payload={
            "supercell_a": {"k": 1},
            "supercell_b": {"k": 1},
        },
    )

    with uow as uw:
        res = check_prototype_buildability(
            uw,
            persisted_test_uid("prototype", "proto:z"),
        )
        assert res.reconstructable is True
        assert res.buildable is False
        assert "slab_a_missing_atoms" in res.reasons
