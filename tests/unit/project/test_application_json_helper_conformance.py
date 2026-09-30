"""Guardrails for application JSON representation helper ownership."""

from __future__ import annotations

import inspect

import numpy as np

from calm.project.application._json import json_native
import calm.project.application.derived_interfaces as derived_interfaces


def test_application_json_native_normalizes_nested_payloads() -> None:
    payload = {
        "array": np.array([[1, 2], [3, 4]]),
        "scalar": np.float64(1.25),
        "tuple": (np.int64(5), {"k": np.array([6, 7])}),
    }

    assert json_native(payload) == {
        "array": [[1, 2], [3, 4]],
        "scalar": 1.25,
        "tuple": [5, {"k": [6, 7]}],
    }


def test_derived_interface_uses_application_json_native_owner() -> None:
    source = inspect.getsource(derived_interfaces)

    assert "from ._json import json_native" in source
    assert '"params": json_native(raw_params)' in source
    assert "strain_state_from_current_object(" in source
    assert "def _jsonify" not in source


def test_application_json_native_propagates_conversion_failures() -> None:
    class BrokenArrayCarrier:
        def tolist(self):
            raise RuntimeError("conversion failed")

    import pytest

    with pytest.raises(RuntimeError, match="conversion failed"):
        json_native({"value": BrokenArrayCarrier()})


def test_application_json_native_rejects_unsupported_and_nonfinite_values() -> None:
    import pytest

    with pytest.raises(TypeError, match="unsupported object"):
        json_native({"value": object()})
    with pytest.raises(ValueError, match="must be finite"):
        json_native({"value": float("nan")})
