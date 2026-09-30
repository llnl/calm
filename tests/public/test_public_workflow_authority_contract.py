from pathlib import Path

import pytest

from calm.analysis.pareto import strain_size_pareto_metadata
from slab_record_fixtures import current_atoms


def test_public_workflow_authority_contract(
    tmp_path: Path,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    payload = prototype_payload_factory(include_supercells=True)
    payload["pareto"] = strain_size_pareto_metadata(
        policy="current_collection_strain_size_pareto",
        population_scope="current_collection_population",
        is_member=True,
        rank=0,
        population_size=1,
        d_cell_key=0,
    )
    atoms = current_atoms()
    prototype_graph_factory(
        slab_a_payload={"atoms": atoms},
        slab_b_payload={"atoms": atoms},
        prototype_payload=payload,
    )

    from calm.public.project import open_project

    proj = open_project(str(tmp_path))
    assert not hasattr(proj, "_public_records")
    assert not (tmp_path / "calm-public-records.json").exists()

    rows = proj.candidates().to_rows(view="all")
    assert len(rows) == 1
    assert rows[0]["project_prototype_uid"] == persisted_test_uid(
        "prototype",
        "proto:x",
    )
    assert all(row.get("authority") == "authoritative" for row in rows)

    report = proj.candidates().validate_buildable()
    assert report.n_candidates >= 1
    assert report.n_buildable >= 1


def test_authoritative_run_name_has_no_sidecar_alias_channel(
    tmp_path: Path,
    prototype_graph_factory,
    prototype_payload_factory,
):
    prototype_graph_factory(
        run_type="prototype_search",
        search_name="authoritative_search",
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    from calm.public.project import open_project

    reopened = open_project(str(tmp_path), summarize=False)
    assert not hasattr(reopened, "_public_records")
    assert not (tmp_path / "calm-public-records.json").exists()
    assert reopened.search("authoritative_search").name == "authoritative_search"
    assert len(reopened.search("authoritative_search").candidates()) == 1

    with pytest.raises(KeyError, match="No persisted search matches"):
        reopened.search("sidecar_alias")


def test_retired_sidecar_file_cannot_override_search_lookup_and_membership(
    tmp_path: Path,
    prototype_graph_factory,
    prototype_payload_factory,
):
    prototype_graph_factory(
        run_type="prototype_search",
        search_name="durable_search",
        run_status="done",
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    # A stale file from the retired reporting subsystem is ordinary inert data.
    legacy = tmp_path / "calm-public-records.json"
    legacy.write_text(
        '{"schema_version": 6, "searches": [{"name": "wrong_sidecar_name"}]}',
        encoding="utf-8",
    )

    from calm.public.project import open_project

    project = open_project(str(tmp_path), summarize=False)
    search = project.search("durable_search")
    assert search.run_status == "done"
    assert len(search.candidates()) == 1
    assert len(search.prototype_ids(pareto=False)) == 1

    with pytest.raises(KeyError, match="No persisted search matches"):
        project.search("wrong_sidecar_name")

    legacy.unlink()
    reopened = open_project(str(tmp_path), summarize=False)
    assert len(reopened.search("durable_search").candidates()) == 1
