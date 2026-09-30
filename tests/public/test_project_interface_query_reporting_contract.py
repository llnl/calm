"""Public authoritative query contract tests for built interfaces."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.records.interfaces import InterfaceModel
from calm.public.inputs.settings import BuildSettings
from slab_record_fixtures import current_atoms


_SEARCH_NAME = "LiF_Li2O_111_screen"


def _open_project_with_candidate(
    tmp_path,
    *,
    prototype_graph_factory,
    prototype_payload_factory,
):
    payload = prototype_payload_factory(include_supercells=True)
    payload["metrics"].update(
        {
            "match_score": 0.1,
            "d_cell": 0.02,
            "n_atoms_interface": 96,
            "interface_area_A2": 42.5,
        }
    )
    atoms = current_atoms()
    prototype_graph_factory(
        slab_a_payload={"atoms": atoms},
        slab_b_payload={"atoms": atoms},
        run_type="prototype_search",
        run_status="done",
        search_name=_SEARCH_NAME,
        run_spec={
            "surface_a": {
                "material": "LiF",
                "miller": [1, 1, 1],
                "termination": "LiF(111)",
                "termination_shift": 0,
            },
            "surface_b": {
                "material": "Li2O",
                "miller": [1, 1, 1],
                "termination": "Li2O(111)",
                "termination_shift": 0,
            },
        },
        prototype_payload=payload,
    )

    from calm.public.project import open_project

    project = open_project(str(tmp_path), summarize=False)
    candidates = project.search(_SEARCH_NAME).candidates()
    assert len(candidates) == 1
    return project, candidates[0]


def _interface_model(candidate, current_atoms_payload_factory) -> InterfaceModel:
    atoms = current_atoms_payload_factory(
        cell=((41.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 3.0)),
    )
    internal = SimpleNamespace(
        atoms=atoms,
        build_uid="build:test:0",
        prototype_uid=candidate.project_prototype_uid,
        area_A2=42.5,
    )
    settings = BuildSettings(gap=2.25, vacuum=17.5, translation=(0.25, 0.75))
    return InterfaceModel(
        internal,
        candidate=candidate.to_dict(),
        build_settings=settings,
    )


def _persist_interface(
    tmp_path,
    *,
    prototype_graph_factory,
    prototype_payload_factory,
    current_atoms_payload_factory,
):
    project, candidate = _open_project_with_candidate(
        tmp_path,
        prototype_graph_factory=prototype_graph_factory,
        prototype_payload_factory=prototype_payload_factory,
    )
    persisted = project._saver.record_interface_model(
        _interface_model(candidate, current_atoms_payload_factory),
        name="built_interface",
    )
    return project, candidate, persisted


def test_persisted_interface_is_projected_from_authoritative_records(
    tmp_path,
    prototype_graph_factory,
    prototype_payload_factory,
    current_atoms_payload_factory,
):
    project, candidate, persisted = _persist_interface(
        tmp_path,
        prototype_graph_factory=prototype_graph_factory,
        prototype_payload_factory=prototype_payload_factory,
        current_atoms_payload_factory=current_atoms_payload_factory,
    )

    assert persisted.uid_full
    assert persisted.id_short
    assert not hasattr(project, "_public_records")

    rows = project.interfaces().to_rows(view="all")

    assert len(rows) == 1
    row = rows[0]
    assert row["uid_full"] == persisted.uid_full
    assert row["id_short"] == persisted.id_short
    assert row["interface_id"] == persisted.id_short
    assert row["name"] == "built_interface"
    assert row["stage"] == "built"
    assert row["candidate_id"] == "C0000"
    assert row["candidate_uid"] == candidate.project_prototype_uid
    assert row["search_id"] == _SEARCH_NAME
    assert row["search_name"] == _SEARCH_NAME
    assert row["material_a"] == "LiF"
    assert row["material_b"] == "Li2O"
    assert row["n_atoms_estimate"] == 96
    assert row["area_A2"] == pytest.approx(42.5)
    assert row["gap"] == pytest.approx(2.25)
    assert row["vacuum"] == pytest.approx(17.5)
    assert row["translation_x"] == pytest.approx(0.25)
    assert row["translation_y"] == pytest.approx(0.75)
    assert row["has_atoms"] is True
    assert row["authority"] == "authoritative"
    assert "build_uid" not in row
    assert "tags" not in row

    construction = project.interfaces().to_rows(view="construction")[0]
    atoms = project.interface_atoms(persisted.uid_full)
    if hasattr(atoms, "get_atomic_numbers"):
        expected_n_atoms = len(atoms)
    else:
        expected_n_atoms = len(atoms["numbers"])
    assert construction["n_atoms"] == expected_n_atoms
    assert construction["area_A2"] == pytest.approx(41.0)
    assert construction["prototype_area_A2"] == pytest.approx(42.5)

    filtered = (
        project.interfaces()
        .search(_SEARCH_NAME)
        .candidate("C0000")
        .materials("LiF")
        .stage("built")
    )
    assert len(filtered.to_rows(view="all")) == 1


def test_interface_query_ignores_retired_sidecar_file(
    tmp_path,
    prototype_graph_factory,
    prototype_payload_factory,
    current_atoms_payload_factory,
):
    _project, candidate, persisted = _persist_interface(
        tmp_path,
        prototype_graph_factory=prototype_graph_factory,
        prototype_payload_factory=prototype_payload_factory,
        current_atoms_payload_factory=current_atoms_payload_factory,
    )
    legacy = tmp_path / "calm-public-records.json"
    assert not legacy.exists()
    legacy.write_text(
        '{"schema_version": 6, "interfaces": [{"name": "wrong"}]}',
        encoding="utf-8",
    )

    from calm.public.project import open_project

    reopened = open_project(str(tmp_path), summarize=False)
    rows = reopened.interfaces().candidate("C0000").to_rows(view="all")
    assert len(rows) == 1
    assert rows[0]["interface_id"] == persisted.id_short
    assert rows[0]["name"] == "built_interface"
    assert rows[0]["search_id"] == _SEARCH_NAME
    assert rows[0]["n_atoms_estimate"] == 96


def test_interface_collection_writes_tables_and_plots(
    tmp_path,
    prototype_graph_factory,
    prototype_payload_factory,
    current_atoms_payload_factory,
):
    pytest.importorskip("matplotlib")

    project, _candidate, _persisted = _persist_interface(
        tmp_path,
        prototype_graph_factory=prototype_graph_factory,
        prototype_payload_factory=prototype_payload_factory,
        current_atoms_payload_factory=current_atoms_payload_factory,
    )

    table_path = tmp_path / "tables" / "interfaces.csv"
    plot_path = tmp_path / "figures" / "interface_build_summary.png"

    project.interfaces().write_table(table_path, view="all")
    fig, ax = project.interfaces().plot_build_summary(save=plot_path)

    assert table_path.exists()
    assert "interface_id" in table_path.read_text(encoding="utf-8")
    assert plot_path.exists()
    assert fig is not None
    assert ax is not None
