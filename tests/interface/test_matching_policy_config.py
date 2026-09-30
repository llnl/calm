from __future__ import annotations

import importlib.util
import sys
from types import ModuleType, SimpleNamespace

import pytest

from calm.interface.config import PrototypeSearchConfig


def _install_optional_import_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    if "ase" not in sys.modules and importlib.util.find_spec("ase") is None:
        ase = ModuleType("ase")

        class Atoms:
            pass

        ase.Atoms = Atoms
        monkeypatch.setitem(sys.modules, "ase", ase)
    if (
        "spglib" not in sys.modules
        and importlib.util.find_spec("spglib") is None
    ):
        spglib = ModuleType("spglib")
        spglib.__version__ = "stage9-test-stub"
        monkeypatch.setitem(sys.modules, "spglib", spglib)


def test_authoritative_search_forwards_explicit_pair_identity_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_optional_import_stubs(monkeypatch)

    import calm.interface.matching.search as matching

    config = PrototypeSearchConfig(
        k_max=1,
        surface_symmetry_mode="identity_only",
        pair_symmetry_policy="proper",
        correspondence_orientation="all",
        identify_material_exchange=True,
        correspondence_entry_limit=37,
    )
    captured: dict[str, object] = {}

    def _enumerate(*_args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        matching._surface_symmetry,
        "resolve_surface_pointgroup_2d",
        lambda *_args, **_kwargs: SimpleNamespace(
            operations=(),
            provenance=None,
        ),
    )
    module = ModuleType("calm.interface.matching._orchestrator")
    module.enumerate_coupled_match_classes_core = _enumerate
    monkeypatch.setitem(
        sys.modules,
        "calm.interface.matching._orchestrator",
        module,
    )

    result = matching.search_primitive_match_classes(object(), object(), config)

    assert result.match_classes == ()
    assert captured["pair_symmetry_policy"] == "proper"
    assert captured["correspondence_orientation"] == "all"
    assert captured["identify_material_exchange"] is True
    assert captured["correspondence_entry_limit"] == 37
