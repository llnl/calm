from pathlib import Path

import pytest

from test_helpers import make_test_interface_prototype
from calm.project.application.followups.relaxation import RelaxationOrchestrator
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.runtime.workspace import Workspace


class _FailingRelaxationBackend:
    name = "failing-relaxation"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def compute(self, *, run_uid, prototype_uid, target_uid, config, uow=None):
        self.calls.append(target_uid)
        raise RuntimeError("failing backend")


def _relaxation_state(sqlite_uow_factory) -> dict[str, object]:
    with sqlite_uow_factory() as entered:
        runs = entered.runs.list(run_type="relaxation_stage")
        followups = entered.followups.list(kind="relaxation_stage")
        artifact_uids = {
            artifact.uid_full
            for run in runs
            for artifact in entered.artifacts.list_for_run(run.uid_full)
        }
        interfaces = entered.derived_interfaces.list()
        return {
            "run_uids": {run.uid_full for run in runs},
            "run_status": {run.uid_full: run.status for run in runs},
            "run_errors": {run.uid_full: run.error for run in runs},
            "followup_uids": {row.uid_full for row in followups},
            "followups_by_run": {
                run.uid_full: {
                    row.uid_full
                    for row in followups
                    if row.run_uid_full == run.uid_full
                }
                for run in runs
            },
            "artifact_uids": artifact_uids,
            "interface_uids": {interface.uid_full for interface in interfaces},
        }


def test_relaxation_run_identity_resume_reopen_and_failure_retry(
    tmp_path: Path,
    sqlite_uow_factory,
):
    ws = Workspace(
        out_dir=tmp_path / "out",
        artifact_store=FSArtifactStore(tmp_path / "out"),
        uow_factory=sqlite_uow_factory,
    )
    mapping = ws.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="relaxation_identity", match_score=0.2)
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]

    first = ws.run_relaxation_stage(
        [prototype_uid],
        max_steps=1,
        backend="deterministic",
        resume=False,
    )
    assert len(first) == 1
    assert first[0]["status"] == "completed"
    assert first[0]["prototype_uid"] == prototype_uid
    first_run_uid = first[0]["run_uid"]
    first_followup_uid = first[0]["followup_uid"]
    first_interface_uid = first[0]["derived_interface_uid"]
    assert first_run_uid
    assert first_followup_uid
    assert first_interface_uid is None
    assert len(first[0]["artifact_refs"]) == 1

    state_after_first = _relaxation_state(sqlite_uow_factory)
    assert state_after_first["run_uids"] == {first_run_uid}
    assert state_after_first["run_status"] == {first_run_uid: "done"}
    assert state_after_first["followup_uids"] == {first_followup_uid}
    assert state_after_first["interface_uids"] == set()
    assert len(state_after_first["artifact_uids"]) == 1

    reopened = Workspace(
        out_dir=tmp_path / "out",
        artifact_store=FSArtifactStore(tmp_path / "out"),
        uow_factory=sqlite_uow_factory,
    )
    resumed = reopened.run_relaxation_stage(
        [prototype_uid],
        max_steps=1,
        backend="deterministic",
        resume=True,
    )
    assert resumed == [
        {
            "prototype_uid": prototype_uid,
            "status": "skipped",
            "run_uid": first_run_uid,
            "followup_uid": None,
            "reason": "run_already_done",
            "derived_interface_uid": None,
            "relaxed_interface_uid": None,
            "artifact_refs": None,
        }
    ]
    assert _relaxation_state(sqlite_uow_factory) == state_after_first

    changed = reopened.run_relaxation_stage(
        [prototype_uid],
        max_steps=2,
        backend="deterministic",
        resume=False,
    )
    assert len(changed) == 1
    assert changed[0]["status"] == "completed"
    changed_run_uid = changed[0]["run_uid"]
    changed_followup_uid = changed[0]["followup_uid"]
    changed_interface_uid = changed[0]["derived_interface_uid"]
    assert changed_run_uid != first_run_uid
    assert changed_followup_uid != first_followup_uid
    assert changed_interface_uid is None

    state_after_changed_input = _relaxation_state(sqlite_uow_factory)
    assert state_after_changed_input["run_uids"] == {
        first_run_uid,
        changed_run_uid,
    }
    assert state_after_changed_input["run_status"] == {
        first_run_uid: "done",
        changed_run_uid: "done",
    }
    assert state_after_changed_input["followup_uids"] == {
        first_followup_uid,
        changed_followup_uid,
    }
    assert state_after_changed_input["interface_uids"] == set()
    assert len(state_after_changed_input["artifact_uids"]) == 2

    failing_backend = _FailingRelaxationBackend()
    with pytest.warns(
        UserWarning,
        match=r"Relaxation backend error .*failing backend",
    ):
        failed_run, failed_results = (
            RelaxationOrchestrator(sqlite_uow_factory())
            .with_backend(failing_backend)
            .run_stage(
                prototypes=[prototype_uid],
                max_steps=1,
                resume=False,
            )
        )
    assert failing_backend.calls == [prototype_uid]
    assert failed_run.status == "failed"
    assert failed_run.uid_full not in {first_run_uid, changed_run_uid}
    assert len(failed_results) == 1
    assert failed_results[0].status == "failed"
    assert failed_results[0].reason == "failing backend"
    failed_followup_uid = failed_results[0].followup_uid
    assert failed_followup_uid

    state_after_failure = _relaxation_state(sqlite_uow_factory)
    assert state_after_failure["run_status"][failed_run.uid_full] == "failed"
    assert state_after_failure["run_errors"][failed_run.uid_full] == {"n_failed": 1}
    assert state_after_failure["followups_by_run"][failed_run.uid_full] == {
        failed_followup_uid
    }
    assert len(state_after_failure["artifact_uids"]) == 2
    assert len(state_after_failure["interface_uids"]) == 0

    retry_backend = _FailingRelaxationBackend()
    with pytest.warns(
        UserWarning,
        match=r"Relaxation backend error .*failing backend",
    ):
        retried_run, retried_results = (
            RelaxationOrchestrator(sqlite_uow_factory())
            .with_backend(retry_backend)
            .run_stage(
                prototypes=[prototype_uid],
                max_steps=1,
                resume=True,
            )
        )
    assert retry_backend.calls == [prototype_uid]
    assert retried_run.uid_full == failed_run.uid_full
    assert retried_run.status == "failed"
    assert len(retried_results) == 1
    assert retried_results[0].status == "failed"
    assert retried_results[0].followup_uid == failed_followup_uid
    assert _relaxation_state(sqlite_uow_factory) == state_after_failure
