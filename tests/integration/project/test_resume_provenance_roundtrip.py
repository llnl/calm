from pathlib import Path

from test_helpers import make_test_interface_prototype
from calm.project.bootstrap import open_workspace


def test_derived_interface_artifact_roundtrip_reopen(tmp_path: Path, current_atoms_payload_factory):
    # 1) Create workspace and persist a prototype
    ws1 = open_workspace(root=tmp_path)

    proto_rows = [make_test_interface_prototype(prototype_uid="internal_rt")]
    mapping = ws1.persist_interface_prototypes(proto_rows)
    proto_uid_full = list(mapping.values())[0]["uid_full"]
    run_id = list(mapping.values())[0].get("run_id")

    # 2) Create a derived interface with serialized atoms (avoid ASE dependency)
    atoms_in = current_atoms_payload_factory()
    iface = ws1.create_derived_interface(prototype=proto_uid_full, label="rt_test", atoms=atoms_in)

    # Expect artifact-backed spec
    spec = iface.spec if hasattr(iface, "spec") else (iface.get("spec") if isinstance(iface, dict) else None)
    assert spec is not None
    a_uid = spec.get("atoms_artifact_uid")
    assert a_uid is not None

    # 3) Reopen workspace (new process simulation)
    ws2 = open_workspace(root=tmp_path)

    # 4) Rehydrate atoms from the reopened workspace
    atoms_out = ws2.get_derived_interface_atoms(
        iface.id_short if getattr(iface, "id_short", None) else iface.uid_full
    )
    assert atoms_out is not None
    try:
        import ase  # noqa: F401
    except ImportError:
        assert isinstance(atoms_out, dict)
        assert atoms_out.get("numbers") == atoms_in.get("numbers")
        assert atoms_out.get("pbc") == atoms_in.get("pbc")
    else:
        assert hasattr(atoms_out, "write")
        assert atoms_out.get_atomic_numbers().tolist() == atoms_in["numbers"]
        assert atoms_out.get_pbc().tolist() == atoms_in["pbc"]

    # 5) Verify artifact metadata references canonical interface UID
    arts = ws2.list_artifacts(run_id)
    art = next((a for a in arts if a.uid_full == a_uid), None)
    assert art is not None
    meta = art.metadata or {}
    assert meta.get("interface_uid_full") == iface.uid_full

    # 6) Optionally verify provenance edge run -> artifact exists
    edges = ws2.list_edges(src=run_id, kind="run_to_artifact")
    assert any(e.dst_uid_full == art.uid_full for e in edges)


def test_existing_interface_can_acquire_its_exact_atoms_artifact(tmp_path: Path, current_atoms_payload_factory):
    ws = open_workspace(root=tmp_path)
    mapping = ws.persist_interface_prototypes(
        [make_test_interface_prototype(prototype_uid="internal_attach")]
    )
    proto_uid_full = list(mapping.values())[0]["uid_full"]
    atoms = current_atoms_payload_factory()

    unmaterialized = ws.create_derived_interface(
        prototype=proto_uid_full,
        label="attach_later",
    )
    materialized = ws.create_derived_interface(
        prototype=proto_uid_full,
        label="attach_later",
        atoms=atoms,
    )

    assert materialized.uid_full == unmaterialized.uid_full
    assert materialized.atoms_artifact_uid is not None
    reopened = open_workspace(root=tmp_path)
    persisted = reopened.get_derived_interface(materialized.uid_full)
    assert persisted.atoms_artifact_uid == materialized.atoms_artifact_uid
    restored = reopened.get_derived_interface_atoms(materialized.uid_full)
    try:
        import ase  # noqa: F401
    except ImportError:
        assert restored == atoms
    else:
        assert restored.get_atomic_numbers().tolist() == atoms["numbers"]
