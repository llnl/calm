"""Dependency-light invariants for interface derivation."""

from __future__ import annotations

import pytest


class _Ids:
    def resolve(self, value: str, *, expected_tag: str) -> str:
        assert expected_tag == "i"
        assert value == "i_seed"
        return "iface:seed"

    def ensure_short_id(self, *, tag: str, uid_full: str) -> str:
        assert tag == "i"
        assert uid_full.startswith("iface:")
        return "i_derived"


class _DerivedInterfaces:
    def __init__(self, seed):
        self.seed = seed
        self.persisted = None

    def get_by_uid_full(self, uid: str):
        return self.seed if uid == self.seed.uid_full else None

    def upsert(self, interface):
        self.persisted = interface
        return interface


class _Edges:
    def add(self, **_kwargs) -> None:
        return None


class _UnitOfWork:
    def __init__(self, seed):
        self.ids = _Ids()
        self.derived_interfaces = _DerivedInterfaces(seed)
        self.edges = _Edges()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def commit(self) -> None:
        return None


def test_derived_interface_can_preserve_authoritative_implicit_vacuum() -> None:
    from calm.project.application.derived_interfaces import DerivedInterfaceService
    from calm.project.domain.models import DerivedInterface

    seed = DerivedInterface(
        uid_full="iface:seed",
        id_short="i_seed",
        prototype_uid_full="proto:x",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:x",
            "stage": "registry_refined",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": 12.0,
            "params": {},
        },
    )
    service = DerivedInterfaceService(uow_factory=lambda: _UnitOfWork(seed))

    derived = service.create(
        prototype="i_seed",
        vacuum=None,
        inherit_seed_vacuum=False,
    )

    assert derived.spec["vacuum"] is None
    assert derived.spec["z_padding"] == pytest.approx(1.5)


def test_derived_interface_inherits_seed_vacuum_by_default() -> None:
    from calm.project.application.derived_interfaces import DerivedInterfaceService
    from calm.project.domain.models import DerivedInterface

    seed = DerivedInterface(
        uid_full="iface:seed",
        id_short="i_seed",
        prototype_uid_full="proto:x",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:x",
            "stage": "registry_refined",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": 12.0,
            "params": {},
        },
    )
    service = DerivedInterfaceService(uow_factory=lambda: _UnitOfWork(seed))

    derived = service.create(prototype="i_seed")

    assert derived.spec["vacuum"] == pytest.approx(12.0)


def test_derived_interface_does_not_inherit_seed_atom_artifact() -> None:
    from calm.project.application.derived_interfaces import DerivedInterfaceService
    from calm.project.domain.models import DerivedInterface

    seed = DerivedInterface(
        uid_full="iface:seed",
        id_short="i_seed",
        prototype_uid_full="proto:x",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:x",
            "stage": "built",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": 12.0,
            "params": {},
            "atoms_artifact_uid": "artifact:seed",
            "artifact_refs": [
                {
                    "artifact_uid": "artifact:seed",
                    "kind": "interface_atoms",
                    "role": "derived_interface_atoms",
                    "uri": "artifacts/seed.json",
                }
            ],
        },
    )
    service = DerivedInterfaceService(uow_factory=lambda: _UnitOfWork(seed))

    derived = service.create(
        prototype="i_seed",
        stage="registry_refined",
        registry_shift_frac_a=(0.25, 0.5),
    )

    assert derived.atoms_artifact_uid is None
    assert derived.artifact_refs == []


def test_derived_interface_writer_rejects_nested_nonstring_param_keys() -> None:
    from calm.project.application.derived_interfaces import DerivedInterfaceService
    from calm.project.domain.models import DerivedInterface

    seed = DerivedInterface(
        uid_full="iface:seed",
        id_short="i_seed",
        prototype_uid_full="proto:x",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:x",
            "stage": "built",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": None,
            "params": {},
        },
    )
    service = DerivedInterfaceService(uow_factory=lambda: _UnitOfWork(seed))

    with pytest.raises(TypeError, match="whitespace-trimmed strings"):
        service.create(prototype="i_seed", params={"nested": {1: "value"}})


def _current_strain_state(alpha: float = 0.5) -> dict:
    return {
        "schema": "calm.interface_strain_state",
        "version": 2,
        "prototype_uid_full": "proto:x",
        "strain_model_uid": "smodel:seed",
        "strain_alpha": alpha,
        "deformation_scope": "incremental_interface_matching",
        "deformation_accounting_policy": "composed_slab_deformation",
        "deformation_accounting_version": 1,
        "F_tot": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "F_A": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "F_B": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "E_A_rms": 0.0,
        "E_B_rms": 0.0,
    }


def _strain_seed():
    from calm.project.domain.models import DerivedInterface

    return DerivedInterface(
        uid_full="iface:seed",
        id_short="i_seed",
        prototype_uid_full="proto:x",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:x",
            "stage": "strain_partitioned",
            "strain_alpha": 0.5,
            "registry_shift_frac_a": [0.0, 0.0],
            "z_padding": 1.5,
            "vacuum": 12.0,
            "params": {},
            "strain_state": _current_strain_state(),
        },
    )


def test_seed_strain_state_is_inherited_only_for_the_same_partition() -> None:
    from calm.project.application.derived_interfaces import DerivedInterfaceService

    seed = _strain_seed()
    service = DerivedInterfaceService(uow_factory=lambda: _UnitOfWork(seed))

    same_partition = service.create(
        prototype="i_seed",
        stage="registry_refined",
        registry_shift_frac_a=(0.25, 0.5),
    )
    changed_partition = service.create(
        prototype="i_seed",
        stage="strain_partitioned",
        strain_alpha=0.25,
    )

    assert same_partition.strain_state == seed.strain_state
    assert changed_partition.strain_state is None


def test_seed_strain_state_can_be_invalidated_by_cell_changing_workflow() -> None:
    from calm.project.application.derived_interfaces import DerivedInterfaceService

    seed = _strain_seed()
    service = DerivedInterfaceService(uow_factory=lambda: _UnitOfWork(seed))

    derived = service.create_in(
        _UnitOfWork(seed),
        prototype="i_seed",
        stage="relaxed",
        inherit_seed_strain_state=False,
    )

    assert derived.strain_state is None
