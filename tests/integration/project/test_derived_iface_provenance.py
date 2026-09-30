from pathlib import Path

from test_helpers import make_test_interface_prototype
from calm.project.bootstrap import open_workspace


def test_new_derived_interface_artifact_metadata_matches_final_uid(tmp_path: Path):
    ws = open_workspace(root=tmp_path)

    # create a minimal prototype record to reference via persist_interface_prototypes
    protos = [make_test_interface_prototype(prototype_uid="internal_x")]
    mapping = ws.persist_interface_prototypes(protos)
    proto_uid_full = list(mapping.values())[0]["uid_full"]
    # run used by the persist_interface_prototypes call
    run_id = list(mapping.values())[0].get("run_id")

    # Persist a derived interface with atoms via workspace wrapper
    import pytest

    pytest.importorskip("ase")
    from ase import Atoms

    atoms = Atoms("H", positions=[[0, 0, 0]], cell=[[3, 0, 0], [0, 3, 0], [0, 0, 3]], pbc=True)
    iface = ws.create_derived_interface(prototype=proto_uid_full, label="test", atoms=atoms)

    # Ensure artifact uid present in spec
    spec = iface.spec if hasattr(iface, 'spec') else (iface.get('spec') if isinstance(iface, dict) else None)
    assert spec is not None
    assert spec.get('atoms_artifact_uid') is not None

    # Fetch artifact from repo and check metadata
    arts = ws.list_artifacts(run_id)
    found = None
    for a in arts:
        if a.uid_full == spec.get('atoms_artifact_uid'):
            found = a
            break
    assert found is not None
    # artifact metadata must include interface uid (provenance)
    meta = found.metadata or {}
    assert meta.get('interface_uid_full') == iface.uid_full


def test_same_interface_spec_reuses_same_uid_with_artifact_backing(tmp_path: Path):
    ws = open_workspace(root=tmp_path)
    pytest = __import__('pytest')
    pytest.importorskip("ase")
    from ase import Atoms

    atoms = Atoms("H", positions=[[0, 0, 0]], cell=[[3, 0, 0], [0, 3, 0], [0, 0, 3]], pbc=True)

    protos = [make_test_interface_prototype(prototype_uid="internal_y")]
    mapping = ws.persist_interface_prototypes(protos)
    proto_uid_full = list(mapping.values())[0]["uid_full"]
    iface1 = ws.create_derived_interface(prototype=proto_uid_full, label="test", atoms=atoms)
    iface2 = ws.create_derived_interface(prototype=proto_uid_full, label="test", atoms=atoms)
    assert iface1.uid_full == iface2.uid_full
