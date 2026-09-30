from __future__ import annotations

from pathlib import Path


def test_workspace_followups_smoke_roundtrip(
    tmp_path: Path,
    stub_authoritative_registry_evaluator,
) -> None:
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

    proto_run = ws.start_prototype_search(slabs[0].id_short, slabs[1].id_short, n_candidates=6)
    assert proto_run.status == "done"

    protos = ws.list_prototypes(run=proto_run.id_short)
    assert protos, "Expected at least one prototype"

    proto_ids = [p.id_short for p in protos[:3]]

    scan_run = ws.start_strain_partition_scan(proto_ids, alphas=[0.0, 0.5, 1.0], payload={"note": "scan"})
    assert scan_run.id_short.startswith("r_")
    assert scan_run.status == "done"

    scan_results = ws.list_followup_results(run=scan_run.id_short, kind="strain_partition_scan")
    assert len(scan_results) == len(proto_ids)
    assert all(r.kind == "strain_partition_scan" for r in scan_results)
    assert all(r.param1 is not None for r in scan_results)

    # Reopen and ensure query + plot works.
    ws2 = open_workspace(root=tmp_path)

    scan_results2 = ws2.list_followup_results(run=scan_run.id_short)
    assert len(scan_results2) == len(proto_ids)

    art = ws2.strain_partition_plot(scan_run.id_short, filename="strain.png")
    assert art.id_short.startswith("a_")
    expected = tmp_path / "out" / "runs" / scan_run.id_short / "plots" / "strain.png"
    assert expected.exists(), f"Expected artifact file to exist: {expected}"

    reg_run = ws2.start_registry_search(proto_ids, n_steps=5, payload={"note": "reg"})
    assert reg_run.status == "done"

    reg_results = ws2.list_followup_results(run=reg_run.id_short, kind="registry_search")
    assert len(reg_results) == len(proto_ids)
    assert all(r.kind == "registry_search" for r in reg_results)
    assert any(r.param2 is not None for r in reg_results)

    art2 = ws2.registry_search_plot(reg_run.id_short, filename="registry.png")
    assert art2.id_short.startswith("a_")
    expected2 = tmp_path / "out" / "runs" / reg_run.id_short / "plots" / "registry.png"
    assert expected2.exists(), f"Expected artifact file to exist: {expected2}"
