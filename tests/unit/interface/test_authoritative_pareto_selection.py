from __future__ import annotations

import numpy as np

from test_helpers import coupled_pair_metadata

from calm.interface.model import InterfacePrototype, SupercellRecipe2D
from calm.interface.pipeline import (
    _annotate_authoritative_pareto,
    _retain_ranked_prototypes,
)


def _prototype(
    uid: str,
    *,
    atoms: int,
    d_cell: float,
    score: float,
) -> InterfacePrototype:
    identity = np.eye(2, dtype=int)
    cell_a = SupercellRecipe2D(
        k=1,
        N_tot=identity,
        R_sup=identity,
        hnf_key_pg=(1, 0, 0, 1),
        cond=1.0,
    )
    cell_b = SupercellRecipe2D(
        k=1,
        N_tot=identity,
        R_sup=identity,
        hnf_key_pg=(1, 0, 0, 2),
        cond=1.0,
    )
    pair_identity, source_provenance = coupled_pair_metadata(cell_a, cell_b)

    return InterfacePrototype(
        prototype_uid=uid,
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        miller_a=(1, 0, 0),
        miller_b=(1, 0, 0),
        supercell_a=cell_a,
        supercell_b=cell_b,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
        match_score=score,
        d_size=0.0,
        d_cell=d_cell,
        d_area=0.0,
        d_shape=d_cell,
        rel_da=0.0,
        rel_db=0.0,
        d_gamma_deg=0.0,
        n_atoms_interface=atoms,
        slab_a=None,  # type: ignore[arg-type]
        slab_b=None,  # type: ignore[arg-type]
    )


def test_match_score_does_not_change_pareto_membership_or_input_order() -> None:
    first = [
        _prototype("small", atoms=50, d_cell=0.2, score=0.9),
        _prototype("low-strain", atoms=100, d_cell=0.1, score=0.1),
        _prototype("dominated", atoms=60, d_cell=0.3, score=0.0),
    ]
    second = [
        _prototype("small", atoms=50, d_cell=0.2, score=0.1),
        _prototype("low-strain", atoms=100, d_cell=0.1, score=0.9),
        _prototype("dominated", atoms=60, d_cell=0.3, score=0.0),
    ]

    annotated_first, front_first = _annotate_authoritative_pareto(first)
    annotated_second, front_second = _annotate_authoritative_pareto(second)

    assert set(front_first) == {"small", "low-strain"}
    assert set(front_second) == set(front_first)
    assert [item.prototype_uid for item in annotated_first] == [
        item.prototype_uid for item in first
    ]
    assert [item.prototype_uid for item in annotated_second] == [
        item.prototype_uid for item in second
    ]


def test_output_limit_does_not_prefer_dominated_weighted_candidate() -> None:
    points = [
        _prototype("small", atoms=50, d_cell=0.2, score=0.9),
        _prototype("low-strain", atoms=100, d_cell=0.1, score=0.8),
        _prototype("dominated", atoms=60, d_cell=0.3, score=0.0),
    ]
    annotated, _ = _annotate_authoritative_pareto(points)
    by_uid = {item.prototype_uid: item for item in annotated}
    authoritative_ranked = [
        by_uid["dominated"],
        by_uid["small"],
        by_uid["low-strain"],
    ]

    retained = _retain_ranked_prototypes(
        authoritative_ranked,
        max_results=2,
    )

    assert {item.prototype_uid for item in retained} == {
        "small",
        "low-strain",
    }
    assert all(item.is_pareto for item in retained)
    assert all(item.pareto_population_size == 3 for item in retained)


def test_result_limit_zero_is_explicit() -> None:
    annotated, _ = _annotate_authoritative_pareto(
        [_prototype("only", atoms=10, d_cell=0.1, score=0.0)]
    )
    assert _retain_ranked_prototypes(annotated, max_results=0) == []
