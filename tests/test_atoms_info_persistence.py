import json

import numpy as np
import pytest
from ase import Atoms

from calm.slab.oriented.transforms import ORIENTED_SLAB_TRANSFORMS_INFO_KEY
from calm.structure.payloads import dict_to_atoms
from calm.structure.payloads import atoms_to_dict


def test_atoms_to_dict_sanitizes_dataclasses_and_payload_carriers() -> None:
    """CALM provenance objects should persist cleanly through JSON and atoms dicts.

    This test guards the *generic* serialization layer (atoms_to_dict) so that
    future provenance objects can be stored in ``Atoms.info`` without
    introducing hard-to-debug JSON serialization failures.
    """

    # Local import to avoid adding a global test dependency.
    import dataclasses

    @dataclasses.dataclass
    class _Payload:
        a: int

        def to_payload(self) -> dict[str, int]:
            return {"a": self.a}

    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=np.diag([1.0, 1.0, 1.0]), pbc=True)
    atoms.info["calm_payload"] = _Payload(a=7)

    d = atoms_to_dict(atoms)
    # Must be JSON-serializable.
    json.dumps(d)

    assert d["info"]["calm_payload"] == {"a": 7}

    atoms_rt = dict_to_atoms(d)
    assert atoms_rt.info["calm_payload"] == {"a": 7}


def test_atoms_to_dict_persists_only_calm_info_keys() -> None:
    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3), pbc=True)
    atoms.info["calm_test"] = {"a": 1, "b": [1, 2, 3]}
    atoms.info["not_calm"] = {"x": 1}

    d = atoms_to_dict(atoms)

    assert "info" in d
    assert "calm_test" in d["info"]
    assert "not_calm" not in d["info"]

    # Must be JSON-serializable for workspace persistence.
    json.dumps(d)

    atoms_rt = dict_to_atoms(d)
    assert atoms_rt.info.get("calm_test") == {"a": 1, "b": [1, 2, 3]}
    assert "not_calm" not in atoms_rt.info


def test_oriented_slab_transforms_roundtrip_through_atoms_dict() -> None:
    from calm.bulk.bulk import Bulk
    from calm.slab.oriented.model import build_oriented_slab

    # Simple cubic conventional cell.
    conv = Atoms("Al", positions=[[0.0, 0.0, 0.0]], cell=np.diag([3.0, 3.0, 3.0]), pbc=True)

    res = build_oriented_slab(
        Bulk(conv),
        hkl=(0, 0, 1),
        layers=1,
        vacuum=None,
        reduce_inplane=False,
        reduce_c_tilt=False,
        orthogonalize_c=False,
    )

    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in res.slab.info

    d = atoms_to_dict(res.slab)
    assert "info" in d
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in d["info"]

    slab_rt = dict_to_atoms(d)
    assert ORIENTED_SLAB_TRANSFORMS_INFO_KEY in slab_rt.info


def test_dict_to_atoms_rejects_ase_todict_schema() -> None:
    """Only CALM's current ``scaled_positions`` schema is readable."""

    payload = {
        "numbers": [13, 13],
        "positions": [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        "cell": np.diag([3.0, 3.0, 3.0]).tolist(),
        "pbc": [True, True, True],
    }

    with pytest.raises(ValueError, match="scaled_positions"):
        dict_to_atoms(payload)


def test_dict_to_atoms_requires_current_pbc_field() -> None:
    payload = {
        "numbers": [13],
        "scaled_positions": [[0.0, 0.0, 0.0]],
        "cell": np.diag([3.0, 3.0, 3.0]).tolist(),
    }

    with pytest.raises(ValueError, match="pbc"):
        dict_to_atoms(payload)


def test_atoms_to_dict_propagates_broken_provenance_adapter() -> None:
    class _BrokenPayload:
        def to_payload(self):
            raise RuntimeError("payload conversion failed")

    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3), pbc=True)
    atoms.info["calm_bad"] = _BrokenPayload()

    with pytest.raises(RuntimeError, match="payload conversion failed"):
        atoms_to_dict(atoms)


def test_atoms_to_dict_rejects_opaque_and_nonfinite_calm_provenance() -> None:
    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3), pbc=True)
    atoms.info["calm_bad"] = object()
    with pytest.raises(TypeError, match="unsupported object"):
        atoms_to_dict(atoms)

    atoms.info["calm_bad"] = float("nan")
    with pytest.raises(ValueError, match="must be finite"):
        atoms_to_dict(atoms)


def test_atoms_to_dict_rejects_provenance_cycles() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    atoms = Atoms("H", positions=[[0.0, 0.0, 0.0]], cell=np.eye(3), pbc=True)
    atoms.info["calm_bad"] = cyclic

    with pytest.raises(ValueError, match="reference cycle"):
        atoms_to_dict(atoms)
