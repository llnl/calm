from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.interface.config import RegistrySearchConfig
from calm.project.application.followups.registry_search import _registry_target_state
from calm.project.domain.models import DerivedInterface


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_steps": 1.5},
        {"step_scale": float("nan")},
        {"temperature": -1.0},
        {"seed": -1},
        {"z_bounds": (-1.0, 2.0)},
        {"z_bounds": (2.0, 1.0)},
        {"p_translate": 1.1},
        {"keep_trace": 1},
    ],
)
def test_registry_search_config_rejects_invalid_controls(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        RegistrySearchConfig(**kwargs)


def test_registry_search_config_normalizes_valid_numeric_controls() -> None:
    config = RegistrySearchConfig(
        n_steps=4,
        step_scale=0.2,
        temperature=0.1,
        seed=7,
        z_bounds=(1, 3),
        z_step_scale=0.3,
        p_translate=0.75,
        keep_trace=True,
    )

    assert config.n_steps == 4
    assert config.z_bounds == (1.0, 3.0)
    assert config.seed == 7


def test_registry_target_state_reads_exact_current_interface_state() -> None:
    interface = DerivedInterface(
        uid_full="iface:seed",
        id_short="i_seed",
        prototype_uid_full="proto:seed",
        spec={
            "schema": "calm.derived_interface",
            "version": 1,
            "prototype": "proto:seed",
            "stage": "strain_partitioned",
            "strain_alpha": 0.25,
            "registry_shift_frac_a": [0.1, 0.8],
            "z_padding": 2.25,
            "vacuum": 12.0,
            "params": {},
        },
    )
    uow = SimpleNamespace(
        derived_interfaces=SimpleNamespace(
            get_by_uid_full=lambda _uid: interface,
        )
    )

    state = _registry_target_state(
        uow,
        target_uid="iface:seed",
        target_kind="interface",
    )

    assert state.translation == (0.1, 0.8)
    assert state.alpha == 0.25
    assert state.z_padding == 2.25
    assert state.vacuum_padding == 12.0


def test_registry_target_state_rejects_unknown_target_kind() -> None:
    uow = SimpleNamespace(derived_interfaces=SimpleNamespace())

    with pytest.raises(ValueError, match="target_kind"):
        _registry_target_state(
            uow,
            target_uid="target:1",
            target_kind="candidate",
        )
