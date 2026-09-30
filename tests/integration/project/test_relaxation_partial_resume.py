from pathlib import Path

from test_helpers import make_test_interface_prototype
from calm.project.application.followups.relaxation import RelaxationOrchestrator
from calm.project.application.followups.relaxation_backends import (
    RelaxationComputeResult,
)
from calm.project.infrastructure.db.tables import followup_results
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.runtime.workspace import Workspace


class _CountingRelaxationBackend:
    name = "counting-relaxation"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def compute(self, *, run_uid, prototype_uid, target_uid, config, uow=None):
        self.calls.append(target_uid)
        return RelaxationComputeResult(
            final_energy=2.5,
            n_steps=1,
            relaxed_params={"relaxed_stub_energy": 2.5},
            summary={"energy": 2.5, "n_steps": 1},
            artifact_payloads=[],
        )


def test_partial_resume_recomputes_only_missing_relaxation_followup(
    tmp_path: Path,
    sqlite_uow_factory,
):
    uow = sqlite_uow_factory()
    ws = Workspace(
        out_dir=tmp_path / "out",
        artifact_store=FSArtifactStore(tmp_path / "out"),
        uow_factory=sqlite_uow_factory,
    )

    mapping = ws.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="resume_relaxation_a"),
            make_test_interface_prototype(
                prototype_uid="resume_relaxation_b",
                match_score=0.2,
                slab_b_uid="slab:test:b:distinct",
            ),
        ]
    )
    prototype_uids = [row["uid_full"] for row in mapping.values()]
    assert len(prototype_uids) == 2
    assert len(set(prototype_uids)) == 2

    initial_backend = _CountingRelaxationBackend()
    run1, initial_results = (
        RelaxationOrchestrator(uow)
        .with_backend(initial_backend)
        .run_stage(
            prototypes=prototype_uids,
            max_steps=1,
            resume=False,
        )
    )

    assert run1.status == "done"
    assert {result.status for result in initial_results} == {"completed"}
    assert initial_backend.calls == prototype_uids

    retained_target, missing_target = prototype_uids
    with uow as entered:
        initial_rows = entered.followups.list(
            run_uid_full=run1.uid_full,
            kind="relaxation_stage",
        )
        assert {row.target_uid_full for row in initial_rows} == set(prototype_uids)
        row_by_target = {row.target_uid_full: row for row in initial_rows}
        retained_followup_uid = row_by_target[retained_target].uid_full
        missing_followup_uid = row_by_target[missing_target].uid_full
        entered.connection.execute(
            followup_results.delete().where(
                followup_results.c.uid_full == missing_followup_uid
            )
        )
        entered.commit()

    resume_backend = _CountingRelaxationBackend()
    run2, resumed_results = (
        RelaxationOrchestrator(uow)
        .with_backend(resume_backend)
        .run_stage(
            prototypes=prototype_uids,
            max_steps=1,
            resume=False,
            partial_resume=True,
        )
    )

    assert run2.uid_full == run1.uid_full
    assert run2.status == "done"
    assert resume_backend.calls == [missing_target]

    result_by_target = {result.target_uid: result for result in resumed_results}
    assert set(result_by_target) == set(prototype_uids)
    assert result_by_target[retained_target].status == "skipped"
    assert result_by_target[retained_target].reason == "existing_followup"
    assert result_by_target[retained_target].followup_uid == retained_followup_uid
    assert result_by_target[missing_target].status == "completed"
    assert result_by_target[missing_target].followup_uid == missing_followup_uid

    with uow as entered:
        final_rows = entered.followups.list(
            run_uid_full=run2.uid_full,
            kind="relaxation_stage",
        )
        assert len(final_rows) == 2
        assert {row.target_uid_full for row in final_rows} == set(prototype_uids)
        assert len({row.uid_full for row in final_rows}) == 2
