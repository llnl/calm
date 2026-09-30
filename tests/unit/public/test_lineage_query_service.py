from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.queries.lineage import ProjectLineageQueryService


class _Repository:
    def __init__(self) -> None:
        self.edges = [
            SimpleNamespace(
                uid_full="edge:1",
                src_uid_full="run:search",
                dst_uid_full="proto:1",
                kind="run_to_prototype",
                payload={},
                created_at="2026-01-01T00:00:00Z",
            ),
            SimpleNamespace(
                uid_full="edge:2",
                src_uid_full="proto:1",
                dst_uid_full="interface:1",
                kind="prototype_to_interface",
                payload={},
                created_at="2026-01-02T00:00:00Z",
            ),
            SimpleNamespace(
                uid_full="edge:3",
                src_uid_full="interface:1",
                dst_uid_full="0123456789abcdef",
                kind="interface_to_followup",
                payload={},
                created_at="2026-01-03T00:00:00Z",
            ),
        ]

    def resolve_identifier(self, identifier):
        return {"p_1": "proto:1"}.get(identifier, identifier)

    def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
        del limit
        rows = self.edges
        if src is not None:
            rows = [edge for edge in rows if edge.src_uid_full == src]
        if dst is not None:
            rows = [edge for edge in rows if edge.dst_uid_full == dst]
        if kind is not None:
            rows = [edge for edge in rows if edge.kind == kind]
        return list(rows)

    def get_run(self, identifier):
        if identifier != "run:search":
            raise KeyError(identifier)
        return {"uid_full": identifier, "id_short": "r_search"}

    def get_prototype(self, identifier):
        if identifier != "proto:1":
            raise KeyError(identifier)
        return {"uid_full": identifier, "id_short": "p_1"}

    def get_interface(self, identifier):
        if identifier != "interface:1":
            raise KeyError(identifier)
        return {
            "uid_full": identifier,
            "id_short": "i_1",
            "label": "built",
        }

    def get_followup_result(self, identifier):
        if identifier != "0123456789abcdef":
            raise KeyError(identifier)
        return {"uid_full": identifier, "id_short": "f_01234567"}

    def __getattr__(self, name):
        if name.startswith("get_"):
            return lambda identifier: (_ for _ in ()).throw(KeyError(identifier))
        raise AttributeError(name)


def _service():
    return ProjectLineageQueryService(repository=_Repository())


def test_lineage_service_resolves_aliases_and_complete_graph() -> None:
    graph = _service().lineage("p_1")

    assert graph.root_uid_full == "proto:1"
    assert {node.uid_full for node in graph.nodes} == {
        "run:search",
        "proto:1",
        "interface:1",
        "0123456789abcdef",
    }
    assert graph.node("0123456789abcdef").kind == "followup_result"
    assert graph.node("0123456789abcdef").id_short == "f_01234567"
    assert [edge.kind for edge in graph.edges] == [
        "run_to_prototype",
        "prototype_to_interface",
        "interface_to_followup",
    ]


def test_lineage_service_honors_direction_depth_and_kind_filters() -> None:
    upstream = _service().lineage(
        {"project_interface_uid": "interface:1"},
        direction="upstream",
        depth=1,
    )
    assert {node.uid_full for node in upstream.nodes} == {
        "proto:1",
        "interface:1",
    }

    filtered = _service().lineage(
        "proto:1",
        direction="downstream",
        kinds={"prototype_to_interface"},
    )
    assert [edge.kind for edge in filtered.edges] == [
        "prototype_to_interface"
    ]


def test_lineage_service_rejects_invalid_selectors_and_traversal_options() -> None:
    with pytest.raises(TypeError, match="persisted object"):
        _service().lineage(object())
    with pytest.raises(ValueError, match="direction"):
        _service().lineage("proto:1", direction="sideways")
    with pytest.raises(ValueError, match="non-negative"):
        _service().lineage("proto:1", depth=-1)
    with pytest.raises(TypeError, match="collection"):
        _service().lineage("proto:1", kinds="prototype_to_interface")
