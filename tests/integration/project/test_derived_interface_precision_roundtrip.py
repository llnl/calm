"""Round-trip contracts for identity-bearing derived-interface specifications."""

from __future__ import annotations

from calm.project.domain.contracts.derived_interface import canonical_derived_interface_spec
from calm.project.domain.identity_v2 import (
    derived_interface_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import DerivedInterface


def test_high_precision_spec_roundtrips_without_identity_drift(
    sqlite_uow_factory,
) -> None:
    prototype_uid = "proto:v2:" + ("1" * 64)
    spec = canonical_derived_interface_spec(
        {
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": prototype_uid,
            "stage": "relaxed",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 2.0,
            "vacuum": 10.0,
            "params": {
                "scientific_authority": "calculator_backed",
                "final_energy_eV": -1.2345678901234567,
            },
        },
        prototype_uid_full=prototype_uid,
    )
    uid = persisted_entity_uid_v2(
        "derived_interface",
        derived_interface_identity_payload(
            prototype_uid_full=prototype_uid,
            spec=spec,
        ),
    )
    interface = DerivedInterface(
        uid_full=uid,
        id_short="i_precision",
        prototype_uid_full=prototype_uid,
        label="relaxed",
        spec=spec,
    )

    with sqlite_uow_factory() as uow:
        stored = uow.derived_interfaces.upsert(interface)
        assert stored.uid_full == uid

    with sqlite_uow_factory() as reopened:
        restored = reopened.derived_interfaces.get_by_uid_full(uid)

    assert restored is not None
    assert restored.uid_full == uid
    assert restored.spec == spec
