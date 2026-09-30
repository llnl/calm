from __future__ import annotations

import json
from pathlib import Path


def test_orch_helpers_persist_artifact_payloads_resolvable(tmp_path: Path) -> None:
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.orch_helpers import (
        persist_artifact_payloads,
    )

    ws = open_workspace(root=tmp_path)
    run = ws.create_run(run_type="unit_test", spec={"x": 1})

    with ws._uow_factory() as uow:
        artifact_uids = persist_artifact_payloads(
            uow=uow,
            run_uid=run.uid_full,
            proto_uid="proto:test",
            target_uid="target:1",
            artifact_payloads=[{"k": 1}],
            artifacts=ws._artifacts,
        )

    assert len(artifact_uids) == 1
    with ws._uow_factory() as uow:
        stored = uow.artifacts.get_by_uid_full(artifact_uids[0])
        edges = uow.edges.list(
            src_uid_full=run.uid_full,
            kind="run_to_artifact",
        )

    assert stored is not None
    assert stored.uri.startswith("file://")
    path = ws.artifact_path(stored)
    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"k": 1}
    matching_edges = [edge for edge in edges if edge.dst_uid_full == stored.uid_full]
    assert len(matching_edges) == 1
    assert matching_edges[0].payload["prototype_uid_full"] == "proto:test"
    assert matching_edges[0].payload["target_uid_full"] == "target:1"

    reopened = open_workspace(root=tmp_path)
    found = {artifact.uid_full: artifact for artifact in reopened.list_artifacts(run.id_short)}
    assert reopened.open_artifact(found[stored.uid_full], mode="json") == {"k": 1}
