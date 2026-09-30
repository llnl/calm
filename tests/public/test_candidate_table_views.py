"""Shared candidate view contracts for persisted and in-memory results."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    STRAIN_SIZE_PARETO_VERSION,
    canonical_d_cell_key,
)
from calm.public.collections.candidates import CandidateCollection
from calm.public.records.candidate_views import (
    CANDIDATE_PROVENANCE_COLUMNS,
    CANDIDATE_STRAIN_COLUMNS,
    CANDIDATE_SUMMARY_COLUMNS,
)
from calm.public.records.interfaces import InterfaceCandidate, InterfaceSearchResult


def _row() -> dict[str, object]:
    return {
        "rank": 0,
        "candidate_id": "C0000",
        "candidate_uid": "proto:0",
        "prototype_uid": "proto:0",
        "project_prototype_uid": "proto:0",
        "search_id": "search:0",
        "search_name": "named_search",
        "score": 0.2,
        "d_cell": 0.1,
        "d_area": 0.05,
        "d_shape": 0.03,
        "max_principal_strain": 0.02,
        "n_atoms_estimate": 20,
        "is_pareto": True,
        "pareto_rank": 0,
        "pareto_policy": STRAIN_SIZE_PARETO_POLICY,
        "pareto_policy_version": STRAIN_SIZE_PARETO_VERSION,
        "pareto_population_scope": STRAIN_SIZE_PARETO_POPULATION_SCOPE,
        "pareto_population_size": 1,
        "pareto_d_cell_key": canonical_d_cell_key(0.1),
        "authority": "authoritative",
    }


def _owners():
    row = _row()
    return (
        CandidateCollection(items=[row]),
        InterfaceSearchResult(
            request=None,
            candidates=[InterfaceCandidate(**row)],
        ),
    )


def test_candidate_owners_share_exact_named_view_schemas() -> None:
    for owner in _owners():
        assert owner.available_views() == (
            "summary",
            "strain",
            "provenance",
            "all",
        )
        assert tuple(owner.to_rows()[0]) == CANDIDATE_SUMMARY_COLUMNS
        assert tuple(owner.to_rows(view="strain")[0]) == CANDIDATE_STRAIN_COLUMNS
        assert (
            tuple(owner.to_rows(view="provenance")[0])
            == CANDIDATE_PROVENANCE_COLUMNS
        )
        assert "authority" not in owner.to_rows()[0]
        assert owner.to_rows(view="provenance")[0]["authority"] == "authoritative"


def test_candidate_exports_share_the_summary_schema(tmp_path: Path) -> None:
    for index, owner in enumerate(_owners()):
        assert tuple(owner.to_dataframe().columns) == CANDIDATE_SUMMARY_COLUMNS

        output = StringIO()
        owner.to_table(title="", file=output).display()
        assert [part.strip() for part in output.getvalue().splitlines()[0].split("|")] == list(
            CANDIDATE_SUMMARY_COLUMNS
        )

        path = tmp_path / f"candidate-{index}.csv"
        owner.write_table(path)
        assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(
            CANDIDATE_SUMMARY_COLUMNS
        )


def test_candidate_views_validate_names_and_empty_headers(tmp_path: Path) -> None:
    empty_owners = (
        CandidateCollection(items=[]),
        InterfaceSearchResult(request=None, candidates=[]),
    )
    for index, owner in enumerate(empty_owners):
        with pytest.raises(ValueError, match="Unknown table view 'unknown'"):
            owner.to_rows(view="unknown")

        path = tmp_path / f"empty-candidate-{index}.csv"
        owner.write_table(path)
        assert path.read_text(encoding="utf-8") == (
            ",".join(CANDIDATE_SUMMARY_COLUMNS) + "\n"
        )
