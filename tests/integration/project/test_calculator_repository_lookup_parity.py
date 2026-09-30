from __future__ import annotations

import json

import pytest

from calm.calculators.exceptions import CalculatorSpecError
from calm.calculators.spec import CalculatorSpec
from calm.project.infrastructure.db.tables import calculators as calculators_t


def test_calculator_repository_roundtrips_canonical_spec(schema_uow_factory) -> None:
    spec = CalculatorSpec(
        family="f",
        model="m",
        version="2",
        source="unit-test",
        device="cpu",
        dtype="float64",
        options={"a": 1},
    ).to_dict()
    uow = schema_uow_factory()
    with uow as entered:
        entered.connection.execute(
            calculators_t.insert().values(
                uid_full="calc:1",
                id_short="c_abcd",
                family="f",
                model="m",
                device="cpu",
                spec_json=json.dumps(spec),
            )
        )

    with uow as entered:
        resolved = entered.ids.resolve("c_abcd", expected_tag="c")
        calculator = entered.calculators.get_by_uid_full(resolved)

    assert calculator is not None
    assert calculator.spec == spec


def test_calculator_repository_rejects_noncurrent_spec(schema_uow_factory) -> None:
    uow = schema_uow_factory()
    with uow as entered:
        entered.connection.execute(
            calculators_t.insert().values(
                uid_full="calc:legacy",
                id_short="c_legacy",
                family="f",
                model="m",
                device="cpu",
                spec_json=json.dumps({"a": 1}),
            )
        )

    with pytest.raises(CalculatorSpecError):
        with uow as entered:
            entered.calculators.get_by_uid_full("calc:legacy")
