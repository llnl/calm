from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from calm.project.application.slabs import (
    SlabsService,
    _build_slab_atoms_if_available,
)


def test_missing_parent_atoms_is_the_only_spec_only_path() -> None:
    assert (
        _build_slab_atoms_if_available(
            bulk_payload={},
            miller=(1, 0, 0),
            vacuum=10.0,
        )
        is None
    )


def test_malformed_parent_atoms_payload_fails_closed() -> None:
    with pytest.raises(TypeError, match="atoms payload must be a mapping"):
        _build_slab_atoms_if_available(
            bulk_payload={"atoms": "not-a-mapping"},
            miller=(1, 0, 0),
            vacuum=10.0,
        )


def test_atomistic_construction_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_atoms_module = ModuleType("calm.structure.payloads")

    def atoms_from_dict(payload):
        return object()

    fake_atoms_module.atoms_from_dict = atoms_from_dict
    monkeypatch.setitem(sys.modules, "calm.structure.payloads", fake_atoms_module)

    fake_bulk_module = ModuleType("calm.bulk.bulk")

    def bulk_factory(atoms):
        return object()

    fake_bulk_module.Bulk = bulk_factory
    monkeypatch.setitem(sys.modules, "calm.bulk.bulk", fake_bulk_module)

    def fail_build(**kwargs):
        raise RuntimeError("authoritative slab failure")

    monkeypatch.setattr(
        "calm.project.application.slabs._build_selected_slab_atoms",
        fail_build,
    )

    with pytest.raises(RuntimeError, match="authoritative slab failure"):
        _build_slab_atoms_if_available(
            bulk_payload={"atoms": {}},
            miller=(1, 0, 0),
            vacuum=10.0,
        )


def test_termination_enumeration_preserves_authoritative_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SlabsService(uow_factory=lambda: object())
    bulk = SimpleNamespace(payload={"atoms": {}})

    fake_atoms_module = ModuleType("calm.structure.payloads")

    def atoms_from_dict(payload):
        return object()

    fake_atoms_module.atoms_from_dict = atoms_from_dict
    monkeypatch.setitem(sys.modules, "calm.structure.payloads", fake_atoms_module)

    fake_bulk_module = ModuleType("calm.bulk.bulk")

    def bulk_factory(atoms, symprec):
        return object()

    fake_bulk_module.Bulk = bulk_factory
    monkeypatch.setitem(sys.modules, "calm.bulk.bulk", fake_bulk_module)

    def fail_enumeration(*args, **kwargs):
        raise ValueError("surface symmetry failed")

    monkeypatch.setattr(
        "calm.slab.oriented.terminations.identify_unique_terminations",
        fail_enumeration,
    )

    with pytest.raises(ValueError, match="surface symmetry failed"):
        service._get_terminations_for_miller(
            bulk,
            (1, 0, 0),
            {},
        )
