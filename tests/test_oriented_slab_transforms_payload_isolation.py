"""Regression guardrails for oriented-slab transforms accessors.

The accessor properties should be *side-effect free* for callers.
In particular, callers should be able to treat the returned payload dict
as an ephemeral snapshot without risking mutation of internal cached state.

Historically the payload was exposed via a cached_property, which meant that
mutating the dict would mutate the cached value for the lifetime of the
Slab instance. We now prefer returning a fresh dict on each access.
"""

from __future__ import annotations

from ase.build import bulk as ase_bulk

from calm.bulk.bulk import Bulk
from calm.slab.slab import Slab
from calm.slab.slab import SlabSpec


def _mk_slab() -> Slab:
    bulk_atoms = ase_bulk("Al", a=4.05, cubic=True)
    bulk = Bulk(bulk_atoms, label="Al")

    spec = SlabSpec(
        miller=(1, 1, 1),
        n_layers=3,
        vacuum=8.0,
        pbc=(True, True, True),
        verbose=False,
    )

    return Slab(bulk, spec)


def test_oriented_slab_transforms_payload_is_not_mutably_cached() -> None:
    slab = _mk_slab()

    payload_1 = slab.oriented_slab_transforms_payload
    assert isinstance(payload_1, dict)

    # Mutate the returned snapshot.
    payload_1["__calm_mutation_test__"] = True

    # Re-fetch; the mutation must not persist.
    payload_2 = slab.oriented_slab_transforms_payload
    assert "__calm_mutation_test__" not in payload_2
