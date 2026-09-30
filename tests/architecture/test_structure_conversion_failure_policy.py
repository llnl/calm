from __future__ import annotations

import inspect

import calm.public.records.generated_surface as generated_surface_module
import calm.public.inputs.materials as materials_module
import calm.structure.characterization as characterization_module
import calm.structure.payloads as payloads_module


def test_current_structure_readers_do_not_use_broad_exception_fallbacks() -> None:
    sources = {
        "ase_atoms": inspect.getsource(payloads_module),
        "material": inspect.getsource(materials_module),
        "surface": inspect.getsource(generated_surface_module),
        "characterization": inspect.getsource(characterization_module),
    }
    for name, source in sources.items():
        assert "except Exception" not in source, name
        assert "except BaseException" not in source, name


def test_atoms_decoder_exposes_exact_current_validator() -> None:
    source = inspect.getsource(payloads_module)
    assert "def canonical_atoms_payload" in source
    assert "return None" in inspect.getsource(payloads_module.dict_to_atoms)
    assert "except OptionalDependencyError" not in source
