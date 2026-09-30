from __future__ import annotations

from pathlib import Path


def test_workspace_artifact_roundtrip_reopen_for_file_uris(tmp_path: Path) -> None:
    from calm.project.bootstrap import open_workspace

    ws = open_workspace(root=tmp_path)

    run = ws.create_run(run_type="unit_test", spec={"x": 1})

    log_art = ws.put_log(run.id_short, text="hello\n", filename="hello.txt")
    json_art = ws.put_json(run.id_short, obj={"a": 1}, filename="data.json")

    # URIs should be canonical (file://) from the store
    assert isinstance(log_art.uri, str) and log_art.uri.startswith("file://")
    assert isinstance(json_art.uri, str) and json_art.uri.startswith("file://")

    # artifact_path and resolve_uri should agree
    p1 = ws.artifact_path(log_art)
    p2 = ws.resolve_uri(log_art.uri)
    assert p1 == p2

    # open via artifact ref and raw uri
    assert ws.open_artifact(log_art, mode="text") == "hello\n"
    assert ws.open_artifact(log_art.uri, mode="text") == "hello\n"
    assert ws.open_artifact(json_art, mode="json") == {"a": 1}

    # Reopen workspace to simulate a new process
    ws2 = open_workspace(root=tmp_path)
    arts = ws2.list_artifacts(run.id_short)
    # Ensure artifacts exist and can be opened again
    # Map artifacts by resolved filename using artifact_path
    found = {ws2.artifact_path(a).name: a for a in arts}
    assert "hello.txt" in found and "data.json" in found
    assert ws2.open_artifact(found["hello.txt"], mode="text") == "hello\n"
    assert ws2.open_artifact(found["data.json"], mode="json") == {"a": 1}



def test_resolve_uri_rejects_noncanonical_paths(tmp_path: Path) -> None:
    import pytest

    from calm.project.bootstrap import open_workspace

    ws = open_workspace(root=tmp_path)

    with pytest.raises(ValueError, match="file://"):
        ws.resolve_uri("runs/r_deadbeef/logs/output.txt")

    with pytest.raises(ValueError, match="file://"):
        ws.resolve_uri(str((tmp_path / "output.txt").resolve()))

    outside = (tmp_path.parent / "outside.txt").resolve().as_uri()
    with pytest.raises(ValueError, match="outside the workspace"):
        ws.resolve_uri(outside)

    with pytest.raises(ValueError, match="file host"):
        ws.resolve_uri("file://localhost/tmp/output.txt")

    with pytest.raises(ValueError, match="query or fragment"):
        ws.resolve_uri("file:///tmp/output.txt?version=1")

    with pytest.raises(ValueError, match="mode must be one of"):
        ws.open_artifact("file:///tmp/output.txt", mode="r")
