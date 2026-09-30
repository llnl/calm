from __future__ import annotations

import pandas as pd

from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult


def _make_candidate(rank=1, cid="c1", score=0.5, d_cell=0.02, n_atoms=100, k_a=1, k_b=1):
    return InterfaceCandidate(
        rank=rank,
        candidate_id=cid,
        score=score,
        d_cell=d_cell,
        d_area=0.01,
        d_shape=0.005,
        d_size=1.0,
        eps1=0.02,
        eps2=-0.01,
        max_principal_strain=0.02,
        isotropic_strain_norm=0.005,
        deviatoric_strain_norm=0.015,
        n_atoms_estimate=n_atoms,
        area=50.0,
        k_a=k_a,
        k_b=k_b,
        is_pareto=True,
    )


def test_to_rows_summary_and_strain():
    c1 = _make_candidate(rank=1, cid="c1")
    c2 = _make_candidate(rank=2, cid="c2", score=0.7, d_cell=0.05, n_atoms=200, k_a=2, k_b=2)
    result = InterfaceSearchResult(request=None, candidates=[c1, c2])

    rows = result.to_rows(view="summary")
    assert isinstance(rows, list)
    assert len(rows) == 2
    assert rows[0]["candidate_id"] == "c1"
    assert rows[1]["n_atoms_estimate"] == 200

    strain_rows = result.to_rows(view="strain")
    assert "eps1" in strain_rows[0]
    assert "max_principal_strain" in strain_rows[1]


def test_to_dataframe_and_columns():
    c1 = _make_candidate(rank=1, cid="c1")
    c2 = _make_candidate(rank=2, cid="c2")
    result = InterfaceSearchResult(request=None, candidates=[c1, c2])

    df = result.to_dataframe(view="summary")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == [
        "candidate_id",
        "d_cell",
        "d_area",
        "d_shape",
        "max_principal_strain",
        "n_atoms_estimate",
        "score",
        "is_pareto",
    ]
    assert float(df.loc[df["candidate_id"] == "c1", "d_cell"].iloc[0]) == 0.02


def test_write_table_csv(tmp_path):
    c1 = _make_candidate(rank=1, cid="c1")
    c2 = _make_candidate(rank=2, cid="c2")
    result = InterfaceSearchResult(request=None, candidates=[c1, c2])

    out = tmp_path / "candidates.csv"
    result.write_table(out, view="summary")
    assert out.exists()

    # Read back and sanity-check columns
    import csv

    with out.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["candidate_id"] == "c1"


def test_search_result_views_are_validated_and_preserve_empty_headers(tmp_path):
    result = InterfaceSearchResult(request=None, candidates=[])

    assert result.available_views() == (
        "summary",
        "strain",
        "provenance",
        "all",
    )

    import pytest

    with pytest.raises(ValueError, match="Unknown table view 'missing'"):
        result.to_rows(view="missing")

    out = tmp_path / "empty_candidates.csv"
    result.write_table(out)
    assert out.read_text(encoding="utf-8").splitlines()[0] == (
        "candidate_id,d_cell,d_area,d_shape,max_principal_strain,"
        "n_atoms_estimate,score,is_pareto"
    )
