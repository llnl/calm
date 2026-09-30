from pathlib import Path

import pytest
from sqlalchemy import text

from calm.project.application.build_stage import BuildStageOrchestrator
from calm.project.domain.identity_v2 import persisted_entity_uid_v2


def test_build_stage_skips_unbuildable(tmp_path: Path, sqlite_uow_factory):
    uow = sqlite_uow_factory()
    run_uid = persisted_entity_uid_v2("run", {"fixture": "unbuildable"})
    prototype_uid = persisted_entity_uid_v2(
        "prototype", {"fixture": "unbuildable"}
    )
    missing_slab_a_uid = persisted_entity_uid_v2(
        "slab", {"fixture": "missing_a"}
    )
    missing_slab_b_uid = persisted_entity_uid_v2(
        "slab", {"fixture": "missing_b"}
    )

    # Create a prototype whose canonical slab references do not exist so the
    # build stage exercises its current unbuildable-graph behavior.
    with uow as uw:
        uw.connection.execute(
            text(
                "INSERT INTO runs "
                "(uid_full, id_short, run_type, status, spec_json) "
                "VALUES (:uid_full, 'r1', 'prototype', 'done', '{}')"
            ),
            {"uid_full": run_uid},
        )
        uw.connection.execute(
            text(
                "INSERT INTO prototypes "
                "(uid_full, id_short, run_uid_full, slab_a_uid_full, "
                "slab_b_uid_full, payload_json) "
                "VALUES (:uid_full, 'p_skip', :run_uid_full, "
                ":slab_a_uid_full, :slab_b_uid_full, '{}')"
            ),
            {
                "uid_full": prototype_uid,
                "run_uid_full": run_uid,
                "slab_a_uid_full": missing_slab_a_uid,
                "slab_b_uid_full": missing_slab_b_uid,
            },
        )
        uw.commit()

    orchestrator = BuildStageOrchestrator(lambda: sqlite_uow_factory())
    res = orchestrator.build_from_prototypes([prototype_uid])
    assert res and res[0].status == "skipped"


def test_build_stage_persists_terminal_state_and_resumes(
    tmp_path: Path,
    sqlite_uow_factory,
):
    missing = persisted_entity_uid_v2("prototype", {"fixture": "missing"})
    orchestrator = BuildStageOrchestrator(sqlite_uow_factory)

    first = orchestrator.build_from_prototypes([missing], run_name="resume")
    assert len(first) == 1
    assert first[0].status == "skipped"
    assert first[0].reason == "prototype_not_found"
    assert first[0].run_uid is not None

    with sqlite_uow_factory() as uow:
        run = uow.runs.get_by_uid_full(first[0].run_uid)
        assert run is not None
        assert run.status == "done"
        assert run.progress == {
            "n_requested": 1,
            "n_built": 0,
            "n_skipped": 1,
        }

    resumed = orchestrator.build_from_prototypes([missing], run_name="resume")
    assert resumed == [
        type(first[0])(
            prototype_uid=missing,
            status="skipped",
            reason="run_already_done",
            run_uid=first[0].run_uid,
        )
    ]


def test_build_stage_rejects_entered_uow(tmp_path: Path, sqlite_uow_factory):
    uow = sqlite_uow_factory()
    with uow as entered:
        orchestrator = BuildStageOrchestrator(lambda: entered)
        with pytest.raises(ValueError, match="fresh non-entered UnitOfWork"):
            orchestrator.build_from_prototypes(["proto:missing"])
