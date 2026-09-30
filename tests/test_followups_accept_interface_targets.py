from __future__ import annotations

from pathlib import Path


def test_followups_accept_interface_targets_smoke(
    tmp_path: Path,
    stub_authoritative_registry_evaluator,
) -> None:
    """Followups should accept derived-interface ids as inputs.

    This validates the workflow wiring needed to run followups on modified
    interface variants (spec-only records) without schema changes.
    """

    from calm.project.bootstrap import open_workspace
    from calm.project.runtime.workspace import Workspace
    from test_helpers import make_test_bulk

    ws = open_workspace(root=tmp_path)
    assert isinstance(ws, Workspace)

    # Create bulks with real atomic structures
    bulk1 = make_test_bulk(ws, "Al", "fcc", 4.05)
    bulk2 = make_test_bulk(ws, "Cu", "fcc", 3.61)

    slabs1 = ws.build_slabs(bulk1.id_short, millers=[(1, 1, 1)])
    slabs2 = ws.build_slabs(bulk2.id_short, millers=[(2, 0, 0)])
    slabs = slabs1 + slabs2
    assert len(slabs) == 2

    proto_run = ws.start_prototype_search(slabs[0].id_short, slabs[1].id_short, n_candidates=3)
    protos = ws.list_prototypes(run=proto_run.id_short, limit=1)
    assert protos, "Expected at least one prototype"

    p0 = protos[0]

    iface = ws.create_derived_interface(
        p0.id_short,
        label="seed_iface",
        strain_alpha=0.25,
        registry_shift_frac_a=(0.1, -0.2),
        vacuum=12.0,
        params={"note": "unit_test"},
    )

    # Strain scan should accept an interface id_short as the seed.
    scan_run = ws.start_strain_partition_scan(prototypes=[iface.id_short])
    scan_results = ws.list_followup_results(run=scan_run.id_short, kind="strain_partition_scan")
    assert scan_results

    r0 = scan_results[0]
    assert r0.prototype_uid_full == p0.uid_full
    assert r0.target_uid_full == iface.uid_full
    assert r0.target_kind == "interface"

    # Registry search should accept an interface id_short as the seed.
    reg_run = ws.start_registry_search(prototypes=[iface.id_short], n_steps=10)
    reg_results = ws.list_followup_results(run=reg_run.id_short, kind="registry_search")
    assert reg_results

    r1 = reg_results[0]
    assert r1.prototype_uid_full == p0.uid_full
    assert r1.target_uid_full == iface.uid_full
    assert r1.target_kind == "interface"

    # Provenance edge should exist.
    edges = ws.list_edges(src=iface.uid_full, kind="interface_to_followup")
    assert edges, "Expected at least one interface_to_followup edge"

    # ---------------------------------------------------------------------
    # Interface-target filtering should be precise (not just by base prototype).
    # ---------------------------------------------------------------------
    iface2 = ws.create_derived_interface(
        p0.id_short,
        label="seed_iface2",
        strain_alpha=0.75,
        registry_shift_frac_a=(0.0, 0.0),
        vacuum=11.0,
        params={"note": "unit_test_2"},
    )

    scan_run2 = ws.start_strain_partition_scan(prototypes=[iface2.id_short])
    scan_results2 = ws.list_followup_results(run=scan_run2.id_short, kind="strain_partition_scan")
    assert scan_results2

    r2 = scan_results2[0]
    assert r2.target_uid_full == iface2.uid_full
    assert r2.target_kind == "interface"

    # Filter by interface should return only that interface's results.
    iface_results = ws.list_followup_results(prototype=iface.id_short, kind="strain_partition_scan")
    assert len(iface_results) == 1
    assert iface_results[0].uid_full == r0.uid_full
    assert iface_results[0].target_uid_full == iface.uid_full

    # Filter by base prototype should include both interface-seeded runs.
    proto_results = ws.list_followup_results(prototype=p0.id_short, kind="strain_partition_scan")
    assert {x.target_uid_full for x in proto_results} >= {
        iface.uid_full,
        iface2.uid_full,
    }
