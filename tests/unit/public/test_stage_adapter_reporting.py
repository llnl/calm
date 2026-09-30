from test_helpers import CaptureReporter
from calm.public.project import Project


class FakeWorkspace:
    def __init__(self):
        pass

    def run_build_stage(self, prototypes, **kwargs):
        return [{"prototype_uid": p, "status": "completed"} for p in prototypes]

    def run_registry_stage(self, prototypes, **kwargs):
        return [{"prototype_uid": p, "status": "completed"} for p in prototypes]

    def run_relaxation_stage(self, prototypes, **kwargs):
        return [{"prototype_uid": p, "status": "completed"} for p in prototypes]

    def run_energy_stage(self, prototypes, **kwargs):
        return [{"prototype_uid": p, "status": "done"} for p in prototypes]


class FakeProject(Project):
    def __init__(self):
        ws = FakeWorkspace()
        super().__init__(ws, path=None)


def test_relaxation_stage_adapter_emits_stage_and_summary():
    project = FakeProject()
    reporter = CaptureReporter()

    rows = project._relaxation_workflows.run_relaxation_stage(
        ["p1"],
        max_steps=1,
        backend="deterministic",
        reporter=reporter,
    )

    kinds = [event.kind for event in reporter.events]
    assert "stage_start" in kinds and "stage_end" in kinds
    assert len(rows) == 1
    assert rows[0]["prototype_uid"] == "p1"
    assert rows[0]["status"] == "completed"
    assert rows[0]["target_uid"] == "p1"
    assert rows[0]["target_kind"] == "prototype"


def test_energy_stage_adapter_emits_stage_and_summary():
    project = FakeProject()
    reporter = CaptureReporter()

    rows = project._energy_workflows.run_energy_stage(
        ["p1"],
        calculation={},
        reporter=reporter,
    )

    kinds = [event.kind for event in reporter.events]
    assert "stage_start" in kinds and "stage_end" in kinds
    assert len(rows) == 1
    assert rows[0]["prototype_uid"] == "p1"
    assert rows[0]["status"] == "done"
    assert rows[0]["target_uid"] == "p1"
    assert rows[0]["target_kind"] == "prototype"
