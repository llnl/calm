from types import SimpleNamespace

from pathlib import Path

from calm.public.project import Project
from slab_record_fixtures import current_atoms, current_slab_payload


class QueryStub:
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
            uid_full="bulk:m", id_short="b_m", label="M_opt", calculator=None
        )

    def get_slab(self, sid):
        for s in self._slabs:
            if sid in {
                getattr(s, "id_short", None),
                getattr(s, "uid_full", None),
                getattr(s, "id", None),
            }:
                return s
        raise KeyError(sid)


class WorkspaceStub(QueryStub):
    pass


def _make_slabs():
    complete = SimpleNamespace(
        uid_full="slab:complete",
        id_short="s_complete",
        label="M_opt-100",
        material="M_opt",
        bulk_uid_full="bulk:m",
        bulk_id_short="b_m",
        miller=(1, 0, 0),
        payload=current_slab_payload(
            bulk_uid_full="bulk:m",
            atoms=current_atoms(),
            label="T",
            top="T",
            bottom="T",
        ),
    )
    incomplete = SimpleNamespace(
        uid_full="slab:incomplete",
        id_short="s_incomplete",
        label="M_opt-100",
        material="M_opt",
        bulk_uid_full="bulk:m",
        bulk_id_short="b_m",
        miller=(1, 0, 0),
        payload=current_slab_payload(bulk_uid_full="bulk:m"),
    )
    return [complete, incomplete]


def test_surfaces_include_empty_and_default_filters(tmp_path: Path):
    slabs = _make_slabs()
    ws = WorkspaceStub(slabs)
    project = Project(ws, path=tmp_path / "example.calm")

    # Default surfaces() should return only usable surfaces (the complete one)
    rows_default = project.surfaces().to_rows(view="all")
    assert any(r.get("id_short") == "s_complete" for r in rows_default)
    assert not any(r.get("id_short") == "s_incomplete" for r in rows_default)

    # include_empty=True should expose both
    rows_all = project.surfaces(include_empty=True).to_rows(view="all")
    ids = {r.get("id_short") for r in rows_all}
    assert "s_complete" in ids and "s_incomplete" in ids


def test_project_surface_prefers_usable(tmp_path: Path):
    slabs = _make_slabs()
    ws = WorkspaceStub(slabs)
    project = Project(ws, path=tmp_path / "example.calm")

    surf = project.surface(material="M_opt", miller=(1, 0, 0))
    # GeneratedSurface.from_workspace should return the complete slab object
    assert getattr(surf, "id_short", None) == "s_complete"
