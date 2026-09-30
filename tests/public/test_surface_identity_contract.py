from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.errors import AmbiguousProjectQueryError
from calm.public.project import Project
from slab_record_fixtures import (
    current_atoms,
    current_slab_payload,
    current_termination_identity,
)


class _QueryStub:
    def __init__(self, slabs):
        self._slabs = list(slabs)

    def list_bulks(self, limit=1000):
        return []

    def list_slabs(self, limit=2000):
        return list(self._slabs)

    def get_bulk(self, identifier):
        if identifier != "bulk:m":
            raise KeyError(identifier)
        return SimpleNamespace(
            uid_full="bulk:m",
            id_short="b_m",
            label="M_opt",
            calculator=None,
        )

    def get_slab(self, identifier):
        for slab in self._slabs:
            if identifier in {
                getattr(slab, "id_short", None),
                getattr(slab, "uid_full", None),
            }:
                return slab
        raise KeyError(identifier)


class _WorkspaceStub(_QueryStub):
    pass


def _slab(
    *,
    uid,
    sid,
    termination,
    shift,
    material="M_opt",
    miller=(1, 0, 0),
    top=None,
    bottom=None,
):
    top = termination if top is None else top
    bottom = termination if bottom is None else bottom
    return SimpleNamespace(
        uid_full=uid,
        id_short=sid,
        bulk_uid_full="bulk:m",
        bulk_id_short="b_m",
        material=material,
        miller=miller,
        payload=current_slab_payload(
            bulk_uid_full="bulk:m",
            miller=miller,
            label=termination,
            shift=shift,
            top=top,
            bottom=bottom,
            identity=current_termination_identity(termination.lower()),
            atoms=current_atoms(),
            params={"layers": 4, "vacuum": 15.0},
            layers=4,
            vacuum_A=15.0,
        ),
    )


def _project(tmp_path):
    slabs = [
        _slab(uid="slab:o", sid="s_o", termination="O", shift=0),
        _slab(uid="slab:li", sid="s_li", termination="Li", shift=1),
    ]
    return Project(_WorkspaceStub(slabs), path=tmp_path / "surface-project.calm")


def test_surface_query_never_silently_selects_a_termination(tmp_path):
    project = _project(tmp_path)

    with pytest.raises(
        AmbiguousProjectQueryError,
        match="matched 2 persisted surfaces",
    ):
        project.surface(material="M_opt", miller=(1, 0, 0))


def test_surface_collection_filters_exact_scientific_identity(tmp_path):
    project = _project(tmp_path)

    selected = project.surfaces(
        material="M_opt",
        miller=(1, 0, 0),
        termination="o",
        termination_shift=0,
    )
    assert len(selected) == 1
    surface = selected.one()
    assert surface.uid_full == "slab:o"
    assert surface.id_short == "s_o"
    assert surface.material == "M_opt"
    assert surface.miller == (1, 0, 0)
    assert surface.termination == "O"
    assert surface.termination_shift == 0
    assert surface.bulk_uid_full == "bulk:m"
    assert surface.bulk_id_short == "b_m"
    assert surface.vacuum == 15.0
    assert surface.layers == 4
    assert surface.authority == "authoritative"

    # Termination labels and integer shifts are distinct exact selectors.
    with pytest.raises(TypeError, match="termination must be a string"):
        project.surface(
            material="M_opt",
            miller=(1, 0, 0),
            termination=1,
        )
    shifted = project.surface(
        material="M_opt",
        miller=(1, 0, 0),
        termination_shift=1,
    )
    assert shifted.uid_full == "slab:li"

    # Material selection is exact; unsafe prefix matching is not permitted.
    assert len(project.surfaces(material="M", miller=(1, 0, 0))) == 0


def test_surface_query_filters_ordered_top_and_bottom_terminations(tmp_path):
    slabs = [
        _slab(
            uid="slab:o-top",
            sid="s_o_top",
            termination="O",
            shift=1,
            top="O",
            bottom="Li₂",
        ),
        _slab(
            uid="slab:o-bottom",
            sid="s_o_bottom",
            termination="Li₂",
            shift=0,
            top="Li₂",
            bottom="O",
        ),
    ]
    project = Project(
        _WorkspaceStub(slabs),
        path=tmp_path / "oriented-termination-project.calm",
    )

    surface = project.surface(
        material="M_opt",
        miller=(1, 0, 0),
        termination_top="li₂",
        termination_bottom="o",
    )
    assert surface.uid_full == "slab:o-bottom"
    assert surface.termination == "Li₂"
    assert surface.termination_top == "Li₂"
    assert surface.termination_bottom == "O"

    selected = project.surfaces(
        material="M_opt",
        miller=(1, 0, 0),
        termination_bottom="LI₂",
    )
    assert [item.uid_full for item in selected] == ["slab:o-top"]

    with pytest.raises(TypeError, match="termination_bottom must be a string"):
        project.surface(
            material="M_opt",
            miller=(1, 0, 0),
            termination_bottom=1,
        )


def test_surface_can_be_resolved_by_stable_uid_or_short_id(tmp_path):
    project = _project(tmp_path)

    assert project.surface("slab:o").id_short == "s_o"
    assert project.surface("s_li").uid_full == "slab:li"

    with pytest.raises(TypeError, match="either id_or_name"):
        project.surface("s_o", termination="O")
    with pytest.raises(TypeError, match="either id_or_name"):
        project.surface("s_o", termination_bottom="O")


def test_generated_surface_to_surface_preserves_persisted_identity(tmp_path):
    generated = _project(tmp_path).surface("s_o")
    request = generated.to_surface()

    assert request.project_slab_uid_full == "slab:o"
    assert request.project_slab_id_short == "s_o"
    assert request.termination == "O"
    assert request.termination_shift == 0
    assert request.termination_identity == current_termination_identity("o")["primary"]
    assert request.termination_identity_version == 2


def test_current_surface_projection_does_not_infer_termination_from_coordinates(
    monkeypatch,
):
    from calm.public.projections.slab import normalize_slab_row

    def _unexpected(*args, **kwargs):
        raise AssertionError("coordinate-based termination inference must not run")

    monkeypatch.setattr(
        "calm.slab.oriented.terminations._cluster_atoms_by_z",
        _unexpected,
    )
    item = SimpleNamespace(
        uid_full="slab:current",
        id_short="s_current",
        bulk_uid_full="bulk:m",
        bulk_id_short="b_m",
        material="M_opt",
        miller=(1, 0, 0),
        payload=current_slab_payload(
            bulk_uid_full="bulk:m",
            atoms=current_atoms(),
        ),
    )

    row = normalize_slab_row(item)

    assert row["termination"] is None
    assert row["termination_top"] is None
    assert row["termination_bottom"] is None
