from pathlib import Path

import pytest

from calm.project.bootstrap import open_workspace
from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork


@pytest.mark.filterwarnings("error:Calculator resolution failed.*:UserWarning")
def test_campaign_resume_downstream_minimal(
    tmp_path: Path,
    prototype_graph_factory,
    stub_authoritative_registry_evaluator,
    persisted_test_uid,
):
    prototype_graph_factory(
        filename="calm.sqlite",
        bulk_uid_full="bulk:campaign-resume",
        bulk_id_short="b_campaign_resume",
        slab_a_uid_full="slab:campaign-a",
        slab_a_id_short="s_campaign_a",
        slab_b_uid_full="slab:campaign-b",
        slab_b_id_short="s_campaign_b",
        run_uid_full="run:campaign-seed",
        run_id_short="r_campaign_seed",
        prototype_uid_full="proto:campaign-resume",
        prototype_id_short="p_campaign_resume",
        prototype_payload={
            "miller_a": [0],
            "miller_b": [0],
            "match_score": 0.1,
            "n_atoms_interface": 1,
        },
    )

    # Open the workspace after the authoritative prototype graph exists.
    ws = open_workspace(root=tmp_path)

    # Create a campaign
    camp = ws.create_campaign(name="c_test", spec={})
    camp_uid = (
        camp.get("uid_full")
        if isinstance(camp, dict)
        else getattr(camp, "uid_full", None)
    )
    assert camp_uid

    # Create or get campaign run deterministically
    run_spec = {"a": 1}
    cr = ws.create_or_get_campaign_run(
        campaign_uid_full=camp_uid,
        run_spec=run_spec,
        backend_id="deterministic",
    )
    cr_uid = (
        cr.get("uid_full")
        if isinstance(cr, dict)
        else getattr(cr, "uid_full", None)
    )
    assert cr_uid

    # Deterministic reuse: the same declaration resolves to the same run.
    cr2 = ws.create_or_get_campaign_run(
        campaign_uid_full=camp_uid,
        run_spec=run_spec,
        backend_id="deterministic",
    )
    cr2_uid = (
        cr2.get("uid_full")
        if isinstance(cr2, dict)
        else getattr(cr2, "uid_full", None)
    )
    assert cr2_uid == cr_uid

    proto_uid_full = persisted_test_uid(
        "prototype",
        "proto:campaign-resume",
    )

    # Run a registry stage in campaign context
    res = ws.run_registry_stage(
        [proto_uid_full],
        n_steps=1,
        resume=False,
        campaign_uid_full=camp_uid,
        campaign_run_uid_full=cr_uid,
    )
    # results is a list; we don't depend on contents, only provenance
    assert isinstance(res, list) and len(res) >= 1
    registry_run_uid = res[0].get("run_uid")
    assert registry_run_uid is not None

    # Run relaxation and energy in campaign context
    rel = ws.run_relaxation_stage(
        [proto_uid_full],
        max_steps=1,
        backend="deterministic",
        resume=False,
        campaign_uid_full=camp_uid,
        campaign_run_uid_full=cr_uid,
    )
    assert isinstance(rel, list) and len(rel) >= 1
    relaxation_run_uid = rel[0].get("run_uid")
    assert relaxation_run_uid is not None
    ene = ws.run_energy_stage(
        [proto_uid_full],
        calculation={},
        backend="deterministic",
        resume=False,
        campaign_uid_full=camp_uid,
        campaign_run_uid_full=cr_uid,
    )
    assert isinstance(ene, list) and len(ene) >= 1
    energy_run_uid = ene[0].get("run_uid")
    assert energy_run_uid is not None

    # Verify stage-run campaign provenance via the authoritative edge store.
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(str(tmp_path / "calm.sqlite"))
    with uow as u:
        # Stage-run -> campaign provenance: registry, relaxation, energy
        reg_edges = u.edges.list(
            src_uid_full=registry_run_uid,
            kind="run_of_campaign",
        )
        assert any(
            e.dst_uid_full == camp_uid
            and e.payload.get("campaign_uid_full") == camp_uid
            and e.payload.get("campaign_run_uid_full") == cr_uid
            for e in reg_edges
        )

        rel_edges = u.edges.list(
            src_uid_full=relaxation_run_uid,
            kind="run_of_campaign",
        )
        assert any(
            e.dst_uid_full == camp_uid
            and e.payload.get("campaign_uid_full") == camp_uid
            and e.payload.get("campaign_run_uid_full") == cr_uid
            for e in rel_edges
        )

        ene_edges = u.edges.list(
            src_uid_full=energy_run_uid,
            kind="run_of_campaign",
        )
        assert any(
            e.dst_uid_full == camp_uid
            and e.payload.get("campaign_uid_full") == camp_uid
            and e.payload.get("campaign_run_uid_full") == cr_uid
            for e in ene_edges
        )

    camp_row = ws.get_campaign(camp_uid)
    assert camp_row is not None
    # Now re-run energy stage with resume=True and same campaign context
    ene2 = ws.run_energy_stage(
        [proto_uid_full],
        calculation={},
        backend="deterministic",
        resume=True,
        campaign_uid_full=camp_uid,
        campaign_run_uid_full=cr_uid,
    )
    # Ensure the resumed run remains linked to the campaign.
    assert isinstance(ene2, list) and len(ene2) >= 1
    resumed_energy_run_uid = ene2[0].get("run_uid")
    assert resumed_energy_run_uid is not None

    with uow as u:
        resumed_ene_edges = u.edges.list(
            src_uid_full=resumed_energy_run_uid,
            kind="run_of_campaign",
        )
        assert any(
            e.dst_uid_full == camp_uid
            and e.payload.get("campaign_uid_full") == camp_uid
            and e.payload.get("campaign_run_uid_full") == cr_uid
            for e in resumed_ene_edges
        )
