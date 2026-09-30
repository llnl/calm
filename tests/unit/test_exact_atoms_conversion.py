from __future__ import annotations

from types import ModuleType, SimpleNamespace
import sys

import pytest

from calm.public.records.generated_surface import GeneratedSurface
from calm.public.inputs.materials import Material
from calm.structure.characterization import (
    canonical_characterization_payload,
    material_characterization_data,
    surface_geometry_projection,
)
from calm.structure.payloads import canonical_atoms_payload, dict_to_atoms


def _payload() -> dict:
    return {
        "numbers": [1],
        "cell": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "scaled_positions": [[0.0, 0.0, 0.0]],
        "pbc": [True, True, True],
        "info": {"calm:test": {"value": 1}},
    }


def test_current_atoms_payload_is_exact() -> None:
    assert canonical_atoms_payload(_payload()) == _payload()

    with pytest.raises(ValueError, match="unsupported field"):
        canonical_atoms_payload({**_payload(), "positions": [[0.0, 0.0, 0.0]]})
    with pytest.raises(ValueError, match="scaled_positions length"):
        canonical_atoms_payload({**_payload(), "scaled_positions": []})
    with pytest.raises(TypeError, match="pbc values must be booleans"):
        canonical_atoms_payload({**_payload(), "pbc": [1, 1, 1]})
    with pytest.raises(ValueError, match="CALM-owned"):
        canonical_atoms_payload({**_payload(), "info": {"user": 1}})


def test_dict_to_atoms_returns_none_only_for_absence() -> None:
    assert dict_to_atoms(None) is None
    with pytest.raises(TypeError, match="mapping or None"):
        dict_to_atoms("not-a-payload")
    with pytest.raises(ValueError, match="scaled_positions"):
        dict_to_atoms(
            {
                "numbers": [1],
                "cell": [[1.0, 0.0, 0.0]] * 3,
                "positions": [[0.0, 0.0, 0.0]],
                "pbc": [True, True, True],
            }
        )



def test_exact_payload_decodes_with_available_ase(monkeypatch) -> None:
    class FakeAtoms:
        def __init__(self, *, numbers, cell, scaled_positions, pbc):
            self.numbers = numbers
            self.cell = cell
            self.scaled_positions = scaled_positions
            self.pbc = pbc
            self.info = {}

    module = ModuleType("ase")
    module.Atoms = FakeAtoms
    monkeypatch.setitem(sys.modules, "ase", module)

    atoms = dict_to_atoms(_payload())
    assert atoms.numbers == [1]
    assert atoms.info == {"calm:test": {"value": 1}}

def test_public_material_rejects_malformed_present_atoms() -> None:
    with pytest.raises(ValueError, match="scaled_positions"):
        Material.from_workspace(
            {
                "uid_full": "bulk:v2:test",
                "id_short": "b_test",
                "label": "bad",
                "payload": {
                    "atoms": {
                        "numbers": [1],
                        "cell": [[1.0, 0.0, 0.0]] * 3,
                        "positions": [[0.0, 0.0, 0.0]],
                        "pbc": [True, True, True],
                    }
                },
            }
        )


def test_generated_surface_propagates_decoder_and_object_errors() -> None:
    surface = GeneratedSurface(
        id_short="s_test",
        label=None,
        material="X",
        miller=(0, 0, 1),
        natoms=1,
        area=1.0,
        payload={
            "structure": {
                "atoms": {
                    "numbers": [1],
                    "cell": [[1.0, 0.0, 0.0]] * 3,
                    "positions": [[0.0, 0.0, 0.0]],
                    "pbc": [True, True, True],
                }
            }
        },
    )
    with pytest.raises(ValueError, match="scaled_positions"):
        surface.to_ase()

    class Broken:
        def to_ase(self):
            raise RuntimeError("decoder failed")

    broken = GeneratedSurface(
        id_short="s_broken",
        label=None,
        material="X",
        miller=(0, 0, 1),
        natoms=None,
        area=None,
        _object=Broken(),
    )
    with pytest.raises(RuntimeError, match="decoder failed"):
        broken.to_ase()


def test_characterization_rejects_malformed_present_atoms() -> None:
    malformed = SimpleNamespace(
        get_chemical_symbols=lambda: ["H"],
        get_cell=lambda: [[1.0, 0.0], [0.0, 1.0]],
        get_chemical_formula=lambda **kwargs: "H",
    )
    with pytest.raises(ValueError, match=r"shape \(3, 3\)"):
        material_characterization_data(malformed)

    bad_surface = SimpleNamespace(
        get_cell=lambda: [[1.0, 0.0, 0.0]] * 3,
        get_positions=lambda: [[0.0, 0.0]],
    )
    with pytest.raises(ValueError, match="positive"):
        surface_geometry_projection(bad_surface)


def test_current_characterization_contract_is_required() -> None:
    with pytest.raises(ValueError, match="requires schema"):
        canonical_characterization_payload({}, kind="material")
    with pytest.raises(ValueError, match="complete v1"):
        canonical_characterization_payload(
            {
                "schema": "calm.material_characterization.v1",
                "contract": {"policy": "wrong"},
                "provenance": {},
            },
            kind="material",
        )

    material = Material(
        name="bad",
        label="bad",
        atoms=None,
        metadata={"characterization": {"schema": "old"}},
    )
    with pytest.raises(ValueError, match="requires schema"):
        material.characterize()


def test_current_atoms_payload_rejects_non_json_info_values() -> None:
    with pytest.raises(TypeError, match="unsupported object"):
        canonical_atoms_payload({**_payload(), "info": {"calm_bad": object()}})
    with pytest.raises(ValueError, match="must be finite"):
        canonical_atoms_payload(
            {**_payload(), "info": {"calm_bad": float("nan")}}
        )
