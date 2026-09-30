from __future__ import annotations

from pathlib import Path


def test_workspace_runs_artifacts_smoke_roundtrip(tmp_path: Path) -> None:
    from calm.project.bootstrap import open_workspace
    from calm.project.runtime.workspace import Workspace

    ws = open_workspace(root=tmp_path)
    assert isinstance(ws, Workspace)

    run = ws.create_run(run_type="unit_test", spec={"x": 1})
    assert run.id_short.startswith("r_")
    assert run.status == "queued"

    art_log = ws.put_log(run.id_short, text="hello\n", filename="hello.txt")
    assert art_log.id_short.startswith("a_")
    assert art_log.run_uid_full == run.uid_full

    art_plot = ws.put_plot(run.id_short, data=b"PNG", filename="plot.png")
    assert art_plot.id_short.startswith("a_")
    assert art_plot.run_uid_full == run.uid_full

    art_struct = ws.put_structure(run.id_short, text="STRUCT\n", filename="struct.xyz")
    assert art_struct.id_short.startswith("a_")
    assert art_struct.run_uid_full == run.uid_full

    expected_log = tmp_path / "out" / "runs" / run.id_short / "logs" / "hello.txt"
    expected_plot = tmp_path / "out" / "runs" / run.id_short / "plots" / "plot.png"
    expected_struct = tmp_path / "out" / "runs" / run.id_short / "structures" / "struct.xyz"

    assert expected_log.exists(), f"Expected artifact file to exist: {expected_log}"
    assert expected_plot.exists(), f"Expected artifact file to exist: {expected_plot}"
    assert expected_struct.exists(), f"Expected artifact file to exist: {expected_struct}"

    # Reopen and list
    ws2 = open_workspace(root=tmp_path)
    arts = ws2.list_artifacts(run.id_short)

    kinds = {a.kind for a in arts}
    assert {"log", "plot", "structure"}.issubset(kinds)
