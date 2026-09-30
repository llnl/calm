"""Regression coverage for exact strain-scan defaults."""

from calm.project.application.followups.strain_scan import (
    StrainPartitionScanOrchestrator,
)


def test_strain_scan_default_metric_uses_exact_current_name() -> None:
    payload = StrainPartitionScanOrchestrator._normalize_payload(
        None,
        [0.0, 0.5, 1.0],
    )

    assert payload == {
        "alphas": [0.0, 0.5, 1.0],
        "target_metric": "potential_energy_density_eV_per_A2",
    }
