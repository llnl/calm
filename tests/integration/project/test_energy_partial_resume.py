from pathlib import Path

from test_helpers import make_test_interface_prototype
from calm.project.application.followups.energy import EnergyOrchestrator
from calm.project.application.followups.energy_backends import EnergyComputeResult
from calm.project.infrastructure.db.tables import followup_results
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.runtime.workspace import Workspace


class _CountingEnergyBackend:
    name = "counting-energy"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def compute(self, *, run_uid, prototype_uid, target_uid, config, uow=None):
        self.calls.append(target_uid)
        return EnergyComputeResult(
            energy=1.25,
            n_steps=1,
            summary={"energy": 1.25},
            artifact_payloads=[],
        )


def test_partial_resume_recomputes_only_missing_energy_followup(
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
            make_test_interface_prototype(prototype_uid="resume_energy_a"),
            make_test_interface_prototype(
                prototype_uid="resume_energy_b",
                match_score=0.2,
                slab_b_uid="slab:test:b:distinct",
            ),
        ]
    )
    prototype_uids = [row["uid_full"] for row in mapping.values()]
    assert len(prototype_uids) == 2
    assert len(set(prototype_uids)) == 2

    initial_backend = _CountingEnergyBackend()
    run1, initial_results = (
        EnergyOrchestrator(uow)
        .with_backend(initial_backend)
        .run_stage(
            prototypes=prototype_uids,
            calculation={},
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
            kind="energy_stage",
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

    resume_backend = _CountingEnergyBackend()
    run2, resumed_results = (
        EnergyOrchestrator(uow)
        .with_backend(resume_backend)
        .run_stage(
            prototypes=prototype_uids,
            calculation={},
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
            kind="energy_stage",
        )
        assert len(final_rows) == 2
        assert {row.target_uid_full for row in final_rows} == set(prototype_uids)
        assert len({row.uid_full for row in final_rows}) == 2


class _InvalidEnergyBackend:
    name = "invalid-energy"

    def __init__(self, *, energy=1.0, n_steps=1) -> None:
        self.energy = energy
        self.n_steps = n_steps

    def compute(self, *, run_uid, prototype_uid, target_uid, config, uow=None):
        return EnergyComputeResult(
            energy=self.energy,
            n_steps=self.n_steps,
            summary={},
            artifact_payloads=[],
        )


def test_energy_stage_persists_nonfinite_backend_output_as_failure(
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
            make_test_interface_prototype(prototype_uid="invalid_energy")
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]

    run, results = (
        EnergyOrchestrator(uow)
        .with_backend(_InvalidEnergyBackend(energy=float("nan")))
        .run_stage(prototypes=[prototype_uid], calculation={}, resume=False)
    )

    assert run.status == "failed"
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "must be finite" in str(results[0].reason)
    with uow as entered:
        rows = entered.followups.list(run_uid_full=run.uid_full, kind="energy_stage")
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].payload["failure"]["exception_type"] == "ValueError"


def test_energy_stage_rejects_nonpositive_backend_step_count(
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
            make_test_interface_prototype(prototype_uid="invalid_steps")
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]

    run, results = (
        EnergyOrchestrator(uow)
        .with_backend(_InvalidEnergyBackend(n_steps=0))
        .run_stage(prototypes=[prototype_uid], calculation={}, resume=False)
    )

    assert run.status == "failed"
    assert results[0].status == "failed"
    assert "positive integer" in str(results[0].reason)
