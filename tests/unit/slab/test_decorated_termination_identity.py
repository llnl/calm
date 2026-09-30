from __future__ import annotations

import numpy as np
import pytest

from calm.slab.oriented.termination_identity import (
    DecoratedLayerAtom,
    DecoratedPeriodicLayer,
    TERMINATION_IDENTITY_VERSION,
    enumerate_decorated_termination_classes,
    normalize_surface_operations,
    stacking_translation_order,
)


def _layer(
    phase: float,
    species_and_uv: list[tuple[str, tuple[float, float]]],
    *,
    composition: str | None = None,
) -> DecoratedPeriodicLayer:
    counts: dict[str, int] = {}
    for symbol, _uv in species_and_uv:
        counts[symbol] = counts.get(symbol, 0) + 1
    stoichiometry = tuple(sorted(counts.items()))
    return DecoratedPeriodicLayer(
        phase=phase,
        height_A=phase,
        atom_indices=tuple(range(len(species_and_uv))),
        composition=composition or "".join(
            f"{symbol}{count if count > 1 else ''}"
            for symbol, count in stoichiometry
        ),
        stoichiometry=stoichiometry,
        atoms=tuple(
            DecoratedLayerAtom(symbol=symbol, uv=uv)
            for symbol, uv in species_and_uv
        ),
    )


def _enumerate(
    layers: list[DecoratedPeriodicLayer],
    *,
    translation=(0.0, 0.0),
    symmetry=None,
    repeats=2,
):
    return enumerate_decorated_termination_classes(
        layers,
        stacking_translation_frac=translation,
        normal_period_A=3.0,
        slab_repeat_count=repeats,
        symmetry_operations=symmetry,
        layer_tolerance_A=1e-5,
        position_tolerance_frac=1e-5,
        stacking_tolerance_frac=1e-8,
    )


def test_monatomic_abc_stacking_has_order_three_but_one_class():
    layers = [_layer(0.0, [("X", (0.0, 0.0))])]
    assert stacking_translation_order((1.0 / 3.0, 2.0 / 3.0)) == 3
    classes = _enumerate(layers, translation=(1.0 / 3.0, 2.0 / 3.0))
    assert len(classes) == 1
    assert len(classes[0].top_signature) == 3
    assert classes[0].top_identity["version"] == TERMINATION_IDENTITY_VERSION


def test_ab_stacking_produces_two_ordered_pairs():
    layers = [
        _layer(0.0, [("A", (0.0, 0.0))]),
        _layer(0.5, [("B", (0.0, 0.0))]),
    ]
    classes = _enumerate(layers, repeats=3)
    assert len(classes) == 2
    assert classes[0].top_identity != classes[1].top_identity
    assert classes[0].pair_identity != classes[1].pair_identity
    assert classes[0].top_identity != classes[0].bottom_identity


def test_aba_sequence_distinguishes_the_two_a_halfspaces():
    layers = [
        _layer(0.0, [("A", (0.0, 0.0))]),
        _layer(1.0 / 3.0, [("B", (0.0, 0.0))]),
        _layer(2.0 / 3.0, [("A", (0.0, 0.0))]),
    ]

    classes = _enumerate(layers, repeats=2)

    assert len(classes) == 3
    a_classes = [
        item
        for item in classes
        if item.representative_layer_index in {0, 2}
    ]
    assert len(a_classes) == 2
    assert a_classes[0].top_identity != a_classes[1].top_identity


def test_same_stoichiometry_lateral_motifs_remain_distinct():
    layers = [
        _layer(
            0.0,
            [("X", (0.0, 0.0)), ("X", (0.5, 0.0))],
            composition="X2",
        ),
        _layer(
            0.5,
            [("X", (0.0, 0.0)), ("X", (0.25, 0.25))],
            composition="X2",
        ),
    ]
    classes = _enumerate(layers)
    assert len(classes) == 2
    assert classes[0].top_identity != classes[1].top_identity


def test_translation_order_and_wrapping_are_identity_invariant():
    original = [
        _layer(0.0, [("A", (0.1, 0.2)), ("B", (0.6, 0.2))]),
        _layer(0.5, [("C", (0.3, 0.7))]),
    ]
    shifted = [
        _layer(0.0, [("B", (1.97, -0.17)), ("A", (1.47, -0.17))]),
        _layer(0.5, [("C", (1.67, 0.33))]),
    ]
    first = _enumerate(original)
    second = _enumerate(shifted)
    assert [item.top_identity for item in first] == [
        item.top_identity for item in second
    ]
    assert [item.pair_identity for item in first] == [
        item.pair_identity for item in second
    ]


def test_declared_surface_symmetry_merges_equivalent_motifs():
    layers = [
        _layer(0.0, [("A", (0.2, 0.1)), ("B", (0.4, 0.1))]),
        _layer(0.5, [("A", (-0.2, -0.1)), ("B", (-0.4, -0.1))]),
    ]
    identity_only = _enumerate(layers, symmetry=[np.eye(2, dtype=int)])
    with_inversion = _enumerate(
        layers,
        symmetry=[np.eye(2, dtype=int), -np.eye(2, dtype=int)],
    )
    assert len(identity_only) == 2
    assert len(with_inversion) == 1
    assert with_inversion[0].equivalent_layer_indices == (0, 1)


def test_ordered_pair_identity_is_explicit():
    layers = [
        _layer(0.0, [("A", (0.0, 0.0))]),
        _layer(0.25, [("B", (0.0, 0.0))]),
        _layer(0.75, [("C", (0.0, 0.0))]),
    ]
    classes = _enumerate(layers, repeats=1)
    for item in classes:
        assert item.pair_identity["scheme"] == "ordered_termination_pair_v2"
        assert item.top_identity["orientation"] == "plus_surface_normal"
        assert item.bottom_identity["orientation"] == "minus_surface_normal"


def test_stacking_order_failure_is_explicit():
    with pytest.raises(ValueError, match="Unable to establish"):
        stacking_translation_order(
            (np.sqrt(2.0) / 10.0, 0.0),
            tolerance=1e-12,
            max_order=8,
        )


def test_tolerance_policy_is_part_of_identity():
    layers = [_layer(0.0, [("X", (0.123456, 0.0))])]
    coarse = enumerate_decorated_termination_classes(
        layers,
        stacking_translation_frac=(0.0, 0.0),
        normal_period_A=2.0,
        slab_repeat_count=1,
        layer_tolerance_A=1e-4,
        position_tolerance_frac=1e-4,
    )
    fine = enumerate_decorated_termination_classes(
        layers,
        stacking_translation_frac=(0.0, 0.0),
        normal_period_A=2.0,
        slab_repeat_count=1,
        layer_tolerance_A=1e-6,
        position_tolerance_frac=1e-6,
    )
    assert coarse[0].top_identity != fine[0].top_identity


def test_termination_symmetry_requires_a_complete_group() -> None:
    identity = np.eye(2, dtype=int)
    shear = np.array([[1, 1], [0, 1]], dtype=int)

    with pytest.raises(ValueError, match="missing the inverse"):
        normalize_surface_operations([identity, shear])

    with pytest.raises(ValueError, match="explicitly contain identity"):
        normalize_surface_operations([-identity])
