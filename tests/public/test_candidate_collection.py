from __future__ import annotations

import pytest

from calm.public.collections.candidates import CandidateCollection


class Proto:
    def __init__(self, uid, n_atoms, d_cell, miller_a=None, miller_b=None):
        self._uid = uid
        self.n_atoms_interface = n_atoms
        self.d_cell = d_cell
        self.miller_a = miller_a
        self.miller_b = miller_b

    def to_dict(self):
        return {
            "uid": self._uid,
            "n_atoms_interface": self.n_atoms_interface,
            "d_cell": self.d_cell,
            "miller_a": self.miller_a,
            "miller_b": self.miller_b,
        }


def test_pareto_selection_basic():
    # Points: (n_atoms, d_cell)
    p1 = Proto("p1", 100, 0.02)
    p2 = Proto("p2", 200, 0.01)
    p3 = Proto("p3", 150, 0.03)

    coll = CandidateCollection(prototypes=[p1, p2, p3])
    pareto_coll = coll.pareto()
    rows = pareto_coll.to_rows(view="summary")
    ids = {r.get("uid") or r.get("candidate_id") for r in rows}
    # p1 and p2 are non-dominated; p3 dominated
    assert "p1" in ids and "p2" in ids and "p3" not in ids


def test_miller_pair_filter():
    a = (1, 0, 0)
    b = (0, 0, 1)
    p1 = Proto("p1", 100, 0.02, miller_a=a, miller_b=b)
    p2 = Proto("p2", 120, 0.03, miller_a=a, miller_b=b)
    p3 = Proto("p3", 150, 0.01, miller_a=(1, 1, 1), miller_b=(0, 1, 0))

    coll = CandidateCollection(prototypes=[p1, p2, p3])
    sel = coll.miller_pair(a, b)
    rows = sel.to_rows()
    ids = {r.get("uid") or r.get("candidate_id") for r in rows}
    assert ids == {"p1", "p2"}


def test_select_n_per_pair_and_pareto():
    # Create 4 per pair; ensure select picks n_per_pair per pair after pareto filtering
    pair1 = ((1, 0, 0), (0, 0, 1))
    pair2 = ((1, 1, 1), (0, 1, 0))
    protos = []
    # pair1: produce varying scores so pareto may keep some
    protos.extend([Proto(f"p1_{i}", 50 + i * 10, 0.02 + i * 0.001, miller_a=pair1[0], miller_b=pair1[1]) for i in range(4)])
    protos.extend([Proto(f"p2_{i}", 100 + i * 5, 0.03 + i * 0.001, miller_a=pair2[0], miller_b=pair2[1]) for i in range(4)])

    coll = CandidateCollection(prototypes=protos)
    selected = coll.select(n_per_pair=2, pareto=True)
    # Ensure at most 4 total
    assert len(selected.to_rows()) <= 4


def test_candidate_collection_does_not_execute_build_workflows() -> None:
    assert not hasattr(CandidateCollection, "_build_all")


class RecordingCandidateRepository:
    def __init__(self):
        self.search_names = []

    def list_candidates(self, *, search_name=None):
        self.search_names.append(search_name)
        return [
            {
                "candidate_id": "C_scoped",
                "rank": 41,
                "n_atoms_estimate": 2,
                "d_cell": 0.01,
                "search_name": search_name,
                "authority": "authoritative",
            }
        ]


def test_search_scope_is_applied_at_repository_boundary():
    repo = RecordingCandidateRepository()

    rows = CandidateCollection(repo=repo).search("named_search").to_rows(view="all")

    assert repo.search_names == ["named_search"]
    assert len(rows) == 1
    assert rows[0]["search_name"] == "named_search"
    # The owning search assigns candidate display identity. Query scoping and
    # filtering must not renumber candidates within a derived collection.
    assert rows[0]["candidate_id"] == "C_scoped"
    assert rows[0]["rank"] == 41


def test_miller_pair_rejects_malformed_candidate_state() -> None:
    candidate = Proto(
        "bad",
        100,
        0.02,
        miller_a=None,
        miller_b=(0, 0, 1),
    )

    with pytest.raises(ValueError, match="Miller indices"):
        CandidateCollection(prototypes=[candidate]).miller_pair(
            (1, 0, 0),
            (0, 0, 1),
        )


def test_select_top_rejects_malformed_ranking_metric() -> None:
    candidate = Proto("bad", 100, "not-a-number")

    with pytest.raises(ValueError, match="ranking metric"):
        CandidateCollection(prototypes=[candidate]).select_top(1, by="d_cell")
