from __future__ import annotations

import csv
import math

import pytest

from calm.analysis.pareto import (
    authoritative_pareto_metadata,
    canonical_d_cell_key,
)
from calm.public.projections.candidate import normalize_candidate_row
from calm.public.collections.candidates import CandidateCollection
from calm.public.records.interfaces import InterfaceCandidate


def _invariant_row(
    uid: str,
    *,
    d_cell: float,
    d_area: float,
    d_shape: float,
    hencky_norm: float | None = None,
) -> dict[str, object]:
    return {
        "uid": uid,
        "candidate_uid": uid,
        "candidate_id": uid,
        "n_atoms_estimate": 10,
        "d_cell": d_cell,
        "d_area": d_area,
        "d_shape": d_shape,
        "hencky_norm": hencky_norm,
        # Simulate a row already contaminated by the retired projection alias.
        "max_principal_strain": hencky_norm,
    }


def test_candidate_to_dict_recovers_exact_maximum_from_unsigned_invariants() -> None:
    candidate = InterfaceCandidate(
        **_invariant_row(
            "candidate",
            d_cell=0.10,
            d_area=0.02,
            d_shape=0.03,
            hencky_norm=0.05,
        )
    )

    expected = (0.02 + 0.03) / (2.0 * math.sqrt(2.0))
    assert candidate.max_principal_strain == pytest.approx(expected)

    row = candidate.to_dict()

    assert row["max_principal_strain"] == pytest.approx(expected)
    assert row["strain_norm"] == pytest.approx(0.05)
    assert "eps1" not in row
    assert "eps2" not in row
    assert "isotropic_strain_signed" not in row


def test_candidate_filter_uses_maximum_principal_strain_not_total_norm() -> None:
    sqrt2 = math.sqrt(2.0)
    rows = [
        _invariant_row(
            "isotropic",
            d_cell=2.0 * sqrt2 * 0.03,
            d_area=2.0 * sqrt2 * 0.03,
            d_shape=0.0,
            hencky_norm=sqrt2 * 0.03,
        ),
        _invariant_row(
            "uniaxial",
            d_cell=0.08,
            d_area=sqrt2 * 0.04,
            d_shape=sqrt2 * 0.04,
            hencky_norm=0.04,
        ),
    ]

    selected = CandidateCollection(prototypes=rows).where(
        max_principal_strain=(None, 0.035)
    )

    assert [row["candidate_id"] for row in selected.to_rows(view="all")] == [
        "isotropic"
    ]


def test_candidate_normalizer_does_not_alias_total_norm_to_maximum() -> None:
    row = normalize_candidate_row(
        {
            "candidate_id": "norm-only",
            "strain_norm": 0.2,
            "n_atoms_estimate": 10,
        }
    )

    assert row["max_principal_strain"] is None


def test_public_plotting_uses_exact_maximum_principal_strain(monkeypatch) -> None:
    from calm.public.presentation import plotting

    captured: dict[str, object] = {}

    def fake_plot(candidates, **kwargs):
        captured["candidates"] = candidates
        captured.update(kwargs)
        return "figure", "axes"

    monkeypatch.setattr(plotting, "plot_pareto_2d", fake_plot)
    raw = _invariant_row(
        "plot",
        d_cell=0.10,
        d_area=0.02,
        d_shape=0.03,
        hencky_norm=0.05,
    )

    plotting.plot_pareto([raw], y="max_principal_strain", front=False)

    rows = captured["candidates"]
    assert isinstance(rows, list)
    expected = (0.02 + 0.03) / (2.0 * math.sqrt(2.0))
    assert rows[0]["max_principal_strain"] == pytest.approx(expected)
    assert captured["y"] == "max_principal_strain"

def test_candidate_export_uses_exact_maximum_principal_strain(tmp_path) -> None:
    raw = _invariant_row(
        "export",
        d_cell=0.10,
        d_area=0.02,
        d_shape=0.03,
        hencky_norm=0.05,
    )
    output = tmp_path / "candidates.csv"

    CandidateCollection(prototypes=[raw]).write_table(output, view="all")

    with output.open(newline="", encoding="utf-8") as handle:
        exported = next(csv.DictReader(handle))
    expected = (0.02 + 0.03) / (2.0 * math.sqrt(2.0))
    assert float(exported["max_principal_strain"]) == pytest.approx(expected)


def test_explicit_signed_pair_remains_authoritative() -> None:
    candidate = InterfaceCandidate(
        candidate_id="signed",
        n_atoms_estimate=10,
        eps1=-0.04,
        eps2=0.01,
        d_area=100.0,
        d_shape=100.0,
    )

    row = candidate.to_dict()

    assert row["eps1"] == -0.04
    assert row["eps2"] == 0.01
    assert row["max_principal_strain"] == 0.04
    assert row["isotropic_strain_signed"] == pytest.approx(-0.015)


def test_reopened_project_recovers_exact_maximum_from_persisted_invariants(
    tmp_path,
    prototype_graph_factory,
    prototype_payload_factory,
) -> None:
    from calm.public.project import open_project

    eps = 0.02633
    d_area = 2.0 * math.sqrt(2.0) * eps
    d_shape = 0.0
    d_cell = d_area
    payload = prototype_payload_factory(include_supercells=True)
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    metrics.update(
        {
            "d_cell": d_cell,
            "d_area": d_area,
            "d_shape": d_shape,
        }
    )
    payload["pareto"] = authoritative_pareto_metadata(
        is_member=True,
        rank=0,
        population_size=1,
        d_cell_key=canonical_d_cell_key(d_cell),
    )
    prototype_graph_factory(
        run_type="prototype_search",
        search_name="strain_projection",
        prototype_payload=payload,
    )

    first = open_project(tmp_path).candidates().search(
        "strain_projection"
    ).to_rows(view="all")[0]
    reopened = open_project(tmp_path).candidates().search(
        "strain_projection"
    ).to_rows(view="all")[0]

    for row in (first, reopened):
        assert row["max_principal_strain"] == pytest.approx(eps)
        assert row["strain_norm"] == pytest.approx(math.sqrt(2.0) * eps)
        assert row["eps1"] is None
        assert row["eps2"] is None
        assert row["isotropic_strain_signed"] is None
