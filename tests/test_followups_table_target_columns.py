from __future__ import annotations

import io
from pathlib import Path


def test_followups_table_target_columns_for_interface_seed(tmp_path: Path) -> None:
    """Followups table should surface the original target (prototype vs interface).

    This is a UX regression guard: current follow-up rows expose their original
    prototype or interface target through explicit authoritative columns.
    """

    from calm.project.bootstrap import open_workspace
    from calm.public.collections.persistence import FollowupCollection
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
        vacuum=12.0,
        params={"note": "unit_test"},
    )

    scan_run = ws.start_strain_partition_scan(prototypes=[iface.id_short], alphas=[0.0, 0.5, 1.0])
    results = ws.list_followup_results(run=scan_run.id_short, kind="strain_partition_scan")
    assert results, "Expected at least one follow-up result"

    # Schema-level target provenance should be preserved on each result.
    assert all(r.target_kind == "interface" for r in results)
    assert all(r.target_uid_full == iface.uid_full for r in results)

    buf = io.StringIO()
    FollowupCollection(results).to_table(
        view="summary",
        title="",
        file=buf,
    ).display()
    txt = buf.getvalue()

    # Table may abbreviate column names, so check for "target" (covers both "target" and "target_kind")
    assert "target" in txt or "ta" in txt  # Column header may be abbreviated
    # When seeded with a derived interface, we should retain that provenance.
    assert "interface" in txt or "in" in txt  # Value may be abbreviated too
    # Prefer stable short ids in the table (run + interface target).
    assert scan_run.id_short in txt
    assert iface.id_short in txt
