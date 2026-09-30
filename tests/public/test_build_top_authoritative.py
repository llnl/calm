from pathlib import Path


def test_build_top_uses_authoritative_builder(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
):
    payload = hydrogen_atoms_payload_factory()
    prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        run_type="prototype_search",
        search_name="s1",
        prototype_payload=prototype_payload_factory(
            include_supercells=True,
        ),
    )

    from calm.public.project import open_project

    proj = open_project(str(tmp_path))
    psi = proj.search("s1")
    report = psi.validate_buildable()
    assert report.ok
    built = proj.build_interfaces("s1", top=1)
    # Project.build_interfaces returns a collection-like object with one result
    assert len(built) == 1
