from pathlib import Path


from calm.public.project import open_project


def test_open_project_ready_without_reporting_workflow_tables(tmp_path: Path, capsys):
    p = tmp_path / "proj_ro"
    p.mkdir()
    project = open_project(str(p), summarize=False)
    assert not hasattr(project, "_public_records")
    assert not (p / "calm-public-records.json").exists()

    _ = open_project(str(p), summarize=True)
    out = capsys.readouterr().out
    assert "reporting-only" not in out
    assert "Project ready for scientific workflows" in out


def test_open_project_warns_for_zero_buildable_search(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
):
    # Build a current authoritative search whose prototype is not buildable.
    payload = hydrogen_atoms_payload_factory()
    prototype_graph_factory(
        slab_a_uid_full="slab:missing",
        create_slab_a=False,
        slab_b_uid_full="slab:a",
        slab_b_id_short="s_a",
        slab_b_payload=payload,
        run_type="prototype_search",
        search_name="s_unbuild",
        prototype_uid_full="proto:bad",
        prototype_id_short="p_bad",
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    # Reopen with summary enabled and capture stdout
    import sys
    from io import StringIO

    old = sys.stdout
    sys.stdout = StringIO()
    try:
        _ = open_project(str(tmp_path), summarize=True)
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old

    assert "s_unbuild" in out
    assert "no buildable candidates" in out
    assert "Project opened with workflow warnings" in out


def test_open_project_ready_when_healthy(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
):
    # Seed one current authoritative search and buildable prototype.
    payload = hydrogen_atoms_payload_factory()
    prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        run_type="prototype_search",
        search_name="s_ok",
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    # Capture stdout
    import sys
    from io import StringIO

    old = sys.stdout
    sys.stdout = StringIO()
    try:
        _ = open_project(str(tmp_path), summarize=True)
        out = sys.stdout.getvalue()
    finally:
        sys.stdout = old

    assert "reporting-only" not in out
    assert "no buildable candidates" not in out
    assert "Project ready for scientific workflows" in out
