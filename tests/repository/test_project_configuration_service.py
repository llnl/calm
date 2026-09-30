from __future__ import annotations

import pytest

from calm.project.application.configuration import (
    get_project_configuration,
    set_project_configuration,
)


def test_project_configuration_roundtrip_and_partial_update(
    schema_uow_factory,
) -> None:
    assert get_project_configuration(schema_uow_factory) is None

    created = set_project_configuration(
        schema_uow_factory,
        mlip="model-a",
        calculator_uid_full="calculator:one",
        workflow_defaults={"relaxation": {"fmax": 0.05}},
    )
    assert created == {
        "default_mlip": "model-a",
        "default_calculator_uid_full": "calculator:one",
        "workflow_defaults": {"relaxation": {"fmax": 0.05}},
    }

    updated = set_project_configuration(
        schema_uow_factory,
        workflow_defaults={"energy": {"mode": "single_point"}},
    )
    assert updated == {
        "default_mlip": "model-a",
        "default_calculator_uid_full": "calculator:one",
        "workflow_defaults": {"energy": {"mode": "single_point"}},
    }
    assert get_project_configuration(schema_uow_factory) == updated


def test_project_configuration_rejects_identity_replacement(
    schema_uow_factory,
) -> None:
    set_project_configuration(
        schema_uow_factory,
        mlip="model-a",
        calculator_uid_full="calculator:one",
    )

    with pytest.raises(RuntimeError, match="cannot replace"):
        set_project_configuration(
            schema_uow_factory,
            mlip="model-b",
        )
    with pytest.raises(RuntimeError, match="different calculator identity"):
        set_project_configuration(
            schema_uow_factory,
            calculator_uid_full="calculator:two",
        )

    assert get_project_configuration(schema_uow_factory) == {
        "default_mlip": "model-a",
        "default_calculator_uid_full": "calculator:one",
        "workflow_defaults": None,
    }
