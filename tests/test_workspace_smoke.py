from __future__ import annotations

from pathlib import Path


def test_workspace_smoke_roundtrip(tmp_path: Path) -> None:
    """Workspace UX should support a minimal reopen + list workflow.

    This is intentionally small: it validates the new layering+bootstrap wiring
    without depending on any removed legacy facade.
    """

    from calm.project.bootstrap import open_workspace
    from calm.project.runtime.workspace import Workspace

    ws = open_workspace(root=tmp_path)
    assert isinstance(ws, Workspace)

    bulk = ws.add_bulk(label="Al", payload={"source": "unit_test"})
    assert bulk.id_short.startswith("b_")

    slabs = ws.build_slabs(bulk.id_short, millers=[(1, 1, 1)], payload={"note": "x"})
    assert slabs, "Expected at least one slab"
    assert slabs[0].id_short.startswith("s_")

    # Re-open and verify list APIs are stable.
    ws2 = open_workspace(root=tmp_path)
    bulks = ws2.list_bulks()
    assert any(b.id_short == bulk.id_short for b in bulks)

    slabs2 = ws2.list_slabs()
    assert any(s.id_short == slabs[0].id_short for s in slabs2)
