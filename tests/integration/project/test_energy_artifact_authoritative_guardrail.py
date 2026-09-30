from pathlib import Path

from test_helpers import make_test_interface_prototype
from calm.public.project import open_project
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.runtime.workspace import Workspace


def test_energy_artifact_persistence_is_database_owned(tmp_path: Path, sqlite_uow_factory):
    ws = Workspace(
        out_dir=tmp_path / "out",
        artifact_store=FSArtifactStore(tmp_path / "out"),
        uow_factory=sqlite_uow_factory,
    )

    project = open_project(str(tmp_path), summarize=False)
    internal = make_test_interface_prototype(
        prototype_uid="internal_4",
        match_score=0.4,
    )
    mapping = ws.persist_interface_prototypes([internal])
    proto_uid_full = list(mapping.values())[0]["uid_full"]

    results = ws.run_energy_stage(
        [proto_uid_full],
        calculation={},
        backend="deterministic",
    )
    assert isinstance(results, list)
    for result in results:
        if result.get("status") == "completed":
            assert isinstance(result.get("artifact_refs", []), list)

    reopened = open_project(str(tmp_path), summarize=False)
    assert not hasattr(reopened, "_public_records")
    assert not (tmp_path / "calm-public-records.json").exists()
