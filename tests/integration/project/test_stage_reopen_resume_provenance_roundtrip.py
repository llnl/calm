from pathlib import Path

import pytest

from calm.project.infrastructure.db.uow import SqlAlchemyUnitOfWork
from calm.project.bootstrap import open_workspace
from calm.public.project import open_project


_STAGE_RUN_TYPES = ("registry_search", "relaxation_stage", "energy_stage")
_STAGE_KINDS = ("registry_search", "relaxation_stage", "energy_stage")


def _uid(record):
    if isinstance(record, dict):
        return record.get("uid_full")
    return getattr(record, "uid_full", None)


def _persistence_snapshot(db_path: Path) -> dict[str, object]:
    uow = SqlAlchemyUnitOfWork.from_sqlite_path(str(db_path))
    with uow as entered:
        runs = [
            run
            for run_type in _STAGE_RUN_TYPES
            for run in entered.runs.list(run_type=run_type)
        ]
        followups = [
            row
            for kind in _STAGE_KINDS
            for row in entered.followups.list(kind=kind)
        ]
        return {
            "run_uids": {run.uid_full for run in runs},
            "run_status": {run.uid_full: run.status for run in runs},
            "followup_uids": {row.uid_full for row in followups},
            "followup_runs": {
                row.uid_full: row.run_uid_full for row in followups
            },
            "artifact_uids": {
                artifact.uid_full
                for run in runs
                for artifact in entered.artifacts.list_for_run(run.uid_full)
            },
            "interface_uids": {
                interface.uid_full
                for interface in entered.derived_interfaces.list()
            },
        }


def _assert_completed(result: list[dict], prototype_uid: str) -> dict:
    assert len(result) == 1
    row = result[0]
    assert row["status"] == "completed"
    assert row["prototype_uid"] == prototype_uid
    assert row["run_uid"]
    assert row["followup_uid"]
    return row


def _assert_resumed(result: list[dict], prototype_uid: str, run_uid: str) -> None:
    assert len(result) == 1
    row = result[0]
    expected = {
        "target_uid": None,
        "target_kind": None,
        "prototype_uid": prototype_uid,
        "status": "skipped",
        "run_uid": run_uid,
        "followup_uid": None,
        "reason": "run_already_done",
        "derived_interface_uid": None,
        "relaxed_interface_uid": None,
        "artifact_refs": None,
    }
    assert {key: row.get(key) for key in expected} == expected


@pytest.mark.filterwarnings("error:Calculator resolution failed.*:UserWarning")
def test_stage_reopen_resume_provenance_roundtrip(
    tmp_path: Path,
    prototype_graph_factory,
    stub_authoritative_registry_evaluator,
    persisted_test_uid,
):
    prototype_graph_factory(
        filename="calm.sqlite",
        bulk_uid_full="bulk:public-roundtrip",
        bulk_id_short="b_public_roundtrip",
        slab_a_uid_full="slab:public-a",
        slab_a_id_short="s_public_a",
        slab_b_uid_full="slab:public-b",
        slab_b_id_short="s_public_b",
        run_uid_full="run:public-seed",
        run_id_short="r_public_seed",
        prototype_uid_full="proto:public-roundtrip",
        prototype_id_short="p_public_roundtrip",
        prototype_payload={
            "miller_a": [0],
            "miller_b": [0],
            "match_score": 0.1,
            "n_atoms_interface": 1,
        },
    )

    project = open_project(str(tmp_path))
    campaign = project.create_campaign(name="public_roundtrip", spec={})
    campaign_uid = _uid(campaign)
    assert campaign_uid

    campaign_run = project._adapter.create_or_get_campaign_run(
        campaign_uid,
        run_spec={"a": 1},
        backend_id="deterministic",
    )
    campaign_run_uid = _uid(campaign_run)
    assert campaign_run_uid

    prototype_uid = persisted_test_uid(
        "prototype",
        "proto:public-roundtrip",
    )
    workspace = open_workspace(root=tmp_path)
    registry = _assert_completed(
        workspace.run_registry_stage(
            [prototype_uid],
            n_steps=1,
            resume=False,
            campaign_uid_full=campaign_uid,
            campaign_run_uid_full=campaign_run_uid,
        ),
        prototype_uid,
    )
    relaxation = _assert_completed(
        workspace.run_relaxation_stage(
            [prototype_uid],
            max_steps=1,
            backend="deterministic",
            resume=False,
            campaign_uid_full=campaign_uid,
            campaign_run_uid_full=campaign_run_uid,
        ),
        prototype_uid,
    )
    energy = _assert_completed(
        workspace.run_energy_stage(
            [prototype_uid],
            calculation={},
            backend="deterministic",
            resume=False,
            campaign_uid_full=campaign_uid,
            campaign_run_uid_full=campaign_run_uid,
        ),
        prototype_uid,
    )

    stage_run_uids = {
        registry["run_uid"],
        relaxation["run_uid"],
        energy["run_uid"],
    }
    stage_followup_uids = {
        registry["followup_uid"],
        relaxation["followup_uid"],
        energy["followup_uid"],
    }
    assert len(stage_run_uids) == 3
    assert len(stage_followup_uids) == 3

    before_reopen = _persistence_snapshot(tmp_path / "calm.sqlite")
    assert before_reopen["run_uids"] == stage_run_uids
    assert before_reopen["run_status"] == {
        run_uid: "done" for run_uid in stage_run_uids
    }
    assert before_reopen["followup_uids"] == stage_followup_uids
    assert set(before_reopen["followup_runs"].values()) == stage_run_uids
    assert len(before_reopen["artifact_uids"]) == 2
    # These low-level deterministic stages target a prototype without persisted
    # atoms. They record run, followup, and artifact provenance but must not
    # fabricate an authoritative derived-interface structure.
    assert before_reopen["interface_uids"] == set()

    reopened_workspace = open_workspace(root=tmp_path)
    resumed_registry = reopened_workspace.run_registry_stage(
        [prototype_uid],
        n_steps=1,
        resume=True,
        campaign_uid_full=campaign_uid,
        campaign_run_uid_full=campaign_run_uid,
    )
    resumed_relaxation = reopened_workspace.run_relaxation_stage(
        [prototype_uid],
        max_steps=1,
        backend="deterministic",
        resume=True,
        campaign_uid_full=campaign_uid,
        campaign_run_uid_full=campaign_run_uid,
    )
    resumed_energy = reopened_workspace.run_energy_stage(
        [prototype_uid],
        calculation={},
        backend="deterministic",
        resume=True,
        campaign_uid_full=campaign_uid,
        campaign_run_uid_full=campaign_run_uid,
    )

    _assert_resumed(resumed_registry, prototype_uid, registry["run_uid"])
    _assert_resumed(resumed_relaxation, prototype_uid, relaxation["run_uid"])
    _assert_resumed(resumed_energy, prototype_uid, energy["run_uid"])
    assert _persistence_snapshot(tmp_path / "calm.sqlite") == before_reopen
