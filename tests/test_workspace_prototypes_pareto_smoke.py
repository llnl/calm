from __future__ import annotations

from pathlib import Path


def test_workspace_prototypes_pareto_smoke_roundtrip(tmp_path: Path) -> None:
    from calm.project.bootstrap import open_workspace
    from calm.project.runtime.workspace import Workspace
    from test_helpers import make_test_bulk

    ws = open_workspace(root=tmp_path)
    assert isinstance(ws, Workspace)

    # Create bulks with real atomic structures
    bulk1 = make_test_bulk(ws, "Al", "fcc", 4.05)
    bulk2 = make_test_bulk(ws, "Cu", "fcc", 3.61)

    slabs1 = ws.build_slabs(bulk1.id_short, millers=[(1, 1, 1)], payload={"note": "x"})
    slabs2 = ws.build_slabs(bulk2.id_short, millers=[(2, 0, 0)], payload={"note": "x"})
    slabs = slabs1 + slabs2
    assert len(slabs) == 2

    run = ws.start_prototype_search(slabs[0].id_short, slabs[1].id_short, n_candidates=10)
    assert run.id_short.startswith("r_")
    assert run.status == "done"

    protos = ws.list_prototypes(run=run.id_short)
    assert len(protos) == 10
    assert any(p.is_pareto for p in protos)

    pareto = ws.list_prototypes(run=run.id_short, pareto=True)
    assert pareto, "Expected at least one pareto prototype"
    assert all(p.is_pareto for p in pareto)

    # Reopen and ensure query works.
    ws2 = open_workspace(root=tmp_path)
    protos2 = ws2.list_prototypes(run=run.id_short)
    assert len(protos2) == 10

    art = ws2.pareto_plot(run.id_short, filename="pareto.png")
    assert art.id_short.startswith("a_")

    expected_path = tmp_path / "out" / "runs" / run.id_short / "plots" / "pareto.png"
    assert expected_path.exists(), f"Expected pareto plot to exist: {expected_path}"

    arts = ws2.list_artifacts(run.id_short)
    assert any(a.uri and a.uri.endswith("/plots/pareto.png") for a in arts)
