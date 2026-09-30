"""Corrected exact oracle for coupled matching of equal square lattices."""

from __future__ import annotations

from reference.coupled_match_reference import (
    FULL_D4_DISCOVERY_BY_INDEX,
    FULL_SQUARE_GROUP,
    IDENTITY_PAIR_KEY_FULL,
    PROPER_SQUARE_GROUP,
    SIGMA5_PAIR_KEY_FULL,
    SIGMA5_PAIR_KEYS_PROPER,
    cumulative_equal_square_class_inventory,
    equal_square_index_oracle,
)


def test_equal_square_index5_stage_counts_and_exact_classes() -> None:
    oracle = equal_square_index_oracle(5)

    assert len(oracle.hnfs) == 6
    assert oracle.raw_member_pairs == 36
    assert len(oracle.surface_orbits) == 3
    assert [len(members) for _key, members in oracle.surface_orbits] == [2, 2, 2]
    assert oracle.orbit_pair_schedules == 9
    assert oracle.shape_compatible_orbit_pairs == 3
    assert oracle.member_pairs_expanded == 12
    assert oracle.correspondence_states == 32
    assert oracle.full_pair_keys == {
        IDENTITY_PAIR_KEY_FULL,
        SIGMA5_PAIR_KEY_FULL,
    }
    assert oracle.proper_pair_keys == {
        IDENTITY_PAIR_KEY_FULL,
        *SIGMA5_PAIR_KEYS_PROPER,
    }


def test_equal_square_index5_oracle_is_independent_of_enumeration_order() -> None:
    forward = equal_square_index_oracle(5)
    reversed_everything = equal_square_index_oracle(
        5,
        hnf_order="reverse",
        comparison_group=tuple(reversed(FULL_SQUARE_GROUP)),
        full_pair_group=tuple(reversed(FULL_SQUARE_GROUP)),
        proper_pair_group=tuple(reversed(PROPER_SQUARE_GROUP)),
    )

    assert reversed_everything.raw_member_pairs == forward.raw_member_pairs
    assert reversed_everything.surface_orbits == forward.surface_orbits
    assert (
        reversed_everything.shape_compatible_orbit_pairs
        == forward.shape_compatible_orbit_pairs
    )
    assert reversed_everything.member_pairs_expanded == forward.member_pairs_expanded
    assert reversed_everything.correspondence_states == forward.correspondence_states
    assert reversed_everything.full_pair_keys == forward.full_pair_keys
    assert reversed_everything.proper_pair_keys == forward.proper_pair_keys


def test_full_d4_cumulative_inventory_through_index30_is_exact_and_monotone() -> None:
    inventory = cumulative_equal_square_class_inventory(30, pair_symmetry="full")

    expected_first_discovery = tuple(
        (key, index) for index, key in FULL_D4_DISCOVERY_BY_INDEX
    )
    assert inventory.first_discovery == expected_first_discovery
    assert inventory.key_sets_by_bound[4] == {
        IDENTITY_PAIR_KEY_FULL,
        SIGMA5_PAIR_KEY_FULL,
    }
    assert inventory.key_sets_by_bound[-1] == {
        key for _index, key in FULL_D4_DISCOVERY_BY_INDEX
    }
    for smaller, larger in zip(
        inventory.key_sets_by_bound,
        inventory.key_sets_by_bound[1:],
    ):
        assert smaller <= larger

    repeats = dict(inventory.repeat_indices_by_key)
    assert 1 in repeats[SIGMA5_PAIR_KEY_FULL]
    assert 5 in repeats[SIGMA5_PAIR_KEY_FULL]
    assert 6 in repeats[SIGMA5_PAIR_KEY_FULL]


def test_cumulative_inventory_is_independent_of_hnf_and_group_order() -> None:
    reference = cumulative_equal_square_class_inventory(30, pair_symmetry="full")
    reordered = cumulative_equal_square_class_inventory(
        30,
        pair_symmetry="full",
        hnf_order="reverse",
        comparison_group=tuple(reversed(FULL_SQUARE_GROUP)),
        pair_group=tuple(reversed(FULL_SQUARE_GROUP)),
    )

    assert reordered.first_discovery == reference.first_discovery
    assert reordered.key_sets_by_bound == reference.key_sets_by_bound
    assert reordered.repeat_indices_by_key == reference.repeat_indices_by_key
