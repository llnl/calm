"""Public contract for package-owned tutorial structures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import calm
from calm.structure.tutorials import _tutorial_payload


ROOT = Path(__file__).resolve().parents[2]
RESOURCE_ROOT = ROOT / "calm" / "data" / "tutorials"
EXPECTED = {
    "lif": {"formula": "F4Li4", "n_atoms": 8, "role": "geometry"},
    "li2o": {"formula": "Li8O4", "n_atoms": 12, "role": "geometry"},
    "cu": {"formula": "Cu4", "n_atoms": 4, "role": "ase-emt"},
    "ni": {"formula": "Ni4", "n_atoms": 4, "role": "ase-emt"},
}


def test_tutorial_structure_is_one_top_level_public_boundary() -> None:
    import calm.api as api

    assert "tutorial_structure" in api.PUBLIC_EXPORTS
    assert calm.tutorial_structure is api.tutorial_structure
    assert api._EXPORT_MAP["tutorial_structure"] == (
        "calm.structure.tutorials",
        "tutorial_structure",
    )


def test_packaged_payload_inventory_is_exact_and_current() -> None:
    shipped = {path.stem for path in RESOURCE_ROOT.glob("*.json")}
    assert shipped == set(EXPECTED)

    for name, expected in EXPECTED.items():
        raw = json.loads((RESOURCE_ROOT / f"{name}.json").read_text(encoding="utf-8"))
        payload = _tutorial_payload(name)
        assert payload == raw
        assert len(payload["numbers"]) == expected["n_atoms"]
        assert payload["pbc"] == [True, True, True]
        assert payload["info"]["calm_tutorial_name"] == name
        assert payload["info"]["calm_tutorial_role"] == expected["role"]


def test_tutorial_structure_rejects_unknown_or_non_string_names() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        calm.tutorial_structure(1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Available names: lif, li2o, cu, ni"):
        calm.tutorial_structure("LiF")


def test_tutorial_structure_returns_fresh_ase_atoms() -> None:
    pytest.importorskip("ase")

    for name, expected in EXPECTED.items():
        first = calm.tutorial_structure(name)
        second = calm.tutorial_structure(name)
        assert first is not second
        assert len(first) == expected["n_atoms"]
        assert first.get_chemical_formula() == expected["formula"]
        assert first.pbc.tolist() == [True, True, True]
        first.positions[0, 0] += 1.0
        assert first.positions[0, 0] != second.positions[0, 0]
