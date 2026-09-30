import json

import numpy as np

from test_helpers import coupled_pair_metadata


def test_interface_prototype_uses_canonical_fields_and_to_dict() -> None:
    """Prototype reporting uses one canonical field vocabulary."""

    from calm.interface.model import InterfacePrototype, SupercellRecipe2D

    I = np.eye(2, dtype=int)

    sc_a = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 2), cond=1.0)
    sc_b = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 3), cond=1.5)

    pair_identity, source_provenance = coupled_pair_metadata(sc_a, sc_b)

    proto = InterfacePrototype(
        prototype_uid="proto:test",
        match_score=0.123456789,
        d_cell=0.123456789,
        d_area=0.2,
        d_shape=0.3,
        d_size=0.4,
        rel_da=0.5,
        rel_db=0.6,
        d_gamma_deg=7.0,
        n_atoms_interface=42,
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        miller_a=(1, 1, 1),
        miller_b=(1, 1, 1),
        supercell_a=sc_a,
        supercell_b=sc_b,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
        # The façade/API should not require real Slab objects for basic
        # reporting/serialization.
        slab_a=None,  # type: ignore[arg-type]
        slab_b=None,  # type: ignore[arg-type]
    )

    assert proto.prototype_uid == "proto:test"
    assert proto.hnf_key_a == (1, 0, 0, 2)
    assert proto.hnf_key_b == (1, 0, 0, 3)

    d = proto.to_dict(rank=7)
    assert d["prototype_uid"] == "proto:test"
    assert d["rank"] == 7
    assert d["hnf_key_a"] == [1, 0, 0, 2]
    assert d["hnf_key_b"] == [1, 0, 0, 3]
    assert np.isclose(d["d_gamma_deg"], 7.0)

    # Optional evidence payloads (signature + fingerprint) should be available
    # behind an explicit flag.
    d2 = proto.to_dict(rank=7, include_fingerprints=True)
    assert "signature" in d2
    assert "fingerprint" in d2
    json.dumps(d2["signature"])  # JSON-serializable
    json.dumps(d2["fingerprint"])  # JSON-serializable

    # Deterministic fingerprints are used for regression/evidence.
    fp = proto.fingerprint(ndigits=4, rank=7)
    json.dumps(fp)  # should be JSON-serializable
    assert fp["rank"] == 7
    assert fp["score"] == 0.1235
    assert fp["d_cell"] == 0.1235
