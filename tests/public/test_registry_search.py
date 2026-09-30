"""Registry search execution belongs to Project refinement workflows."""

from calm.public.records.interfaces import InterfaceCandidate


def test_interface_candidate_has_no_registry_search_executor() -> None:
    assert not hasattr(InterfaceCandidate, "_search_registry")
