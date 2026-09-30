from pathlib import Path




def test_authoritative_build_and_persist_as_derived_interface(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    payload = hydrogen_atoms_payload_factory()
    prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        prototype_payload=prototype_payload_factory(
            include_supercells=True,
        ),
    )

    from calm.public.project import open_project

    proj = open_project(str(tmp_path))
    prototype_uid = persisted_test_uid("prototype", "proto:x")

    # Build authoritative atoms from prototype
    built = proj._workspace.build_interface_from_prototype(
        prototype_uid,
        alpha=0.5,
        translation_frac=(0.0, 0.0),
        z_padding=1.5,
    )
    assert built.atoms is not None
    from calm.slab.oriented.cell_contract import (
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    )

    accounting = built.atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY]
    assert accounting["policy"] == "composed_slab_deformation"

    # Persist as a derived interface via workspace create_derived_interface wrapper
    iface = proj._workspace.create_derived_interface(
        prototype_uid,
        label="test_iface",
        strain_alpha=0.5,
        atoms=built.atoms,
    )
    assert getattr(iface, "uid_full", None) is not None
    # Fetch persisted derived interface via workspace getter
    fetched = proj._workspace.get_derived_interface(iface.id_short)
    # Current persistence stores interface atoms through one artifact UID.
    spec = fetched.spec
    assert isinstance(spec.get("atoms_artifact_uid"), str)
    # Reconstruction through the exact artifact-backed path should succeed.
    atoms = proj._workspace.get_derived_interface_atoms(iface.id_short)
    assert atoms is not None
    assert atoms.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] == accounting
