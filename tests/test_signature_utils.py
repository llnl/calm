from __future__ import annotations

import json

import numpy as np


def test_deterministic_json_sorts_keys_and_normalizes_numpy_types() -> None:
    from calm.serialization.regression import deterministic_json

    payload = {
        "b": np.array([1, 2, 3], dtype=int),
        "a": {"y": np.float64(1.23456789012345), "x": np.int64(7)},
    }

    s = deterministic_json(payload, float_ndigits=8)

    # Must be valid JSON.
    obj = json.loads(s)
    assert obj["a"]["x"] == 7
    assert obj["b"] == [1, 2, 3]
    # Float rounding controlled by float_ndigits.
    assert obj["a"]["y"] == 1.23456789

    # Determinism: reordering keys should not change output.
    payload2 = {"a": payload["a"], "b": payload["b"]}
    assert deterministic_json(payload2, float_ndigits=8) == s


def test_fingerprint_json_is_stable_for_equivalent_payloads() -> None:
    from calm.serialization.regression import fingerprint_json

    p1 = {"x": 1, "y": [1, 2, 3]}
    p2 = {"y": [1, 2, 3], "x": 1}

    assert fingerprint_json(p1) == fingerprint_json(p2)
