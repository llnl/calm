"""Guardrails for candidate identity and public projection boundaries."""

from __future__ import annotations

from types import SimpleNamespace

from calm.public.collections.candidates import CandidateCollection
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult


class PrototypeWithDict:
    def __init__(self) -> None:
        self.uid = "proto:abc123"

    def to_dict(self, *, rank: int | None = None) -> dict[str, object]:
        row: dict[str, object] = {
            "uid": self.uid,
            "prototype_uid": self.uid,
            "candidate_id": self.uid,
            "match_score": 0.25,
            "d_cell": 0.02,
            "d_area": 0.01,
            "d_shape": 0.03,
            "n_atoms_interface": 96,
        }
        if rank is not None:
            row["rank"] = rank
        return row


def test_public_candidate_projection_separates_display_id_from_uid() -> None:
    candidate = InterfaceCandidate.from_prototype(PrototypeWithDict(), rank=3)

    row = candidate.to_dict()

    assert row["rank"] == 3
    assert row["candidate_id"] == "C0003"
    assert row["uid"] == "proto:abc123"
    assert row["candidate_uid"] == "proto:abc123"
    assert row["prototype_uid"] == "proto:abc123"
    assert "prototype" not in row


def test_public_candidate_only_projects_internal_prototype_when_requested() -> None:
    prototype = PrototypeWithDict()
    candidate = InterfaceCandidate.from_prototype(prototype, rank=0)

    assert "prototype" not in candidate.to_dict()
    assert candidate.to_dict(include_internal=True)["prototype"] is prototype


def test_explicit_public_candidate_id_and_uid_are_preserved() -> None:
    candidate = InterfaceCandidate(
        candidate_id="C0420",
        candidate_uid="proto:stable:420",
        prototype_uid="proto:stable:420",
        rank=9,
        d_cell=0.05,
        n_atoms_estimate=128,
    )

    row = candidate.to_dict()

    assert row["candidate_id"] == "C0420"
    assert row["candidate_uid"] == "proto:stable:420"
    assert row["prototype_uid"] == "proto:stable:420"
    assert row["uid"] == "proto:stable:420"


def test_candidate_collection_summary_keeps_uid_out_of_display_columns() -> None:
    collection = CandidateCollection(prototypes=[PrototypeWithDict()])

    summary_row = collection.to_rows()[0]
    full_row = collection.to_rows(view="full")[0]

    assert summary_row["candidate_id"] == "C0000"
    assert "candidate_uid" not in summary_row
    assert "prototype_uid" not in summary_row
    assert full_row["candidate_uid"] == "proto:abc123"
    assert full_row["prototype_uid"] == "proto:abc123"


def test_search_result_selection_preserves_public_candidate_identity() -> None:
    candidates = [
        InterfaceCandidate(candidate_id="C0000", candidate_uid="proto:a", rank=0, d_cell=0.01, n_atoms_estimate=64),
        InterfaceCandidate(candidate_id="C0001", candidate_uid="proto:b", rank=1, d_cell=0.02, n_atoms_estimate=128),
    ]
    result = InterfaceSearchResult(SimpleNamespace(), candidates, apply_pareto=False)

    selected = result.select(n=1)
    row = selected.to_rows(view="full")[0]

    assert row["candidate_id"] == "C0000"
    assert row["candidate_uid"] == "proto:a"
    assert row["rank"] == 0


def test_candidate_collection_filter_preserves_search_display_identity() -> None:
    rows = [
        {
            "candidate_id": f"proto:stable:{index}",
            "candidate_uid": f"proto:stable:{index}",
            "prototype_uid": f"proto:stable:{index}",
            "d_cell": d_cell,
            "n_atoms_estimate": 64 + index,
            "score": float(index),
        }
        for index, d_cell in enumerate((0.01, 0.02, 0.03, 0.04))
    ]
    candidates = CandidateCollection(prototypes=rows)

    assert [row["candidate_id"] for row in candidates.to_rows(view="full")] == [
        "C0000",
        "C0001",
        "C0002",
        "C0003",
    ]

    selected = candidates.where(d_cell=(0.03, None))
    selected_rows = selected.to_rows(view="full")

    assert [row["candidate_id"] for row in selected_rows] == ["C0002", "C0003"]
    assert [row["rank"] for row in selected_rows] == [2, 3]
    assert selected.get("C0003").candidate_uid == "proto:stable:3"
    assert selected.get(rank=2).candidate_id == "C0002"
