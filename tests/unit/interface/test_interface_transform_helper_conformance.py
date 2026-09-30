from pathlib import Path

import numpy as np
import pytest

from calm.interface.building._kernel import _embed_2x2_in_3x3


INTERFACE_DIR = Path(__file__).resolve().parents[3] / "calm" / "interface"


def test_embed_2x2_in_3x3_is_single_interface_owner() -> None:
    sources = {
        path.relative_to(INTERFACE_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in INTERFACE_DIR.rglob("*.py")
        if path.name != "__init__.py"
    }

    owners = [
        name
        for name, source in sources.items()
        if "def _embed_2x2_in_3x3" in source
    ]
    assert owners == ["building/_kernel.py"]

    references = {
        name for name, source in sources.items() if "_embed_2x2_in_3x3" in source
    }
    assert references == {
        "building/_kernel.py",
        "energy/_kernel.py",
        "pipeline.py",
    }


def test_embed_2x2_in_3x3_preserves_integer_transform_shape_and_dtype() -> None:
    matrix = _embed_2x2_in_3x3([[2, 1], [0, 3]], dtype="int")

    assert matrix.dtype == np.dtype(int)
    np.testing.assert_array_equal(matrix, np.array([[2, 1, 0], [0, 3, 0], [0, 0, 1]], dtype=int))


def test_embed_2x2_in_3x3_preserves_float_rotation_block() -> None:
    matrix = _embed_2x2_in_3x3([[0.5, -0.25], [0.25, 0.5]], dtype="float")

    assert matrix.dtype == np.dtype(float)
    np.testing.assert_allclose(matrix, np.array([[0.5, -0.25, 0.0], [0.25, 0.5, 0.0], [0.0, 0.0, 1.0]]))


def test_embed_2x2_in_3x3_rejects_non_2x2_inputs() -> None:
    with pytest.raises(ValueError, match="Expected 2x2 matrix"):
        _embed_2x2_in_3x3([[1, 2, 3], [4, 5, 6]], dtype="int")


def test_embed_2x2_in_3x3_rejects_unsupported_dtype_contracts() -> None:
    with pytest.raises(ValueError, match="dtype must be"):
        _embed_2x2_in_3x3([[1, 0], [0, 1]], dtype="complex")
