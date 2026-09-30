"""Reference-energy evaluation belongs to Project workflows."""

from calm.public.records.interfaces import InterfaceModel


def test_interface_model_has_no_reference_energy_execution_path() -> None:
    assert not hasattr(InterfaceModel, "_energy")
