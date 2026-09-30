from __future__ import annotations

import pytest

from calm.analysis.pareto import (
    STRAIN_SIZE_D_CELL_DECIMALS,
    STRAIN_SIZE_PARETO_POLICY,
    canonical_d_cell_key,
    strain_size_pareto,
)


def test_authoritative_policy_uses_atom_count_not_interface_area() -> None:
    points = [
        {"uid": "P1", "atoms": 100, "d_cell": 0.1, "area": 1.0},
        {"uid": "P2", "atoms": 50, "d_cell": 0.2, "area": 2.0},
    ]

    result = strain_size_pareto(
        points,
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
    )

    assert result.policy == STRAIN_SIZE_PARETO_POLICY
    assert result.front_ids == ("P2", "P1")
    assert result.mask.tolist() == [True, True]


def test_equal_objective_pairs_do_not_dominate_each_other() -> None:
    points = [
        {"uid": "A", "atoms": 10, "d_cell": 0.1},
        {"uid": "B", "atoms": 10, "d_cell": 0.1},
        {"uid": "C", "atoms": 11, "d_cell": 0.2},
    ]

    result = strain_size_pareto(
        points,
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
    )

    assert result.front_ids == ("A", "B")
    assert result.mask.tolist() == [True, True, False]


def test_quantized_mismatch_key_is_transitive_and_boundary_defined() -> None:
    assert STRAIN_SIZE_D_CELL_DECIMALS == 12
    assert canonical_d_cell_key(0.1 + 4.0e-13) == canonical_d_cell_key(0.1)
    assert canonical_d_cell_key(0.1 + 6.0e-13) == canonical_d_cell_key(0.100000000001)
    assert canonical_d_cell_key(0.1 + 6.0e-13) > canonical_d_cell_key(0.1)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_quantized_mismatch_key_rejects_invalid_values(bad: float) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        canonical_d_cell_key(bad)


def test_membership_and_front_order_are_input_order_invariant() -> None:
    points = [
        {"uid": "B", "atoms": 20, "d_cell": 0.1},
        {"uid": "A", "atoms": 10, "d_cell": 0.2},
        {"uid": "D", "atoms": 30, "d_cell": 0.3},
        {"uid": "C", "atoms": 10, "d_cell": 0.2},
    ]
    reversed_points = list(reversed(points))

    result = strain_size_pareto(
        points,
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
    )
    reversed_result = strain_size_pareto(
        reversed_points,
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
    )

    assert result.front_ids == ("A", "C", "B")
    assert reversed_result.front_ids == result.front_ids


def test_atom_count_accepts_integer_valued_reals_only() -> None:
    result = strain_size_pareto(
        [{"uid": "A", "atoms": 10.0, "d_cell": 0.1}],
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
    )
    assert result.front_ids == ("A",)
    assert result.population_size == 1

    with pytest.raises(TypeError, match="exact non-negative integer"):
        strain_size_pareto(
            [{"uid": "A", "atoms": 10.5, "d_cell": 0.1}],
            atom_count="atoms",
            d_cell="d_cell",
            ids="uid",
        )


def test_authoritative_metadata_requires_complete_current_contract() -> None:
    from calm.analysis.pareto import (
        authoritative_pareto_metadata,
        is_authoritative_pareto_metadata,
        is_strain_size_pareto_metadata,
        strain_size_pareto_metadata,
    )

    metadata = authoritative_pareto_metadata(
        is_member=True,
        rank=0,
        population_size=2,
        d_cell_key=100,
    )
    assert is_authoritative_pareto_metadata(metadata)

    malformed = dict(metadata)
    malformed["population_scope"] = "current_subset"
    assert not is_authoritative_pareto_metadata(malformed)
    assert is_strain_size_pareto_metadata(malformed)

    alternative = strain_size_pareto_metadata(
        policy="current_collection_strain_size_pareto",
        population_scope="current_collection_population",
        is_member=True,
        rank=0,
        population_size=1,
        d_cell_key=100,
    )
    assert is_strain_size_pareto_metadata(alternative)
    assert not is_authoritative_pareto_metadata(alternative)


def test_explicit_alternative_policy_and_scope_are_preserved() -> None:
    result = strain_size_pareto(
        [{"uid": "A", "atoms": 10, "d_cell": 0.1}],
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
        policy="aggregate_selected_runs_strain_size_pareto",
        population_scope="selected_runs_filtered_population",
    )

    assert result.policy == "aggregate_selected_runs_strain_size_pareto"
    assert result.population_scope == "selected_runs_filtered_population"


def test_sorted_front_matches_independent_pairwise_definition() -> None:
    import random

    generator = random.Random(17)
    points = [
        {
            "uid": f"P{index}",
            "atoms": generator.randrange(1, 20),
            "d_cell": generator.randrange(0, 20) / 100.0,
        }
        for index in range(100)
    ]
    result = strain_size_pareto(
        points,
        atom_count="atoms",
        d_cell="d_cell",
        ids="uid",
    )

    expected = []
    for index, point in enumerate(points):
        dominated = any(
            other_index != index
            and other["atoms"] <= point["atoms"]
            and canonical_d_cell_key(other["d_cell"])
            <= canonical_d_cell_key(point["d_cell"])
            and (
                other["atoms"] < point["atoms"]
                or canonical_d_cell_key(other["d_cell"])
                < canonical_d_cell_key(point["d_cell"])
            )
            for other_index, other in enumerate(points)
        )
        expected.append(not dominated)

    assert result.mask.tolist() == expected
