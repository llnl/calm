import json

import pytest

from calm.project.infrastructure.db.payload_helpers import (
    extract_canonical_tilt_metadata,
    payload_canonical_json_and_hash,
)
from calm.serialization.regression import sha256_hex


def test_payload_ordering_and_hash() -> None:
    payload = {"b": 1, "a": 2}
    payload_json, phash = payload_canonical_json_and_hash(payload)
    assert payload_json == '{"a":2,"b":1}'
    assert json.loads(payload_json) == payload
    assert phash == sha256_hex(payload_json)


def test_payload_float_precision_is_not_rounded() -> None:
    value = 0.1234567890123456
    payload_json, phash = payload_canonical_json_and_hash({"value": value})
    assert json.loads(payload_json)["value"] == value
    assert phash == sha256_hex(payload_json)


def test_none_payload() -> None:
    payload_json, phash = payload_canonical_json_and_hash(None)
    assert payload_json == "{}"
    assert phash == sha256_hex("{}")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"x": {1, 2, 3}}, "JSON-native"),
        ({"x": (1, 2, 3)}, "JSON-native"),
        ({1: "value"}, "keys must be strings"),
        ({"x": float("nan")}, "must be finite"),
    ],
)
def test_coercive_or_non_finite_payload_is_rejected(
    payload: dict,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        payload_canonical_json_and_hash(payload)


def test_tilt_metadata_uses_only_current_canonical_location() -> None:
    tilt = {"tilt_xy": [0.0, 0.0]}
    canonical = {"atoms": {"info": {"calm:tilt": tilt}}}
    assert extract_canonical_tilt_metadata(canonical) == tilt
    assert extract_canonical_tilt_metadata({"atoms": {"calm:tilt": tilt}}) is None
    assert extract_canonical_tilt_metadata({"calm:tilt": tilt}) is None
