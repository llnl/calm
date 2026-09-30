"""Ownership guards for interface follow-up workflows."""

from calm.public.records.interfaces import InterfaceModel


def test_interface_model_does_not_execute_energy_or_relaxation() -> None:
    assert not hasattr(InterfaceModel, "_energy")
    assert not hasattr(InterfaceModel, "_relax")
