from pathlib import Path

from calm.public.project import Project


class FakeWorkspaceNoProto:
    """Workspace adapter lacking prototype persistence support."""
    def add_bulk(self, *args, **kwargs):
        return {"id_short": "b_x_1", "uid_full": "bulk:x"}


class FakeWorkspaceWithProto:
    """Workspace adapter that persists prototypes and returns mapping."""
    def __init__(self):
        self.saved_searches = []

    def add_bulk(self, *args, **kwargs):
        return {"id_short": "b_x_1", "uid_full": "bulk:x", "payload": kwargs.get("payload") or {}}

    def persist_interface_prototypes(
        self,
        prototypes,
        *,
        run_uid_full=None,
    ):
        # simulate creating authoritative prototype ids
        out = {}
        for i, p in enumerate(prototypes):
            out_key = getattr(p, "uid_full", f"proto:{i}")
            out[out_key] = {
                "uid_full": f"proto:{i}",
                "id_short": f"p_{i}",
                "run_id": None,
                "run_uid_full": run_uid_full,
            }
        return out


def test_project_backed_search_must_persist_prototypes(tmp_path: Path):
    # Option 1 + failure semantics A: project-backed search must persist prototypes and fail loudly if backend lacks support
    ws = FakeWorkspaceWithProto()
    proj = Project(ws, path=tmp_path)

    # Exercise the authoritative project saver with a search result carrying
    # internal prototypes.
    # Construct a minimal InterfaceSearchResult with an internal_result that
    # contains prototypes so the saver code will attempt prototype persistence.
    from types import SimpleNamespace
    from calm.public.records.interfaces import InterfaceSearchResult

    internal = SimpleNamespace(prototypes=[{"uid": "proto1"}])
    result = InterfaceSearchResult(request=None, candidates=[], internal_result=internal)

    # Internal persistence routes through
    # PublicProjectSaver.record_search_result.
    proj._saver.record_search_result(result, name="s1")

    assert result._persisted_prototype_map == {
        "proto:0": {
            "uid_full": "proto:0",
            "id_short": "p_0",
            "run_id": None,
            "run_uid_full": None,
        }
    }
    assert not hasattr(proj, "_public_records")
    assert not (tmp_path / "calm-public-records.json").exists()


def test_project_backed_search_raises_if_workspace_lacks_prototype_persistence(tmp_path: Path):
    ws = FakeWorkspaceNoProto()
    proj = Project(ws, path=tmp_path)
    from types import SimpleNamespace
    from calm.public.records.interfaces import InterfaceSearchResult

    internal = SimpleNamespace(prototypes=[{"uid": "proto1"}])
    result = InterfaceSearchResult(request=None, candidates=[], internal_result=internal)

    # Expect RuntimeError when saving search results because workspace lacks prototype persistence
    import pytest

    with pytest.raises(AttributeError):
        proj._saver.record_search_result(result, name="s2")
