from __future__ import annotations

from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_VERSION,
    canonical_d_cell_key,
)
from calm.public.collections.candidates import CandidateCollection
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult


def _candidate(
    uid: str,
    *,
    atoms: int,
    d_cell: float,
    is_pareto: bool,
) -> InterfaceCandidate:
    return InterfaceCandidate(
        candidate_uid=uid,
        uid=uid,
        n_atoms_estimate=atoms,
        d_cell=d_cell,
        score=0.0,
        is_pareto=is_pareto,
        pareto_policy=STRAIN_SIZE_PARETO_POLICY,
        pareto_policy_version=STRAIN_SIZE_PARETO_VERSION,
        pareto_population_scope=(
            "full_admitted_canonical_pre_rank_pre_truncation"
        ),
        pareto_population_size=3,
        pareto_d_cell_key=canonical_d_cell_key(d_cell),
    )


def test_public_result_preserves_source_membership() -> None:
    dominated = _candidate(
        "dominated",
        atoms=60,
        d_cell=0.3,
        is_pareto=False,
    )
    front = _candidate("front", atoms=50, d_cell=0.2, is_pareto=True)

    result = InterfaceSearchResult(None, [dominated, front])

    assert [candidate.is_pareto for candidate in result] == [False, True]
    assert [candidate.candidate_uid for candidate in result.pareto] == ["front"]


def test_collection_filter_does_not_promote_source_dominated_candidate() -> None:
    dominated = _candidate(
        "dominated",
        atoms=60,
        d_cell=0.3,
        is_pareto=False,
    )
    collection = CandidateCollection(prototypes=[dominated])

    assert collection.pareto().to_rows() == []


def test_global_plot_uses_authoritative_rows(monkeypatch) -> None:
    from calm.public.presentation import plotting

    rows = [
        _candidate("dominated", atoms=60, d_cell=0.3, is_pareto=False).to_dict(),
        _candidate("front", atoms=50, d_cell=0.2, is_pareto=True).to_dict(),
    ]
    captured = {}

    def fake_plot(candidates, **kwargs):
        captured["candidates"] = candidates
        captured.update(kwargs)
        return "figure", "axes"

    monkeypatch.setattr(plotting, "plot_pareto_2d", fake_plot)

    plotting.plot_pareto(rows, front="global")

    assert [row["candidate_uid"] for row in captured["pareto"]] == ["front"]


def test_global_plot_recomputes_aggregate_across_search_populations(
    monkeypatch,
) -> None:
    from calm.public.presentation import plotting

    rows = [
        _candidate("s1-small", atoms=20, d_cell=0.39, is_pareto=True).to_dict(),
        _candidate("s1-low", atoms=90, d_cell=0.075, is_pareto=True).to_dict(),
        _candidate("s2-middle", atoms=75, d_cell=0.32, is_pareto=True).to_dict(),
        _candidate("s2-dominated", atoms=100, d_cell=0.16, is_pareto=True).to_dict(),
    ]
    rows[0]["search_name"] = "search-1"
    rows[1]["search_name"] = "search-1"
    rows[2]["search_name"] = "search-2"
    rows[3]["search_name"] = "search-2"
    captured = {}

    def fake_plot(candidates, **kwargs):
        captured["candidates"] = candidates
        captured.update(kwargs)
        return "figure", "axes"

    monkeypatch.setattr(plotting, "plot_pareto_2d", fake_plot)

    plotting.plot_pareto(
        rows,
        front="global",
        group_by="search_name",
        front_scope="both",
    )

    assert [row["candidate_uid"] for row in captured["pareto"]] == [
        "s1-small",
        "s2-middle",
        "s1-low",
    ]


def test_computed_plot_requests_display_plane_front(monkeypatch) -> None:
    from calm.public.presentation import plotting

    captured = {}

    def fake_plot(candidates, **kwargs):
        captured.update(kwargs)
        return "figure", "axes"

    monkeypatch.setattr(plotting, "plot_pareto_2d", fake_plot)
    plotting.plot_pareto(
        [
            {"candidate_id": "A", "n_atoms_estimate": 10, "d_cell": 0.2},
            {"candidate_id": "B", "n_atoms_estimate": 20, "d_cell": 0.1},
        ],
        front="computed",
    )

    assert captured["pareto"] is None
    assert captured["show_front"] is True


def test_from_internal_preserves_result_level_front_provenance() -> None:
    from types import SimpleNamespace

    internal = SimpleNamespace(
        prototypes=[],
        pareto_policy=STRAIN_SIZE_PARETO_POLICY,
        pareto_policy_version=STRAIN_SIZE_PARETO_VERSION,
        pareto_population_scope=(
            "full_admitted_canonical_pre_rank_pre_truncation"
        ),
        pareto_population_size=5,
        pareto_front_uids=("proto:A", "proto:B"),
    )

    result = InterfaceSearchResult.from_internal(internal)

    assert result.metadata["pareto_policy"] == STRAIN_SIZE_PARETO_POLICY
    assert result.metadata["pareto_policy_version"] == STRAIN_SIZE_PARETO_VERSION
    assert result.metadata["pareto_population_size"] == 5
    assert result.metadata["pareto_front_uids"] == ["proto:A", "proto:B"]


def test_public_tables_include_policy_provenance() -> None:
    front = _candidate("front", atoms=50, d_cell=0.2, is_pareto=True)

    result_row = InterfaceSearchResult(None, [front]).to_rows(
        view="provenance"
    )[0]
    collection_row = CandidateCollection(prototypes=[front]).to_rows(
        view="provenance"
    )[0]

    for row in (result_row, collection_row):
        assert row["pareto_policy"] == STRAIN_SIZE_PARETO_POLICY
        assert row["pareto_policy_version"] == STRAIN_SIZE_PARETO_VERSION
        assert row["pareto_population_size"] == 3
        assert row["pareto_d_cell_key"] == canonical_d_cell_key(0.2)


def test_authoritative_collection_scope_rejects_missing_provenance() -> None:
    candidate = InterfaceCandidate(
        candidate_uid="legacy",
        uid="legacy",
        n_atoms_estimate=10,
        d_cell=0.1,
        score=0.0,
    )
    collection = CandidateCollection(prototypes=[candidate])

    import pytest

    with pytest.raises(ValueError, match="Authoritative full-population"):
        collection.pareto(scope="authoritative")


def test_computed_collection_scope_is_explicitly_current_population() -> None:
    candidates = [
        InterfaceCandidate(
            candidate_uid="A",
            uid="A",
            n_atoms_estimate=10,
            d_cell=0.2,
            score=0.0,
        ),
        InterfaceCandidate(
            candidate_uid="B",
            uid="B",
            n_atoms_estimate=20,
            d_cell=0.3,
            score=0.0,
        ),
    ]
    collection = CandidateCollection(prototypes=candidates)

    rows = collection.pareto(scope="computed").to_rows(view="provenance")
    assert [row["candidate_id"] for row in rows] == ["A"]
    assert rows[0]["pareto_policy"] == "current_collection_strain_size_pareto"
    assert rows[0]["pareto_population_size"] == 2


def test_stored_plot_requires_authoritative_provenance(monkeypatch) -> None:
    import pytest

    from calm.public.presentation import plotting

    monkeypatch.setattr(
        plotting,
        "plot_pareto_2d",
        lambda *args, **kwargs: ("figure", "axes"),
    )
    rows = [{"candidate_id": "A", "n_atoms_estimate": 10, "d_cell": 0.2}]

    with pytest.raises(ValueError, match="Authoritative stored Pareto"):
        plotting.plot_pareto(rows, front="stored")


def test_global_plot_preserves_complete_scoped_alternative(monkeypatch) -> None:
    from calm.public.presentation import plotting

    rows = [
        {
            "candidate_id": "A",
            "n_atoms_estimate": 10,
            "d_cell": 0.2,
            "is_pareto": False,
            "pareto_policy": "current_collection_strain_size_pareto",
            "pareto_policy_version": 1,
            "pareto_population_scope": "parent_collection_population",
            "pareto_population_size": 2,
            "pareto_d_cell_key": canonical_d_cell_key(0.2),
        }
    ]
    captured = {}

    def fake_plot(candidates, **kwargs):
        captured.update(kwargs)
        return "figure", "axes"

    monkeypatch.setattr(plotting, "plot_pareto_2d", fake_plot)
    plotting.plot_pareto(rows, front="global")

    assert captured["pareto"] == []


def test_current_result_marks_missing_objectives_unavailable() -> None:
    candidate = InterfaceCandidate(
        candidate_uid="incomplete",
        uid="incomplete",
        d_cell=0.1,
        score=0.0,
    )

    result = InterfaceSearchResult(None, [candidate])

    assert result.metadata["pareto_status"] == "unavailable_missing_objectives"
    assert result[0].is_pareto is None
    assert result[0].pareto_status == "unavailable_missing_objectives"


def test_collection_auto_mode_preserves_incomplete_reporting_rows() -> None:
    candidate = InterfaceCandidate(
        candidate_uid="incomplete",
        uid="incomplete",
        d_cell=0.1,
        score=0.0,
    )
    collection = CandidateCollection(prototypes=[candidate])

    rows = collection.to_rows(view="all")

    assert rows[0]["is_pareto"] is None
    assert rows[0]["pareto_status"] == "unavailable_missing_objectives"


def test_computed_collection_requires_complete_objectives() -> None:
    import pytest

    candidate = InterfaceCandidate(
        candidate_uid="incomplete",
        uid="incomplete",
        d_cell=0.1,
        score=0.0,
    )
    collection = CandidateCollection(prototypes=[candidate])

    with pytest.raises(ValueError, match="requires exact atom counts"):
        collection.pareto(scope="computed")
