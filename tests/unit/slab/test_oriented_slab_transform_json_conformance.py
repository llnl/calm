from importlib.machinery import ModuleSpec
from pathlib import Path
import importlib.util
import sys
import types

import numpy as np
from oriented_slab_fixtures import current_construction_controls


def _install_fake_ase() -> bool:
    try:
        available = importlib.util.find_spec("ase") is not None
    except ValueError:
        available = "ase" in sys.modules
    if available:
        return False
    ase = types.ModuleType("ase")
    ase.__spec__ = ModuleSpec("ase", loader=None)

    class Atoms:  # pragma: no cover - behavior is irrelevant for these tests.
        pass

    ase.Atoms = Atoms
    sys.modules["ase"] = ase
    return True


_INSERTED_ASE_STUB = _install_fake_ase()
try:
    from calm.serialization.scientific import scientific_json_native as _json_native
    from calm.slab.oriented.transforms import (
        OrientedSlabTransforms,
        to_transforms_payload,
    )
finally:
    if _INSERTED_ASE_STUB:
        sys.modules.pop("ase", None)

ROOT = Path(__file__).resolve().parents[3]


def test_oriented_slab_transform_json_native_preserves_payload_shapes() -> None:
    payload = _json_native(
        {
            "matrix": np.array([[1, 2], [3, 4]], dtype=np.int64),
            "scalar": np.float64(1.25),
            "nested": (np.int64(7), {"flag": True}),
        }
    )

    assert payload == {
        "matrix": [[1, 2], [3, 4]],
        "scalar": 1.25,
        "nested": [7, {"flag": True}],
    }


def test_oriented_slab_transforms_payload_normalizes_extra_values() -> None:
    transforms = OrientedSlabTransforms(
        U=np.eye(3),
        hkl=(1, 1, 0),
        extra={"S_conv_to_surface_col": np.array([[1, 0], [0, 1]], dtype=np.int64)},
    )

    payload = to_transforms_payload(transforms)

    assert payload["S_conv_to_surface_col"] == [[1, 0], [0, 1]]


def test_oriented_slab_transform_json_native_has_single_owner() -> None:
    sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in [
            ROOT / "calm/serialization/scientific.py",
            ROOT / "calm/slab/oriented/transforms.py",
            ROOT / "calm/slab/oriented/builder.py",
        ]
    }

    assert "def scientific_json_native" in sources["scientific.py"]
    assert "def _json_native" not in sources["transforms.py"]
    assert "def _jsonify" not in sources["builder.py"]
    assert "json_native as _json_native" in sources["transforms.py"]
    assert "json_native as _json_native" in sources["builder.py"]



def test_scientific_json_projection_rejects_unsupported_and_nonfinite_values() -> None:
    try:
        _json_native({"bad": object()})
    except TypeError as exc:
        assert "unsupported object" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unsupported scientific provenance was stringified")

    try:
        _json_native({"bad": np.inf})
    except ValueError as exc:
        assert "must be finite" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("non-finite scientific provenance was accepted")

def test_current_transform_parser_rejects_historical_aliases() -> None:
    from calm.slab.oriented.transforms import from_transforms_payload

    aliases = [
        {"schema_version": 1, "hkl": [1, 0, 0], "U": np.eye(3)},
        {"version": 1, "miller": [1, 0, 0], "U": np.eye(3)},
        {"version": 1, "hkl": [1, 0, 0], "U_conv_to_slab": np.eye(3)},
        {"transforms": {"U": np.eye(3)}},
    ]
    for payload in aliases:
        try:
            from_transforms_payload(payload)
        except ValueError as exc:
            assert "Historical" in str(exc) or "missing required" in str(exc)
        else:  # pragma: no cover - explicit assertion without pytest dependency
            raise AssertionError(f"historical payload was accepted: {payload}")


def test_current_transform_parser_requires_exact_version() -> None:
    from calm.slab.oriented.transforms import from_transforms_payload

    current = {
        "version": 1,
        "hkl": [1, 1, 0],
        "U": np.eye(3),
        "construction_controls": current_construction_controls(),
    }
    assert from_transforms_payload(current).payload["version"] == 1

    for version in (0, 2):
        payload = dict(current, version=version)
        try:
            from_transforms_payload(payload)
        except ValueError as exc:
            assert "Unsupported" in str(exc)
        else:  # pragma: no cover
            raise AssertionError(f"unsupported version was accepted: {version}")


def test_atoms_info_writer_validates_current_schema() -> None:
    from types import SimpleNamespace

    from calm.slab.oriented.transforms import (
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
        put_transforms_payload_in_atoms_info,
    )

    atoms = SimpleNamespace(info={})
    payload = {
        "version": 1,
        "hkl": [0, 0, 1],
        "U": np.eye(3),
        "construction_controls": current_construction_controls(),
    }
    put_transforms_payload_in_atoms_info(atoms, payload)
    assert atoms.info[ORIENTED_SLAB_TRANSFORMS_INFO_KEY]["version"] == 1

    try:
        put_transforms_payload_in_atoms_info(
            atoms,
            {"schema_version": 1, "hkl": [0, 0, 1], "U": np.eye(3)},
        )
    except ValueError as exc:
        assert "Historical" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("historical payload was written to Atoms.info")

    try:
        put_transforms_payload_in_atoms_info(
            atoms,
            {"version": 1, "hkl": [0, 0, 1], "U": np.eye(3)},
        )
    except ValueError as exc:
        assert "construction_controls provenance" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("incomplete sidecar payload was written to Atoms.info")


def test_current_transform_parser_rejects_missing_construction_controls() -> None:
    from calm.slab.oriented.transforms import (
        OrientedSlabTransforms,
        from_transforms_payload,
        from_transforms_sidecar_payload,
    )

    payload = {"version": 1, "hkl": [0, 0, 1], "U": np.eye(3)}
    try:
        from_transforms_payload(payload)
    except ValueError as exc:
        assert "construction_controls provenance" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("incomplete current transform payload was accepted")

    restored = from_transforms_sidecar_payload(payload)
    assert "construction_controls" not in restored.payload
    assert OrientedSlabTransforms.from_json(restored.to_json()).payload == {
        "version": 1,
        "hkl": [0, 0, 1],
        "U": np.eye(3).tolist(),
    }


def test_current_transform_parser_validates_bounded_gauge_controls() -> None:
    from calm.slab.oriented.transforms import from_transforms_payload

    payload = {
        "version": 1,
        "hkl": [0, 0, 1],
        "U": np.eye(3),
        "construction_controls": current_construction_controls(),
    }
    payload["construction_controls"]["c_tilt_boundary_policy"] = "not_applied"

    try:
        from_transforms_payload(payload)
    except ValueError as exc:
        assert "does not match c_tilt_enabled" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("malformed current construction controls were accepted")
