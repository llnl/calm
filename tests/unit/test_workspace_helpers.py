from calm.project.runtime.helpers import merge_payload


def test_merge_payload_preserves_payload_and_adds_missing_label() -> None:
    assert merge_payload(payload={"a": 1}, label="L") == {"a": 1, "label": "L"}
    assert merge_payload(payload={"label": "stored"}, label="ignored") == {
        "label": "stored"
    }
    assert merge_payload() is None
