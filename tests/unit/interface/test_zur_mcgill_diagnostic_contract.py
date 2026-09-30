from __future__ import annotations

import inspect

import numpy as np

from test_helpers import coupled_pair_metadata

from calm.interface.matching.zur_mcgill import (
    ZUR_MCGILL_DIAGNOSTIC_POLICY,
    ZUR_MCGILL_DIAGNOSTIC_VERSION,
)
import calm.interface.matching._orchestrator as _coupled_matching
from calm.interface.model import InterfacePrototype, SupercellRecipe2D
from calm.interface.types import ZMStrain2D


def test_zur_mcgill_projection_is_self_describing_and_diagnostic_only() -> None:
    diagnostic = ZMStrain2D.from_bases(
        np.eye(2),
        np.array([[1.1, 0.2], [0.0, 0.9]]),
    )
    payload = diagnostic.to_diagnostic_dict()
    assert payload["policy"] == ZUR_MCGILL_DIAGNOSTIC_POLICY
    assert payload["policy_version"] == ZUR_MCGILL_DIAGNOSTIC_VERSION
    assert payload["diagnostic_only"] is True
    assert payload["authoritative_uses"] == ()


def test_prototype_public_projection_labels_legacy_mismatch_values() -> None:
    recipe = SupercellRecipe2D(
        k=1,
        N_tot=np.eye(2, dtype=int),
        R_sup=np.eye(2),
        hnf_key_pg=(1, 0, 0, 1),
        cond=1.0,
    )
    pair_identity, source_provenance = coupled_pair_metadata(recipe, recipe)

    prototype = InterfacePrototype(
        prototype_uid="proto:test",
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
        miller_a=(1, 0, 0),
        miller_b=(1, 0, 0),
        supercell_a=recipe,
        supercell_b=recipe,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
        match_score=0.1,
        d_size=0.2,
        d_cell=0.3,
        d_area=0.1,
        d_shape=0.2,
        rel_da=0.01,
        rel_db=0.02,
        d_gamma_deg=1.5,
        n_atoms_interface=2,
        slab_a=object(),  # type: ignore[arg-type]
        slab_b=object(),  # type: ignore[arg-type]
    )
    diagnostic = prototype.to_dict()["zur_mcgill_diagnostic"]
    assert diagnostic["diagnostic_only"] is True
    assert diagnostic["policy"] == ZUR_MCGILL_DIAGNOSTIC_POLICY
    assert diagnostic["authoritative_uses"] == ()
    assert diagnostic["rel_da"] == 0.01


def test_authoritative_scoring_does_not_consume_zur_mcgill_components() -> None:
    source = inspect.getsource(_coupled_matching._build_candidate_geometry)
    assert ".rel_da" not in source
    assert ".rel_db" not in source
    assert ".d_gamma_deg" not in source
    assert source.index("match_score =") < source.index("ZMStrain2D.from_bases")
