from pathlib import Path


def test_candidate_collection_authoritative_validation_ok(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
):
    payload = hydrogen_atoms_payload_factory()
    prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    from calm.public.project import open_project

    proj = open_project(str(tmp_path))

    coll = proj.candidates()
    report = coll.validate_buildable()
    assert report.n_candidates == 1
    assert report.n_buildable == 1
    assert report.ok


def test_candidate_collection_reports_authoritative_graph_issue(
    tmp_path: Path,
    prototype_graph_factory,
    prototype_payload_factory,
):
    prototype_graph_factory(
        slab_a_uid_full="slab:missing",
        create_slab_a=False,
        slab_b_payload={},
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    from calm.public.project import open_project

    proj = open_project(str(tmp_path))
    report = proj.candidates().validate_buildable()

    assert report.n_candidates == 1
    assert report.n_buildable == 0
    assert not report.ok
    assert any("slab" in issue.message.lower() for issue in report.issues)
