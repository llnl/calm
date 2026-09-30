from __future__ import annotations

import numpy as np

from test_helpers import coupled_pair_metadata


def _make_proto(uid: str) -> "InterfacePrototype":
    from calm.interface.model import InterfacePrototype, SupercellRecipe2D

    I = np.eye(2, dtype=int)
    sc_a = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 2), cond=1.0)
    sc_b = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 3), cond=1.0)

    pair_identity, source_provenance = coupled_pair_metadata(sc_a, sc_b)

    return InterfacePrototype(
        prototype_uid=uid,
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        miller_a=(1, 1, 1),
        miller_b=(1, 1, 1),
        supercell_a=sc_a,
        supercell_b=sc_b,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
        slab_a=None,  # type: ignore[arg-type]
        slab_b=None,  # type: ignore[arg-type]
        match_score=0.1,
        d_size=0.0,
        d_cell=0.2,
        d_area=0.3,
        d_shape=0.4,
        rel_da=0.1,
        rel_db=0.2,
        d_gamma_deg=0.0,
        n_atoms_interface=10,
    )


def test_prototype_search_result_behaves_like_a_sequence() -> None:
    """UX: allow `len(res)`, iteration, and slicing.

    This keeps example scripts and user notebooks lightweight.
    """

    from calm.interface.config import PrototypeSearchConfig
    from calm.interface.results import PrototypeSearchResult

    p0 = _make_proto("proto:0")
    p1 = _make_proto("proto:1")

    cfg = PrototypeSearchConfig(k_max=2, max_results=10)
    res = PrototypeSearchResult(config=cfg, prototypes=[p0, p1])

    assert len(res) == 2
    assert list(res) == [p0, p1]
    assert res[0] is p0
    assert res[:1] == [p0]

    d = res.to_dict()
    assert d["prototypes"][0]["rank"] == 1

    empty = PrototypeSearchResult(config=cfg, prototypes=[], slab_a_uid="slab:A", slab_b_uid="slab:B")
    assert len(empty) == 0
    assert not empty

def test_manual_result_records_current_population_without_mutating_prototypes() -> None:
    from calm.interface.results import PrototypeSearchResult

    p0 = _make_proto("proto:0")
    p1 = _make_proto("proto:1")
    result = PrototypeSearchResult(prototypes=[p0, p1])

    assert result.prototypes == [p0, p1]
    assert p0.pareto_policy is None
    assert result.pareto_population_scope == "current_result_population"
    assert result.pareto_front_uids == ("proto:0", "proto:1")
