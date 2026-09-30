from __future__ import annotations

import json

import numpy as np
import pytest

from benchmarks.benchmarks.claims.dedup_comparison import (
    METHOD_METADATA,
    LedgerEntry,
    calm_stage_keys,
    cluster_interoptimus_style,
    evaluate_record_adapters,
    interoptimus_direction_signature,
    jelver_style_filter,
    ogre_style_key,
    select_intermat_paper_style,
    select_intermat_source,
    select_intermatch_style,
    zur_mcgill_descriptor_key,
)


I2 = np.eye(2, dtype=int)
SHEAR = np.array([[1, 1], [0, 1]], dtype=int)
SWAP = np.array([[0, 1], [1, 0]], dtype=int)
ROTATION_90 = np.array([[0, -1], [1, 0]], dtype=int)
REPEAT_ONE_DIRECTION = np.diag([1, 2])


def _stack(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.vstack([a, b])


def _identity_group() -> tuple[np.ndarray, ...]:
    return (I2.copy(),)


def _square_group() -> tuple[np.ndarray, ...]:
    rotations = (
        I2,
        ROTATION_90,
        ROTATION_90 @ ROTATION_90,
        ROTATION_90 @ ROTATION_90 @ ROTATION_90,
    )
    reflection = np.diag([1, -1])
    operations = {
        tuple(int(value) for value in operation.ravel()): operation
        for rotation in rotations
        for operation in (rotation, reflection @ rotation)
    }
    return tuple(operations[key] for key in sorted(operations))


def _record(
    record_id: str,
    source: np.ndarray,
    *,
    basis_a: np.ndarray | None = None,
    basis_b: np.ndarray | None = None,
    strains: tuple[float, float] | None = None,
    atom_count: int | None = None,
    source_atom_count: int | None = None,
    elastic_energy: float | None = None,
    d_cell: float | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "record_id": record_id,
        "source_pair_matrix": source.tolist(),
    }
    if basis_a is not None:
        result["source_basis_A"] = basis_a.tolist()
        result["source_gram_A"] = (basis_a.T @ basis_a).tolist()
    if basis_b is not None:
        result["source_basis_B"] = basis_b.tolist()
        result["source_gram_B"] = (basis_b.T @ basis_b).tolist()
    if strains is not None:
        result["principal_log_strains"] = list(strains)
    if atom_count is not None:
        result["atom_count"] = atom_count
    if source_atom_count is not None:
        result["source_atom_count"] = source_atom_count
    if elastic_energy is not None:
        result["elastic_energy"] = elastic_energy
    if d_cell is not None:
        result["d_cell"] = d_cell
    return result


def test_ledger_entry_parses_trace_mapping_and_copies_arrays() -> None:
    source = _stack(I2, SHEAR)
    basis_a = np.eye(2)
    mapping = {
        "audit_index": 7,
        "source_pair_matrix": source,
        "source_basis_A": basis_a,
        "source_basis_B": np.eye(2),
        "principal_log_strains": [-0.01, 0.02],
        "d_cell": 0.03,
        "atom_count": 12,
    }

    entry = LedgerEntry.from_record(mapping)
    source[0, 0] = 99
    basis_a[0, 0] = 99.0

    assert entry.record_id == "7"
    assert entry.source_pair_matrix.dtype.kind in {"i", "u"}
    assert entry.source_pair_matrix[0, 0] == 1
    assert entry.source_basis_A is not None
    assert entry.source_basis_A[0, 0] == 1.0
    assert entry.source_gram_A is not None
    assert np.array_equal(entry.source_gram_A, np.eye(2))
    json.dumps(entry.to_dict(), sort_keys=True)


@pytest.mark.parametrize(
    "source",
    [
        [[True, 0], [0, 1], [1, 0], [0, 1]],
        [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]],
        [[1, 0], [0, 0], [1, 0], [0, 1]],
    ],
)
def test_ledger_entry_rejects_nonexact_or_singular_blocks(source: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        LedgerEntry.from_record({"record_id": "bad", "source_pair_matrix": source})


def test_metadata_distinguishes_equivalence_grouping_filters_and_selectors() -> None:
    assert METHOD_METADATA["calm"].method_kind == "equivalence"
    assert METHOD_METADATA["calm"].fidelity == "implementation_exact"
    assert METHOD_METADATA["zur_mcgill_descriptor"].method_kind == "heuristic_grouping"
    assert (
        METHOD_METADATA["interoptimus_direction_signature"].fidelity
        == "source_derived_2d_analogue"
    )
    assert METHOD_METADATA["ogre_style"].fidelity == "source_derived_2d_analogue"
    assert METHOD_METADATA["jelver_style"].method_kind == "filter"
    assert METHOD_METADATA["intermat_source"].method_kind == "selector"
    assert METHOD_METADATA["intermat_source"].fidelity == "source_derived_2d_analogue"
    assert "90d7d7ebe06b946ec4e8514b2f90156e86b21c87" in (
        METHOD_METADATA["intermat_source"].source_revision
    )
    assert any(
        "not represented as an InterMat dependency pin" in deviation
        for deviation in METHOD_METADATA["intermat_source"].documented_deviations
    )
    assert METHOD_METADATA["intermat_paper_style"].method_kind == "selector"
    assert METHOD_METADATA["intermatch_style"].method_kind == "selector"


def test_calm_stage_keys_remove_common_repetition_and_basis_relabelling() -> None:
    source = _stack(I2, SHEAR)
    relabelling = np.array([[2, 1], [1, 1]], dtype=int)
    repeated = source @ REPEAT_ONE_DIRECTION
    group = _identity_group()

    baseline = calm_stage_keys(
        _record("baseline", source),
        point_group_A=group,
        point_group_B=group,
    )
    relabelled = calm_stage_keys(
        _record("relabelled", source @ relabelling),
        point_group_A=group,
        point_group_B=group,
    )
    repeated_result = calm_stage_keys(
        _record("repeated", repeated),
        point_group_A=group,
        point_group_B=group,
    )

    assert baseline.class_key == relabelled.class_key == repeated_result.class_key
    assert baseline.diagnostics["source_key"] != relabelled.diagnostics["source_key"]
    assert baseline.diagnostics["source_key"] != repeated_result.diagnostics["source_key"]
    assert baseline.diagnostics["common_right_key"] == relabelled.diagnostics["common_right_key"]
    assert repeated_result.diagnostics["repeat_index"] == 2
    assert repeated_result.diagnostics["saturated_key"] == baseline.diagnostics["saturated_key"]


def test_calm_surface_symmetry_stage_is_separate_from_common_right_stage() -> None:
    source = _stack(I2, SHEAR)
    symmetry_variant = _stack(ROTATION_90 @ I2, SHEAR)
    group = _square_group()

    baseline = calm_stage_keys(
        _record("baseline", source),
        point_group_A=group,
        point_group_B=group,
    )
    variant = calm_stage_keys(
        _record("variant", symmetry_variant),
        point_group_A=group,
        point_group_B=group,
    )

    assert baseline.diagnostics["common_right_key"] != variant.diagnostics["common_right_key"]
    assert baseline.class_key == variant.class_key


def test_reduced_metric_descriptor_can_merge_distinct_coupled_pairs() -> None:
    first = _record("first", _stack(I2, I2), basis_a=np.eye(2), basis_b=np.eye(2))
    second = _record(
        "second",
        _stack(I2, ROTATION_90),
        basis_a=np.eye(2),
        basis_b=ROTATION_90.astype(float),
    )

    descriptor_first = zur_mcgill_descriptor_key(first)
    descriptor_second = zur_mcgill_descriptor_key(second)
    exact_first = calm_stage_keys(
        first,
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )
    exact_second = calm_stage_keys(
        second,
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )

    assert descriptor_first.class_key == descriptor_second.class_key
    assert exact_first.class_key != exact_second.class_key
    assert descriptor_first.metadata.method_kind == "heuristic_grouping"
    assert descriptor_first.diagnostics["published_equivalence_quotient"] is False


def test_interoptimus_signature_ignores_scale_and_rejects_one_sided_swap() -> None:
    source = _stack(np.diag([2, 3]), np.diag([5, 7]))
    rescaled = _stack(np.diag([4, 3]), np.diag([10, 7]))
    swapped = source @ SWAP
    one_side_swapped = _stack(source[:2], source[2:] @ SWAP)
    group = _identity_group()

    keys = [
        interoptimus_direction_signature(
            _record(name, matrix),
            point_group_A=group,
            point_group_B=group,
        ).class_key
        for name, matrix in (
            ("source", source),
            ("rescaled", rescaled),
            ("swapped", swapped),
            ("one-side", one_side_swapped),
        )
    ]

    assert keys[0] == keys[1] == keys[2]
    assert keys[0] != keys[3]


def test_interoptimus_greedy_cluster_uses_pairwise_direction_rule() -> None:
    source = _stack(np.diag([2, 3]), np.diag([5, 7]))
    rescaled = _stack(np.diag([4, 3]), np.diag([10, 7]))
    swapped = source @ SWAP
    one_side_swapped = _stack(source[:2], source[2:] @ SWAP)
    records = tuple(
        _record(
            name,
            matrix,
            basis_a=matrix[:2].astype(float),
            basis_b=matrix[2:].astype(float),
            strains=(d_cell, 0.0),
            source_atom_count=20,
            d_cell=d_cell,
        )
        for name, matrix, d_cell in (
            ("source", source, 0.1),
            ("rescaled", rescaled, 0.2),
            ("swapped", swapped, 0.3),
            ("one-side", one_side_swapped, 0.4),
        )
    )

    result = cluster_interoptimus_style(
        records,
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )

    assert result.status == "classified"
    assert result.class_by_record_id["source"] == result.class_by_record_id["rescaled"]
    assert result.class_by_record_id["source"] == result.class_by_record_id["swapped"]
    assert result.class_by_record_id["source"] != result.class_by_record_id["one-side"]
    assert result.diagnostics["structure_matcher_fallback_included"] is False
    assert result.diagnostics["relation_may_be_nontransitive"] is True


def test_interoptimus_greedy_cluster_exposes_nontransitive_tolerance_effect() -> None:
    def angled(name: str, offset: int, strain_rank: float) -> dict[str, object]:
        block = np.array([[1000, 0], [offset, 1]], dtype=int)
        return _record(
            name,
            _stack(block, block),
            basis_a=block.astype(float),
            basis_b=block.astype(float),
            strains=(strain_rank, 0.0),
            source_atom_count=20,
            d_cell=strain_rank,
        )

    endpoint_first = (
        angled("A", 0, 0.0),
        angled("B", 8, 0.1),
        angled("C", 16, 0.2),
    )
    middle_first = (
        angled("A", 0, 0.1),
        angled("B", 8, 0.0),
        angled("C", 16, 0.2),
    )

    first = cluster_interoptimus_style(
        endpoint_first,
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )
    second = cluster_interoptimus_style(
        middle_first,
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )

    assert first.diagnostics["cluster_count"] == 2
    assert second.diagnostics["cluster_count"] == 1


def test_interoptimus_greedy_applies_substrate_angle_cosine_prefilter() -> None:
    square = I2
    oblique = np.array([[1, 1], [0, 5]], dtype=int)
    records = (
        _record(
            "square",
            _stack(square, square),
            basis_a=square.astype(float),
            basis_b=square.astype(float),
            strains=(0.0, 0.0),
            source_atom_count=2,
        ),
        _record(
            "oblique",
            _stack(oblique, oblique),
            basis_a=oblique.astype(float),
            basis_b=oblique.astype(float),
            strains=(0.01, 0.0),
            source_atom_count=2,
        ),
    )

    result = cluster_interoptimus_style(
        records,
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )

    assert result.diagnostics["cluster_count"] == 2
    assert result.diagnostics["angle_prefilter_rejections"] == 1
    assert result.diagnostics["pair_tests"] == 0


def test_ogre_style_signature_tracks_integer_scale_and_ordered_directions() -> None:
    source = _stack(np.diag([2, 3]), np.diag([5, 7]))
    symmetry_variant = _stack(ROTATION_90 @ source[:2], source[2:])
    changed_scale = source.copy()
    changed_scale[:, 0] *= 2
    group = _square_group()

    baseline = ogre_style_key(
        _record("baseline", source),
        point_group_A=group,
        point_group_B=group,
    )
    symmetric = ogre_style_key(
        _record("symmetric", symmetry_variant),
        point_group_A=group,
        point_group_B=group,
    )
    scaled = ogre_style_key(
        _record("scaled", changed_scale),
        point_group_A=group,
        point_group_B=group,
    )
    swapped = ogre_style_key(
        _record("swapped", source @ SWAP),
        point_group_A=group,
        point_group_B=group,
    )

    assert baseline.class_key == symmetric.class_key
    assert baseline.class_key != scaled.class_key
    assert baseline.class_key != swapped.class_key


def test_jelver_global_gcd_filter_misses_general_directional_repeat() -> None:
    source = _stack(I2, SHEAR)
    scalar_repeat = source @ (2 * I2)
    directional_repeat = source @ REPEAT_ONE_DIRECTION
    group = _identity_group()

    baseline = jelver_style_filter(
        _record("baseline", source, basis_a=I2.astype(float)),
        point_group_A=group,
        point_group_B=group,
    )
    scalar = jelver_style_filter(
        _record("scalar", scalar_repeat, basis_a=(2 * I2).astype(float)),
        point_group_A=group,
        point_group_B=group,
    )
    directional = jelver_style_filter(
        _record(
            "directional",
            directional_repeat,
            basis_a=REPEAT_ONE_DIRECTION.astype(float),
        ),
        point_group_A=group,
        point_group_B=group,
    )

    assert baseline.retained is True
    assert scalar.retained is False
    assert scalar.diagnostics["global_integer_content"] == 2
    assert directional.retained is True
    assert directional.diagnostics["global_integer_content"] == 1


def test_jelver_filter_reports_niggli_input_as_not_applicable_when_missing() -> None:
    result = jelver_style_filter(
        _record("missing", _stack(I2, I2)),
        point_group_A=_identity_group(),
        point_group_B=_identity_group(),
    )

    assert result.status == "not_applicable"
    assert result.retained is None


def test_jelver_cell_symmetry_uses_first_vector_then_second_vector_order() -> None:
    inversion_group = (I2, -I2)
    block_a = np.array([[0, -3], [1, -3]], dtype=int)
    result = jelver_style_filter(
        _record("ordered", _stack(block_a, I2), basis_a=np.eye(2)),
        point_group_A=inversion_group,
        point_group_B=_identity_group(),
    )

    # The second vector (-3, -3) is individually canonical, but the inverse
    # cell starts with (0, -1), which precedes (0, 1) in (u1, u2) order.
    assert result.diagnostics["second_vector_symmetry_canonical_A"] is True
    assert result.diagnostics["cell_symmetry_canonical_A"] is False
    assert result.diagnostics["cell_lexicographic_order"] == (
        "first_vector_then_second_vector"
    )
    assert result.retained is False


def test_intermat_source_selector_requires_and_uses_native_zsl_rank() -> None:
    records = (
        _record("first", _stack(I2, I2)),
        _record("second", _stack(I2, I2)),
    )

    unavailable = select_intermat_source(records)
    selected = select_intermat_source(
        records,
        native_zsl_rank_by_id={"first": 8, "second": 3},
    )

    assert unavailable.status == "not_applicable"
    assert unavailable.reason == "native_zsl_rank_required_for_every_record"
    assert selected.selected_record_ids == ("second",)
    assert selected.diagnostics["selection_semantics"] == "first_accepted_native_zsl_match"


def test_intermat_source_selector_rejects_duplicate_native_zsl_ranks() -> None:
    records = (
        _record("first", _stack(I2, I2)),
        _record("second", _stack(I2, I2)),
    )

    with pytest.raises(ValueError, match="native ZSL ranks must be unique"):
        select_intermat_source(
            records,
            native_zsl_rank_by_id={"first": 3, "second": 3},
        )


def test_intermat_paper_selector_uses_declared_length_mismatch_norm() -> None:
    records = (
        _record(
            "larger",
            _stack(I2, I2),
            basis_a=np.eye(2),
            basis_b=np.diag([1.10, 1.00]),
        ),
        _record(
            "smaller",
            _stack(I2, I2),
            basis_a=np.eye(2),
            basis_b=np.diag([1.02, 1.03]),
        ),
    )

    result = select_intermat_paper_style(records, length_norm="l2")

    assert result.status == "selected"
    assert result.selected_record_ids == ("smaller",)
    assert result.diagnostics["length_norm"] == "l2"
    assert result.diagnostics["admitted_record_count"] == 1
    assert result.diagnostics["rejection_counts_nonexclusive"] == {
        "per_vector_length_mismatch": 1,
        "maximum_endpoint_area": 0,
        "included_angle_mismatch": 0,
    }
    assert result.metadata.method_kind == "selector"


def test_intermat_paper_selector_applies_all_admission_filters_before_ranking() -> None:
    angle = np.deg2rad(92.0)
    records = (
        _record(
            "area-rejected-perfect-match",
            _stack(I2, I2),
            basis_a=20.0 * np.eye(2),
            basis_b=20.0 * np.eye(2),
        ),
        _record(
            "angle-rejected",
            _stack(I2, I2),
            basis_a=np.eye(2),
            basis_b=np.array([[1.0, np.cos(angle)], [0.0, np.sin(angle)]]),
        ),
        _record(
            "length-rejected",
            _stack(I2, I2),
            basis_a=np.eye(2),
            basis_b=np.diag([1.09, 1.00]),
        ),
        _record(
            "admitted",
            _stack(I2, I2),
            basis_a=np.eye(2),
            basis_b=np.diag([1.02, 1.03]),
        ),
    )

    result = select_intermat_paper_style(records)

    assert result.status == "selected"
    assert result.selected_record_ids == ("admitted",)
    assert set(result.score_by_record_id) == {"admitted"}
    assert result.diagnostics["input_record_count"] == 4
    assert result.diagnostics["admitted_record_count"] == 1
    assert result.diagnostics["rejection_counts_nonexclusive"] == {
        "per_vector_length_mismatch": 1,
        "maximum_endpoint_area": 1,
        "included_angle_mismatch": 1,
    }
    assert result.diagnostics["max_length_mismatch"] == pytest.approx(0.08)
    assert result.diagnostics["max_area_angstrom2"] == pytest.approx(300.0)
    assert result.diagnostics["max_angle_mismatch_degrees"] == pytest.approx(1.0)
    assert result.diagnostics["native_parity"] is False


def test_intermat_paper_selector_thresholds_are_configurable() -> None:
    record = _record(
        "candidate",
        _stack(I2, I2),
        basis_a=20.0 * np.eye(2),
        basis_b=22.0 * np.eye(2),
    )

    default = select_intermat_paper_style([record])
    relaxed = select_intermat_paper_style(
        [record],
        max_length_mismatch=0.11,
        max_area=500.0,
        max_angle_mismatch_degrees=0.0,
    )

    assert default.status == "not_applicable"
    assert default.reason == "no_record_passes_paper_admission_filters"
    assert relaxed.status == "selected"
    assert relaxed.selected_record_ids == ("candidate",)


def test_intermat_paper_selector_includes_eight_percent_boundary() -> None:
    boundary = _record(
        "boundary",
        _stack(I2, I2),
        basis_a=np.eye(2),
        basis_b=np.diag([1.08, 1.00]),
    )

    result = select_intermat_paper_style([boundary])

    assert result.status == "selected"
    assert result.selected_record_ids == ("boundary",)


def test_intermat_paper_selector_is_invariant_to_independent_basis_relabelling() -> None:
    basis_a = np.eye(2)
    basis_b = np.diag([1.02, 1.03])
    relabel_a = np.array([[1, 1], [0, 1]], dtype=int)
    relabel_b = np.array([[1, -2], [0, 1]], dtype=int)
    baseline = _record(
        "baseline",
        _stack(I2, I2),
        basis_a=basis_a,
        basis_b=basis_b,
    )
    relabelled = _record(
        "relabelled",
        _stack(relabel_a, relabel_b),
        basis_a=basis_a @ relabel_a,
        basis_b=basis_b @ relabel_b,
    )

    score_a = select_intermat_paper_style([baseline]).score_by_record_id["baseline"]
    score_b = select_intermat_paper_style([relabelled]).score_by_record_id["relabelled"]

    assert np.allclose(score_a, score_b, rtol=1.0e-12, atol=1.0e-12)


def test_intermatch_requires_elastic_data_and_uses_atom_count_priority() -> None:
    records = (
        _record("A", _stack(I2, I2), strains=(0.09, 0.00), source_atom_count=20),
        _record("B", _stack(I2, I2), strains=(0.02, 0.00), source_atom_count=30),
        _record("C", _stack(I2, I2), strains=(0.11, 0.00), source_atom_count=10),
        _record("D", _stack(I2, I2), strains=(0.09, 0.00), source_atom_count=20),
    )

    unavailable = select_intermatch_style(records)
    selected = select_intermatch_style(
        records,
        elastic_energy_by_id={"A": 5.0, "B": 1.0, "D": 4.0},
    )

    assert unavailable.status == "not_applicable"
    assert (
        unavailable.reason
        == "comparable_elastic_energy_required_for_every_eligible_record"
    )
    assert unavailable.diagnostics["missing_record_ids"] == ("A", "B", "D")
    assert selected.status == "selected"
    assert selected.selected_record_ids == ("D",)
    assert selected.diagnostics["eligible_record_count"] == 3


def test_intermatch_rejects_negative_energy_for_eligible_record() -> None:
    record = _record(
        "negative",
        _stack(I2, I2),
        strains=(0.02, 0.00),
        source_atom_count=20,
    )

    with pytest.raises(ValueError, match="elastic energies must be nonnegative"):
        select_intermatch_style(
            [record],
            elastic_energy_by_id={"negative": -1.0},
        )


def test_intermatch_does_not_require_energy_when_no_record_is_strain_eligible() -> None:
    record = _record(
        "ineligible",
        _stack(I2, I2),
        strains=(0.11, 0.00),
        source_atom_count=20,
    )

    result = select_intermatch_style([record])

    assert result.status == "not_applicable"
    assert result.reason == "no_record_within_strain_ceiling"


def test_intermatch_deformation_gate_respects_the_declared_strained_side() -> None:
    record = _record(
        "directional",
        _stack(I2, I2),
        strains=(0.10, 0.00),
        source_atom_count=20,
    )

    side_a = select_intermatch_style(
        [record],
        elastic_energy_by_id={"directional": 1.0},
        strained_side="A",
    )
    side_b = select_intermatch_style(
        [record],
        elastic_energy_by_id={"directional": 1.0},
        strained_side="B",
    )

    assert side_a.status == "not_applicable"
    assert side_a.reason == "no_record_within_strain_ceiling"
    assert side_b.status == "selected"
    assert side_b.selected_record_ids == ("directional",)
    assert side_b.diagnostics["strained_side"] == "B"
    assert "exp(-epsilon_i)" in side_b.diagnostics["deformation_semantics"]


def test_high_level_adapter_results_are_json_serializable_and_complete() -> None:
    record = _record(
        "entry",
        _stack(I2, SHEAR),
        basis_a=np.eye(2),
        basis_b=SHEAR.astype(float),
        strains=(-0.01, 0.02),
        atom_count=8,
    )
    group = _identity_group()

    outcomes = evaluate_record_adapters(
        record,
        point_group_A=group,
        point_group_B=group,
    )

    assert set(outcomes) == {
        "zur_mcgill_descriptor",
        "calm",
        "interoptimus_direction_signature",
        "ogre_style",
        "jelver_style",
    }
    for outcome in outcomes.values():
        assert outcome.record_id == "entry"
        json.dumps(outcome.to_dict(), sort_keys=True)
