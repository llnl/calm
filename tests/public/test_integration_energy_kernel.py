"""The public InterfaceModel is a result object, not an energy executor."""

from calm.public.records.interfaces import InterfaceModel


def test_interface_model_has_no_direct_energy_execution_path() -> None:
    assert not hasattr(InterfaceModel, "_energy")
