from __future__ import annotations

import hashlib
import json

import numpy as np

from test_helpers import coupled_pair_metadata


def _sha256_json(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_interface_prototype_to_dict_fingerprints_deterministic() -> None:
    """Evidence C4: fingerprint/signature payloads are deterministic and stable.

    Requirements
    ------------
    1) include_fingerprints=False does not emit evidence payloads.
    2) include_fingerprints=True emits both 'signature' and 'fingerprint'.
    3) Repeated calls with the same inputs are bitwise-identical.
    4) Changing 'rank' must not change the signature/fingerprint.
    5) Changing fingerprint_ndigits must change at least one of
       (signature, fingerprint) for nontrivial floating inputs.
    """

    from calm.interface.model import InterfacePrototype, SupercellRecipe2D

    I = np.eye(2, dtype=int)

    # Use distinct HNF keys so serialization can confirm they survive.
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
        slab_a=None,  # type: ignore[arg-type]
        slab_b=None,  # type: ignore[arg-type]
    )

    # (1) no evidence payload by default
    d0 = proto.to_dict(rank=7)
    assert "signature" not in d0
    assert "fingerprint" not in d0

    # (2) evidence payloads present when requested
    d1 = proto.to_dict(rank=7, include_fingerprints=True, fingerprint_ndigits=10)
    assert "signature" in d1
    assert "fingerprint" in d1

    sig1 = d1["signature"]
    fp1 = d1["fingerprint"]

    assert isinstance(sig1, str)
    assert len(sig1) >= 32

    # Fingerprint must be JSON-serializable.
    _ = _sha256_json(fp1)

    # (3) determinism on repeated calls
    d2 = proto.to_dict(rank=7, include_fingerprints=True, fingerprint_ndigits=10)
    assert d2 == d1

    # (4) rank independence for evidence payloads
    d3 = proto.to_dict(rank=8, include_fingerprints=True, fingerprint_ndigits=10)
    assert d3["signature"] == sig1
    assert d3["fingerprint"] == fp1

    # (5) ndigits should affect fingerprint/signature for nontrivial floats
    d4 = proto.to_dict(rank=7, include_fingerprints=True, fingerprint_ndigits=6)
    same_sig = d4.get("signature") == sig1
    same_fp = d4.get("fingerprint") == fp1
    assert not (same_sig and same_fp), "fingerprint_ndigits had no effect on evidence payloads"
