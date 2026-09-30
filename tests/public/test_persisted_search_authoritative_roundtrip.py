import pytest

pytest.importorskip("ase")

from pathlib import Path

from calm.public.project import open_project


def test_persisted_search_authority_roundtrip(tmp_path: Path):
    # Public-only roundtrip: no raw DB seeding or _public_records mutation
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()

    proj = open_project(str(proj_dir))

    # Create two minimal materials and save
    from ase import Atoms
    from calm import Material

    atoms = Atoms("H", positions=[[0, 0, 0]], cell=[[3, 0, 0], [0, 3, 0], [0, 0, 3]], pbc=True)
    m1 = Material.from_ase(atoms, name="A")
    m2 = Material.from_ase(atoms, name="B")

    # Persist materials via public API
    a = proj.add_material(m1, name="A_raw")
    b = proj.add_material(m2, name="B_raw")

    # Generate surfaces (use default layers small to be fast)
    slabs_a = proj.generate_surfaces(a, millers=[(1, 0, 0)], layers=1, vacuum=10.0)
    slabs_b = proj.generate_surfaces(b, millers=[(1, 0, 0)], layers=1, vacuum=10.0)
    assert slabs_a and slabs_b

    # Run a named search directly from the canonical generated-surface records.
    name = "roundtrip_search"
    search = proj.search_interfaces(slabs_a[0], slabs_b[0], name=name)
    assert search.name == name
    live_audit = search.enumeration_audit()
    assert live_audit.k_max >= 1
    assert live_audit.totals["pairs"]["candidates_admitted"] >= 1

    # Search-only workflows must not create a reporting sidecar. Reopening must
    # therefore recover the search entirely from authoritative database state.
    assert not (proj_dir / "calm-public-records.json").exists()

    # Reopen project and ensure persisted search is database-authoritative.
    proj2 = open_project(str(proj_dir))
    psi = proj2.search(name)
    st = psi.status()
    assert st["n_candidates"] >= 1
    persisted_audit = psi.enumeration_audit()
    assert persisted_audit.to_dict() == live_audit.to_dict()

    # Buildability summary should be available (non-throwing)
    summary = psi.buildability_summary()
    # Project.build_interfaces should either build or raise with a clear error
    try:
        built = proj2.build_interfaces(name, top=1, name_prefix="rt")
        # If built, ensure collection-like features exist
        assert hasattr(built, "write_structures") or isinstance(built, list)
    except RuntimeError as e:
        # If aborted, ensure error message refers to missing authoritative linkage
        assert "authoritative" in str(e) or "persist" in str(e)
