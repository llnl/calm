from __future__ import annotations

from pathlib import Path

import pytest


def test_workspace_derive_interfaces_from_strain_partition_scan_smoke(tmp_path: Path) -> None:
    """Strain-scan derivation preserves seed parameters, not its atom artifact."""

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

    built = ws.build_interface_from_prototype(p0.id_short)
    seed = ws.create_derived_interface(
        p0.id_short,
        label="seed_iface",
        registry_shift_frac_a=(0.1, -0.2),
        vacuum=12.0,
        params={"note": "unit_test"},
        atoms=built.atoms,
    )

    scan_run = ws.start_strain_partition_scan(prototypes=[seed.id_short], alphas=[0.0, 0.5, 1.0])
    scan_results = ws.list_followup_results(run=scan_run.id_short, kind="strain_partition_scan")
    assert scan_results

    r0 = scan_results[0]
    assert r0.target_kind == "interface"
    assert r0.target_uid_full == seed.uid_full

    derived = ws.derive_interfaces_from_strain_partition_scan(scan_run.id_short, label="best_strain")
    assert len(derived) == 1

    d0 = derived[0]
    assert d0.prototype_uid_full == p0.uid_full
    assert d0.spec.get("strain_alpha") == r0.payload["selection"]["alpha"]
    assert d0.spec.get("registry_shift_frac_a") == seed.spec.get("registry_shift_frac_a")
    assert d0.spec.get("vacuum") == seed.spec.get("vacuum")
    assert d0.atoms_artifact_uid is None
    assert d0.artifact_refs == []
    with pytest.raises(KeyError, match="No atoms available"):
        ws.get_derived_interface_atoms(d0.uid_full)

    from calm.slab.oriented.cell_contract import (
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    )

    seed_atoms = ws.get_derived_interface_atoms(seed.uid_full)
    derived_atoms = ws.materialize_derived_interface_atoms(d0.uid_full)
    seed_accounting = seed_atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
    derived_accounting = derived_atoms.info[
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY
    ]
    assert derived_accounting["policy"] == seed_accounting["policy"]
    assert derived_accounting["version"] == seed_accounting["version"]
    for side in ("lower", "upper"):
        assert (
            derived_accounting[side]["F_construction_slab"]
            == seed_accounting[side]["F_construction_slab"]
        )

    lineage = ws.list_edges(src=seed.uid_full, kind="interface_to_interface")
    assert any(edge.dst_uid_full == d0.uid_full for edge in lineage)
    edges = ws.list_edges(src=r0.uid_full, kind="followup_to_interface")
    assert any(e.dst_uid_full == d0.uid_full for e in edges)


def test_workspace_derive_interfaces_from_registry_search_smoke(
    tmp_path: Path,
    stub_authoritative_registry_evaluator,
) -> None:
    """Registry derivation preserves seed strain without reusing its artifact."""

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

    # The artifact and persisted seed specification must describe the same build.
    built = ws.build_interface_from_prototype(
        p0.id_short,
        alpha=0.25,
        z_padding=2.25,
        vacuum=12.0,
    )
    seed = ws.create_derived_interface(
        p0.id_short,
        label="seed_iface",
        strain_alpha=0.25,
        z_padding=2.25,
        vacuum=12.0,
        params={"note": "unit_test"},
        atoms=built.atoms,
    )

    reg_run = ws.start_registry_search(prototypes=[seed.id_short], n_steps=10)
    reg_results = ws.list_followup_results(run=reg_run.id_short, kind="registry_search")
    assert reg_results

    r0 = reg_results[0]
    assert r0.target_kind == "interface"
    assert r0.target_uid_full == seed.uid_full

    derived = ws.derive_interfaces_from_registry_search(reg_run.id_short, label="best_registry")
    assert len(derived) == 1

    d0 = derived[0]
    assert d0.prototype_uid_full == p0.uid_full
    assert d0.spec.get("strain_alpha") == seed.spec.get("strain_alpha")
    assert d0.spec.get("registry_shift_frac_a") == r0.payload.get("registry_shift_frac_a")
    assert r0.payload.get("z_padding") == 2.25
    assert d0.spec.get("z_padding") == 2.25
    vac0 = r0.payload.get("vacuum")
    assert isinstance(vac0, (int, float))
    assert d0.spec.get("vacuum") == float(vac0) == 12.0
    assert d0.atoms_artifact_uid is None
    assert d0.artifact_refs == []
    with pytest.raises(KeyError, match="No atoms available"):
        ws.get_derived_interface_atoms(d0.uid_full)

    from calm.slab.oriented.cell_contract import (
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    )

    seed_atoms = ws.get_derived_interface_atoms(seed.uid_full)
    derived_atoms = ws.materialize_derived_interface_atoms(d0.uid_full)
    assert (
        derived_atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
        == seed_atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
    )

    lineage = ws.list_edges(src=seed.uid_full, kind="interface_to_interface")
    assert any(edge.dst_uid_full == d0.uid_full for edge in lineage)
    edges = ws.list_edges(src=r0.uid_full, kind="followup_to_interface")
    assert any(e.dst_uid_full == d0.uid_full for e in edges)
