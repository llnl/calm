from pathlib import Path

import pytest



def test_authoritative_public_workflow_smoke(
    tmp_path: Path,
):
    # Guard optional deps
    pytest.importorskip("sqlalchemy")

    from calm import Material, open_project

    proj = open_project(str(tmp_path))
    # Public ingest -> surface -> search path
    # 1) Import two minimal materials via public API
    pytest.importorskip("ase")
    from ase import Atoms
    atoms = Atoms("H", positions=[[0, 0, 0]], cell=[[3, 0, 0], [0, 3, 0], [0, 0, 3]], pbc=True)
    mat_a = proj.add_material(
        Material.from_ase(atoms.copy(), name="SmokeMatA", label="SmokeMatA")
    )
    mat_b = proj.add_material(
        Material.from_ase(atoms.copy(), name="SmokeMatB", label="SmokeMatB")
    )

    assert getattr(mat_a, "id_short", None) is not None
    assert getattr(mat_b, "id_short", None) is not None

    # 2) Generate surfaces for each material
    slabs_a = proj.generate_surfaces(mat_a, millers=[(1, 0, 0)], layers=1, vacuum=10.0)
    slabs_b = proj.generate_surfaces(mat_b, millers=[(1, 0, 0)], layers=1, vacuum=10.0)

    assert isinstance(slabs_a, list) and slabs_a
    assert isinstance(slabs_b, list) and slabs_b

    # The generated project-backed surfaces are the canonical search inputs.
    surf_a = slabs_a[0]
    surf_b = slabs_b[0]

    # 3) Run the canonical project-backed named search.
    psi = proj.search_interfaces(surf_a, surf_b, name="smoke_search")
    assert not psi.empty
    # The returned object is the durable named-search view.
    status = psi.status()
    assert status["name"] == "smoke_search"
    assert status["n_candidates"] >= 1

    report = psi.validate_buildable()
    assert report.ok
    built = proj.build_interfaces(psi, top=1)
    # Project.build_interfaces returns a collection-like result supporting helper methods
    assert hasattr(built, "write_structures")
    assert len(built) == 1
    assert built[0] is not None

    # 3.a) Ensure at least one candidate row has authoritative prototype linkage
    cand_rows = psi.candidates().to_rows(view="all")
    assert any(r.get("project_prototype_uid") or r.get("project_prototype_id") for r in cand_rows), "No authoritative prototype linkage present in candidate rows"

    # 4) Post-build: verify built result is usable (can write structures)
    out_dir = tmp_path / "built_structures"
    written = built.write_structures(out_dir)
    assert written, "No structure files were written from the built collection"
    for p in written:
        assert (p.exists() if hasattr(p, "exists") else True)

    # Verify persistence and discoverability via public projections
    status = proj.search("smoke_search").status()
    assert status["name"] == "smoke_search"
    assert status["n_candidates"] >= 1
    assert status["n_buildable"] >= 1
    assert status["n_built_interfaces"] >= 1

    # The interfaces projection filtered by search should show the persisted build
    iface_rows = proj.interfaces().search(name="smoke_search").to_rows(view="all")
    assert iface_rows, "built interfaces for smoke_search should be discoverable via public interface query"
    assert any(r.get("search_name") == "smoke_search" for r in iface_rows)
    # Ensure at least one stable linkage is present (prototype/build/project iface id)
    assert any(
        r.get("project_interface_uid") is not None
        for r in iface_rows
    )
