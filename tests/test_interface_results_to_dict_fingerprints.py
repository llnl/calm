"""Tests for optional evidence payloads (signature + fingerprints) in result objects.

These tests are intentionally lightweight and focus on API stability:

- `PrototypeSearchResult.to_dict(include_fingerprints=True)` should propagate
  `include_fingerprints` to each `InterfacePrototype.to_dict(...)`.
- The canonical `PrototypeSearchResult` type carries optional evidence payloads.
"""

from __future__ import annotations

import json

import numpy as np

from test_helpers import coupled_pair_metadata


def test_prototype_search_result_to_dict_can_include_fingerprints() -> None:
    import calm.interface.results as results_module
    from calm.interface.config import PrototypeSearchConfig
    from calm.interface.model import InterfacePrototype, SupercellRecipe2D
    from calm.interface.results import PrototypeSearchResult

    assert not hasattr(results_module, "InterfacePrototypeSearchResult")

    I = np.eye(2, dtype=int)

    sc_a = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 2), cond=1.0)
    sc_b = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 3), cond=1.5)

    pair_identity, source_provenance = coupled_pair_metadata(sc_a, sc_b)

    proto = InterfacePrototype(
        prototype_uid="proto:test",
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

    cfg = PrototypeSearchConfig(k_max=2, max_results=10)
    res = PrototypeSearchResult(config=cfg, prototypes=[proto])

    # Convenience: slab_uids may be inferred from prototypes when omitted.
    assert res.slab_a_uid == 'slab:A'
    assert res.slab_b_uid == 'slab:B'

    # Default: no evidence payloads in the per-prototype dict.
    d0 = res.to_dict(include_fingerprints=False)
    p0 = d0["prototypes"][0]
    assert "signature" not in p0
    assert "fingerprint" not in p0

    # With evidence payloads enabled.
    d1 = res.to_dict(include_fingerprints=True)
    p1 = d1["prototypes"][0]

    assert "signature" in p1
    assert "fingerprint" in p1

    # Both should be JSON serializable.
    json.dumps(p1["signature"], sort_keys=True)
    json.dumps(p1["fingerprint"], sort_keys=True)
