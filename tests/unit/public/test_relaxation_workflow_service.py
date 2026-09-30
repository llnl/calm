from __future__ import annotations

from typing import Any

import pytest

from calm.public.workflows.relaxation import ProjectRelaxationWorkflowService
from calm.public.inputs.settings import RelaxSettings


def _interface(
    uid: str,
    *,
    stage: str = "registry_refined",
    search_name: str = "search-a",
    source_run_uid: str | None = None,
    authority: str = "authoritative",
) -> dict[str, Any]:
    row = {
        "uid_full": uid,
        "id_short": uid.replace("iface:", "i_"),
        "label": uid,
        "prototype_uid_full": "proto:1",
        "stage": stage,
        "search_name": search_name,
        "authority": authority,
    }
    if source_run_uid is not None:
        row["source_run_uid"] = source_run_uid
    return row


def _run() -> dict[str, Any]:
    return {
        "uid_full": "run:relax",
        "id_short": "r_relax",
        "run_type": "relaxation_stage",
        "status": "done",
        "spec": {},
        "authority": "authoritative",
    }


def _result(*, status: str = "done", failure: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "relaxation_backend": "deterministic",
        "backend_identity": {"name": "deterministic"},
        "relaxation_settings": {
            "fmax": 0.02,
            "steps": 100,
            "relax_cell": False,
        },
    }
    if failure is not None:
        payload["error"] = {"message": failure}
    return {
        "uid_full": "followup:relax",
        "id_short": "f_relax",
        "run_uid_full": "run:relax",
        "run_id_short": "r_relax",
        "prototype_uid_full": "proto:1",
        "target_uid_full": "iface:refined",
        "target_kind": "interface",
        "kind": "relaxation_stage",
        "status": status,
        "payload": payload,
        "authority": "authoritative",
    }


class _Repository:
    def __init__(self) -> None:
        self.interfaces = {
            "iface:refined": _interface("iface:refined"),
            "iface:strain": _interface(
                "iface:strain",
                stage="strain_partitioned",
            ),
            "iface:other": _interface(
                "iface:other",
                search_name="search-b",
            ),
            "iface:relaxed": _interface(
                "iface:relaxed",
                stage="relaxed",
                source_run_uid="run:relax",
            ),
        }
        self.followups = [_result()]
        self.list_calls: list[str | None] = []

    def list_interfaces(self, *, search_name=None, limit=None):
        del limit
        self.list_calls.append(search_name)
        return [
            row
            for row in self.interfaces.values()
            if search_name is None or row["search_name"] == search_name
        ]

    def get_interface(self, identifier: str):
        return self.interfaces[str(identifier)]

    def get_run(self, identifier: str):
        assert identifier == "run:relax"
        return _run()

    def list_followup_results(
        self,
        *,
        run=None,
        prototype=None,
        kind=None,
        status=None,
        limit=None,
    ):
        del prototype, status, limit
        assert run == "run:relax"
        assert kind == "relaxation_stage"
        return list(self.followups)


class _Workspace:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run_relaxation_stage(self, prototypes, **kwargs):
        self.calls.append({"prototypes": list(prototypes), **kwargs})
        return [
            {
                "run_uid": "run:relax",
                "status": "done",
                "target_uid": uid,
            }
            for uid in prototypes
        ]


def _service() -> tuple[ProjectRelaxationWorkflowService, _Workspace, _Repository]:
    workspace = _Workspace()
    repository = _Repository()
    project = object()
    return (
        ProjectRelaxationWorkflowService(
            project=project,
            workspace=workspace,
            repository=repository,
        ),
        workspace,
        repository,
    )


def test_relaxation_workflow_is_composed_by_service() -> None:
    service, workspace, _repository = _service()
    settings = RelaxSettings(fmax=0.03, steps=12, relax_cell=False)

    workflow = service.relax_interfaces(
        ["iface:refined", "iface:refined"],
        settings=settings,
        backend="deterministic",
        partial_resume=True,
    )

    assert workflow.run.uid_full == "run:relax"
    assert [row.uid_full for row in workflow.results] == ["followup:relax"]
    assert [row.uid_full for row in workflow.relaxed_interfaces] == [
        "iface:relaxed"
    ]
    assert workspace.calls[0]["prototypes"] == ["iface:refined"]
    assert workspace.calls[0]["protocol"] == "ionic_positions_v1"
    assert workspace.calls[0]["convergence"] == {"force_tol": 0.03}
    assert workspace.calls[0]["max_steps"] == 12
    assert workspace.calls[0]["partial_resume"] is True
    assert workspace.calls[0]["payload"]["public_api"] == (
        "Project.relax_interfaces"
    )


def test_default_target_selection_is_stage_and_search_scoped() -> None:
    service, workspace, repository = _service()

    service.relax_interfaces(
        None,
        backend="deterministic",
        stage="strain_partitioned",
        search_name="search-a",
    )

    assert repository.list_calls[0] == "search-a"
    assert workspace.calls[0]["prototypes"] == ["iface:strain"]


def test_explicit_target_must_match_requested_search() -> None:
    service, workspace, _repository = _service()

    with pytest.raises(ValueError, match="belongs to search 'search-b'"):
        service.relax_interfaces(
            "iface:other",
            backend="deterministic",
            search_name="search-a",
        )

    assert workspace.calls == []


def test_relaxation_rejects_unrefined_or_projection_targets() -> None:
    service, workspace, repository = _service()
    repository.interfaces["iface:built"] = _interface(
        "iface:built",
        stage="built",
    )
    repository.interfaces["iface:projection"] = _interface(
        "iface:projection",
        authority="projection",
    )

    with pytest.raises(ValueError, match="strain_partitioned or registry_refined"):
        service.relax_interfaces("iface:built", backend="deterministic")
    with pytest.raises(ValueError, match="authoritative persisted interfaces"):
        service.relax_interfaces("iface:projection", backend="deterministic")

    assert workspace.calls == []


def test_relaxation_failure_policy_uses_persisted_results() -> None:
    service, _workspace, repository = _service()
    repository.followups = [_result(status="failed", failure="backend failed")]

    with pytest.raises(RuntimeError, match="backend failed"):
        service.relax_interfaces("iface:refined", backend="deterministic")

    workflow = service.relax_interfaces(
        "iface:refined",
        backend="deterministic",
        on_error="record",
    )
    assert len(workflow.failures) == 1


def test_custom_backend_requires_explicit_identity() -> None:
    service, workspace, _repository = _service()

    with pytest.raises(TypeError, match="must implement identity"):
        service.relax_interfaces("iface:refined", backend=object())

    assert workspace.calls == []


def test_stage_adapter_forwards_campaign_context() -> None:
    service, workspace, _repository = _service()

    rows = service.run_relaxation_stage(
        ["iface:refined"],
        backend="deterministic",
        campaign_uid_full="campaign:x",
        campaign_run_uid_full="campaign-run:x",
    )

    assert rows[0]["run_uid"] == "run:relax"
    assert workspace.calls[0]["campaign_uid_full"] == "campaign:x"
    assert workspace.calls[0]["campaign_run_uid_full"] == "campaign-run:x"
