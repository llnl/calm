from __future__ import annotations

import io

from pathlib import Path


def test_workspace_derived_interfaces_smoke_roundtrip(tmp_path: Path) -> None:
    from calm.project.bootstrap import open_workspace
    from calm.public.collections.interfaces import InterfaceCollection
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

    run = ws.start_prototype_search(slabs[0].id_short, slabs[1].id_short, n_candidates=3)
    protos = ws.list_prototypes(run=run.id_short, limit=1)
    assert protos, "Expected at least one prototype"

    p0 = protos[0]

    iface = ws.create_derived_interface(
        p0.id_short,
        label="scan_candidate",
        strain_alpha=0.25,
        registry_shift_frac_a=(0.10, -0.20),
        vacuum=12.0,
        params={"note": "unit_test"},
    )

    assert iface.id_short.startswith("i_"), "Expected interface id_short to be tagged with i_"
    assert iface.prototype_uid_full == p0.uid_full
    assert iface.spec.get("prototype") == p0.uid_full

    # Composability: allow using an existing derived interface as a seed.
    # The resulting record should merge the seed spec with any overrides.
    iface2 = ws.create_derived_interface(
        iface.id_short,
        label="tuned_vacuum",
        vacuum=15.0,
        params={"note2": "x"},
    )
    assert iface2.id_short.startswith("i_")
    assert iface2.prototype_uid_full == p0.uid_full
    assert iface2.spec.get("prototype") == p0.uid_full
    assert iface2.spec.get("strain_alpha") == 0.25
    assert iface2.spec.get("registry_shift_frac_a") == [0.1, 0.8]
    assert iface2.spec.get("vacuum") == 15.0
    assert iface2.spec.get("params") == {"note": "unit_test", "note2": "x"}

    # Listing should round-trip.
    ifaces = ws.list_derived_interfaces(prototype=p0.id_short)
    assert any(x.uid_full == iface.uid_full for x in ifaces)
    assert any(x.uid_full == iface2.uid_full for x in ifaces)

    # Provenance edge should exist.
    edges = ws.list_edges(src=p0.uid_full, kind="prototype_to_interface")
    assert any(e.dst_uid_full == iface.uid_full for e in edges)
    assert any(e.dst_uid_full == iface2.uid_full for e in edges)

    # Provenance should also capture interface→interface composition.
    edges2 = ws.list_edges(src=iface.uid_full, kind="interface_to_interface")
    assert any(e.dst_uid_full == iface2.uid_full for e in edges2)

    # Canonical provenance fields should round-trip independently of terminal
    # width constraints and presentation-only display labels.
    collection = InterfaceCollection(items=ifaces)
    provenance_rows = collection.to_rows(view="provenance")
    assert provenance_rows
    assert "id_short" in provenance_rows[0]
    assert "prototype_uid_full" in provenance_rows[0]

    # The bounded terminal presentation should render without raising.
    buf = io.StringIO()
    collection.to_table(
        view="provenance",
        title="",
        file=buf,
    ).display()
    assert buf.getvalue().strip()
