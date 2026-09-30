import pytest

from calm.public.records.generated_surface import GeneratedSurface
from calm.public.workflows.search import search_interfaces
from calm.public.inputs.settings import SearchSettings


def test_search_rejects_generated_surface_without_authoritative_atoms() -> None:
    surface = GeneratedSurface(
        id_short="s_a",
        uid_full="slab:a",
        label="A",
        material="A",
        miller=(1, 0, 0),
        natoms=4,
        area=None,
        authority="authoritative",
        _object=None,
    )
    with pytest.raises(TypeError, match="no slab object or atomistic payload"):
        search_interfaces(surface, surface, settings=SearchSettings())
