from __future__ import annotations

from calm.public.projections.atoms import (
    _as_mapping,
    actual_natoms_from_atoms,
    compact_calculator,
    extract_atoms_like,
    reduced_formula_from_atoms,
)


def _atoms_payload() -> dict:
    return {
        "numbers": [1, 1, 8],
        "cell": [[3.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 3.0]],
        "scaled_positions": [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.25, 0.25, 0.25],
        ],
        "pbc": [True, True, True],
    }


def test_compact_calculator_from_mapping():
    val = {"family": "GRACE", "model": "1L"}
    assert compact_calculator(val) == "GRACE:1L"


def test_as_mapping_on_dataclass_like():
    class D:
        def to_dict(self):
            return {"a": 1}

    assert _as_mapping(D()) == {"a": 1}


def test_extract_atoms_like_from_current_payload():
    atoms = _atoms_payload()
    payload = {"payload": {"atoms": atoms}}
    assert extract_atoms_like(payload) == atoms


def test_actual_natoms_and_mapping_formula_policy():
    atoms_like = _atoms_payload()
    assert actual_natoms_from_atoms(atoms_like) == 3
    assert reduced_formula_from_atoms(atoms_like) is None
