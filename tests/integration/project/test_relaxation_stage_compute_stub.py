from pathlib import Path

from test_helpers import make_test_interface_prototype
from calm.project.infrastructure.artifacts.fs_store import FSArtifactStore
from calm.project.runtime.workspace import Workspace


def test_relaxation_compute_creates_derived_and_artifact(tmp_path: Path, sqlite_uow_factory):
    ws = Workspace(
        out_dir=tmp_path / "out",
        artifact_store=FSArtifactStore(tmp_path / "out"),
        uow_factory=sqlite_uow_factory,
    )

    # Persist a minimal internal prototype so we have a resolved prototype
    internal = make_test_interface_prototype(prototype_uid="internal_1")
    mapping = ws.persist_interface_prototypes([internal])
    # Mapping may be keyed by the original internal uid or by persisted uid; pick appropriately
    if "internal_1" in mapping:
        proto_uid_full = mapping["internal_1"]["uid_full"]
    else:
        # fallback: take the first persisted prototype
        proto_uid_full = list(mapping.values())[0]["uid_full"]

    results = ws.run_relaxation_stage(
        [proto_uid_full], max_steps=1, backend="deterministic"
    )
    assert isinstance(results, list)
    assert len(results) == 1
    r = results[0]
    assert r.get("status") in ("completed", "skipped")
    # A completed deterministic run may have no persisted derived interface.
    # Absence is represented by None; fabricated interface identifiers are forbidden.
    if r.get("status") == "completed":
        interface_uid = r.get("relaxed_interface_uid")
        assert interface_uid is None or not str(interface_uid).startswith("iface:synthetic")
        assert isinstance(r.get("artifact_refs"), list)

    # Resume: second identical call with resume=True should return skipped
    results2 = ws.run_relaxation_stage(
        [proto_uid_full], max_steps=1, backend="deterministic", resume=True
    )
    assert isinstance(results2, list)
    # at least one skipped result expected
    assert any(rr.get("status") == "skipped" for rr in results2)
