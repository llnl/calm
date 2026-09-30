import json

import pytest

from calm.calculators.exceptions import CalculatorSpecError
from calm.calculators.spec import CalculatorSpec


def test_calculator_spec_roundtrip_and_fingerprint_stable():
    spec = CalculatorSpec(
        family="mace",
        model="medium-mpa-0",
        device="cpu",
        options={"stress": True, "cutoffs": [1.0, 2.0, 3.0]},
    )

    payload = spec.to_json()
    data = json.loads(payload)
    assert data["family"] == "mace"
    assert data["model"] == "medium-mpa-0"
    assert data["device"] == "cpu"

    spec2 = CalculatorSpec.from_json(payload)
    assert spec2.to_json() == payload
    assert spec2.fingerprint() == spec.fingerprint()


def test_calculator_spec_options_are_immutable_from_outside():
    options = {"stress": True, "nested": {"a": 1}}
    spec = CalculatorSpec(family="mace", model="medium-mpa-0", options=options)

    # Mutating original dict should not affect spec
    options["stress"] = False
    options["nested"]["a"] = 2

    assert spec.options_dict()["stress"] is True
    assert spec.options_dict()["nested"]["a"] == 1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_calculator_spec_rejects_nonfinite_options(value: float) -> None:
    with pytest.raises(CalculatorSpecError, match="non-finite float"):
        CalculatorSpec(
            family="mace",
            model="medium-mpa-0",
            options={"cutoff": value},
        )


@pytest.mark.parametrize("options", [None, [], ""])
def test_calculator_spec_from_dict_rejects_nonmapping_options(options) -> None:
    with pytest.raises(CalculatorSpecError, match="options must be a mapping"):
        CalculatorSpec.from_dict(
            {
                "schema_version": 1,
                "family": "mace",
                "model": "medium-mpa-0",
                "options": options,
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("family", None),
        ("family", 7),
        ("model", None),
        ("model", 7),
        ("device", 7),
        ("version", 7),
    ],
)
def test_calculator_spec_rejects_nonstring_text_fields(
    field: str,
    value,
) -> None:
    payload = {
        "schema_version": 1,
        "family": "mace",
        "model": "medium-mpa-0",
        "options": {},
    }
    payload[field] = value

    with pytest.raises(CalculatorSpecError, match=field):
        CalculatorSpec.from_dict(payload)


@pytest.mark.parametrize("schema_version", [True, 1.0, "1"])
def test_calculator_spec_requires_exact_integer_schema_version(
    schema_version,
) -> None:
    with pytest.raises(CalculatorSpecError, match="schema_version"):
        CalculatorSpec.from_dict(
            {
                "schema_version": schema_version,
                "family": "mace",
                "model": "medium-mpa-0",
                "options": {},
            }
        )


def test_calculator_spec_rejects_unknown_fields() -> None:
    with pytest.raises(CalculatorSpecError, match="unsupported field"):
        CalculatorSpec.from_dict(
            {
                "schema_version": 1,
                "family": "mace",
                "model": "medium-mpa-0",
                "options": {},
                "backend_alias": "other",
            }
        )
