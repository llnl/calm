from pathlib import Path

import pytest

from slab_record_fixtures import current_atoms


def test_interface_query_uses_authoritative_derived_interface(
    tmp_path: Path,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    pytest.importorskip("ase")
    atoms = current_atoms()
    prototype_graph_factory(
        slab_a_payload={"atoms": atoms},
        slab_b_payload={"atoms": atoms},
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    from calm.public.project import open_project

    project = open_project(str(tmp_path), summarize=False)
    persisted = project._workspace.create_derived_interface(
        persisted_test_uid("prototype", "proto:x"),
        label="i_real",
        z_padding=1.5,
        vacuum=10.0,
    )

    rows = project.interfaces().to_rows(view="all")
    assert not hasattr(project, "_public_records")
    assert any(
        row.get("uid_full") == persisted.uid_full
        and row.get("id_short") == persisted.id_short
        and row.get("label") == "i_real"
        for row in rows
    )
