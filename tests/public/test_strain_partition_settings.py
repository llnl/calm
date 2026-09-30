import pytest

from calm import RegistrySettings, StrainPartitionSettings


def test_strain_partition_settings_use_exact_metrics_and_canonical_grid():
    settings = StrainPartitionSettings(
        target_metric="gamma_eV_per_A2",
        alphas=(1.0, 0.5, 0.0, 0.5),
    )
    assert settings.resolve_metric() == "gamma_eV_per_A2"
    assert settings.resolve_alphas() == (0.0, 0.5, 1.0)
    assert settings.to_dict() == {
        "target_metric": "gamma_eV_per_A2",
        "alphas": [0.0, 0.5, 1.0],
    }

    assert (
        StrainPartitionSettings(
            target_metric="potential_energy_density_eV_per_A2"
        ).resolve_metric()
        == "potential_energy_density_eV_per_A2"
    )

    for retired in (
        "gamma",
        "interfacial_energy",
        "potential_energy_density",
        "potential_energy",
        "e_per_a2",
    ):
        with pytest.raises(ValueError, match="Unsupported strain-partition"):
            StrainPartitionSettings(target_metric=retired).validate()


def test_strain_partition_settings_reject_unknown_or_invalid_values():
    with pytest.raises(ValueError, match="Unsupported strain-partition"):
        StrainPartitionSettings(target_metric="automatic").validate()
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        StrainPartitionSettings(target_metric="gamma_eV_per_A2", alphas=(-0.1, 0.5)).validate()
    with pytest.raises(ValueError, match="must not be empty"):
        StrainPartitionSettings(target_metric="gamma_eV_per_A2", alphas=()).validate()


def test_registry_settings_are_fully_operational_for_persisted_refinement():
    settings = RegistrySettings(steps=12, translation_step=0.04, seed=17)
    settings.validate_for_persisted_refinement()
    assert settings.to_dict() == {
        "steps": 12,
        "translation_step": 0.04,
        "seed": 17,
    }
    assert RegistrySettings().operational_translation_step == 0.08


def test_registry_settings_reject_nonfinite_and_inexact_values():
    with pytest.raises(TypeError, match="steps must be an integer"):
        RegistrySettings(steps=1.5).validate()
    with pytest.raises(TypeError, match="steps must be an integer"):
        RegistrySettings(steps=True).validate()
    with pytest.raises(ValueError, match="translation_step must be finite"):
        RegistrySettings(translation_step=float("nan")).validate()
    with pytest.raises(TypeError, match="seed must be an integer"):
        RegistrySettings(seed=2.5).validate()
    with pytest.raises(ValueError, match="seed must be >= 0"):
        RegistrySettings(seed=-1).validate()
