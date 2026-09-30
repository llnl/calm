from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.project.domain.contracts.relaxed_reference import (
    RELAXED_SURFACE_PROTOCOL,
    canonical_surface_partition,
    canonical_surface_relaxation_settings,
    validate_relaxed_surface_summary,
)
from calm.project.application.followups.reference_energy import (
    _authoritative_interface_area,
    _center_surface_in_fixed_cell,
    _fixed_cell_relaxed_interface_context,
    _reference_step_count,
)


class _Atoms:
    def __init__(self, scaled, numbers, cell=None, pbc=None):
        self._scaled = np.asarray(scaled, dtype=float)
        self.numbers = np.asarray(numbers, dtype=int)
        self.cell = np.asarray(cell if cell is not None else np.diag([2.0, 3.0, 10.0]))
        self.pbc = np.asarray(pbc if pbc is not None else [True, True, True])
        self.info = {}

    def __len__(self):
        return len(self.numbers)

    def __getitem__(self, item):
        return _Atoms(
            self._scaled[item],
            self.numbers[item],
            cell=self.cell.copy(),
            pbc=self.pbc.copy(),
        )

    def copy(self):
        return _Atoms(
            self._scaled.copy(),
            self.numbers.copy(),
            cell=self.cell.copy(),
            pbc=self.pbc.copy(),
        )

    def get_scaled_positions(self, wrap=False):
        values = self._scaled.copy()
        return np.mod(values, 1.0) if wrap else values

    def set_scaled_positions(self, value):
        self._scaled = np.asarray(value, dtype=float)

    def get_cell(self):
        return self.cell.copy()

    def get_atomic_numbers(self):
        return self.numbers.copy()


def _source_relaxation_params(**overrides):
    values = {
        "scientific_authority": "calculator_backed",
        "relaxation_backend": "real",
        "relaxation_settings": {
            "fmax": 0.05,
            "steps": 20,
            "relax_cell": False,
        },
        "protocol": "ionic_positions_v1",
        "source_run_uid": "run:1",
        "source_followup_uid": "followup:1",
        "final_energy_eV": -1.0,
        "n_steps": 8,
        "max_steps": 20,
        "fmax_eV_per_A": 0.05,
        "max_force_eV_per_A": 0.03,
        "max_optimizer_residual": 0.03,
        "optimizer_reported_converged": True,
        "residual_satisfied": True,
    }
    values.update(overrides)
    return values


def test_surface_relaxation_controls_are_fixed_cell_and_exact() -> None:
    controls = canonical_surface_relaxation_settings(
        {"fmax": 0.03, "steps": 20, "relax_cell": False}
    )
    assert controls == {
        "protocol": RELAXED_SURFACE_PROTOCOL,
        "optimizer": "BFGS",
        "fmax": 0.03,
        "steps": 20,
        "relax_cell": False,
    }
    with pytest.raises(ValueError, match="fixed-cell"):
        canonical_surface_relaxation_settings({"relax_cell": True})


def test_reference_step_count_accepts_zero_only_for_relaxed_surfaces() -> None:
    assert _reference_step_count(0, relaxed_surface=True) == 0
    assert _reference_step_count(8, relaxed_surface=True) == 8
    assert _reference_step_count(8, relaxed_surface=False) == 8

    with pytest.raises(ValueError, match="positive integer"):
        _reference_step_count(0, relaxed_surface=False)
    with pytest.raises(ValueError, match="nonnegative integer"):
        _reference_step_count(-1, relaxed_surface=True)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"n_total": 4, "n_side_a": 2, "n_side_b": 2}, None),
        ({"n_total": 4, "n_side_a": 1, "n_side_b": 2}, "does not match"),
        ({"n_total": 1, "n_side_a": 1, "n_side_b": 0}, "at least one atom"),
    ],
)
def test_surface_partition_is_ordered_and_complete(values, message) -> None:
    if message is None:
        assert canonical_surface_partition(**values) == (2, 2)
    else:
        with pytest.raises(ValueError, match=message):
            canonical_surface_partition(**values)


def test_periodic_surface_centering_preserves_cell_and_compacts_cluster() -> None:
    atoms = _Atoms(
        [[0.1, 0.2, 0.96], [0.2, 0.3, 0.02], [0.3, 0.4, 0.05]],
        [13, 13, 13],
    )
    centered = _center_surface_in_fixed_cell(atoms)
    assert np.array_equal(centered.cell, atoms.cell)
    z = np.sort(centered.get_scaled_positions()[:, 2])
    assert z[-1] - z[0] == pytest.approx(0.09)
    assert 0.5 * (z[0] + z[-1]) == pytest.approx(0.5)


def test_relaxed_interface_context_requires_calculator_backed_fixed_cell() -> None:
    interface = SimpleNamespace(
        stage="relaxed",
        params=_source_relaxation_params(),
    )
    context = _fixed_cell_relaxed_interface_context(interface)
    assert context["source_relaxation_run_uid_full"] == "run:1"
    assert context["source_relaxation_convergence_certificate"]["converged"]

    interface.params["scientific_authority"] = "synthetic_test_only"
    with pytest.raises(ValueError, match="calculator-backed"):
        _fixed_cell_relaxed_interface_context(interface)

    interface.params = _source_relaxation_params(
        residual_satisfied=False,
    )
    with pytest.raises(ValueError, match="convergence certificate"):
        _fixed_cell_relaxed_interface_context(interface)


def test_relaxed_surface_summary_requires_matching_convergence_certificate() -> None:
    settings = {"fmax": 0.04, "steps": 12, "relax_cell": False}
    summary = {
        "protocol": RELAXED_SURFACE_PROTOCOL,
        "scientific_authority": "calculator_backed",
        "optimizer": "ASE.BFGS",
        "converged": True,
        "relax_cell": False,
        "fmax": 0.04,
        "steps": 12,
        "n_steps": 8,
        "max_force_eV_per_A": 0.03,
        "termination_reason": "converged",
    }
    assert validate_relaxed_surface_summary(summary, settings=settings) == summary
    summary["converged"] = False
    with pytest.raises(ValueError, match="convergence"):
        validate_relaxed_surface_summary(summary, settings=settings)
    summary["converged"] = "true"
    with pytest.raises(ValueError, match="convergence"):
        validate_relaxed_surface_summary(summary, settings=settings)


def test_authoritative_interface_area_uses_exact_cell_plane() -> None:
    atoms = _Atoms([[0.0, 0.0, 0.5]], [13], cell=[[2, 0, 0], [1, 3, 0], [0, 0, 9]])
    assert _authoritative_interface_area(atoms) == pytest.approx(6.0)


def test_relaxed_surface_targets_are_cleaved_from_final_interface() -> None:
    from calm.project.application.followups.reference_energy import (
        _prepare_relaxed_surface_targets,
    )

    expected_a = _Atoms([[0.0, 0.0, 0.1]], [13])
    expected_b = _Atoms([[0.0, 0.0, 0.7], [0.5, 0.5, 0.8]], [29, 29])
    final_interface = _Atoms(
        [[0.0, 0.0, 0.12], [0.0, 0.0, 0.72], [0.5, 0.5, 0.82]],
        [13, 29, 29],
    )
    interface = SimpleNamespace(
        stage="relaxed",
        params=_source_relaxation_params(
            source_run_uid="run:relax",
            source_followup_uid="followup:relax",
        ),
    )
    targets = _prepare_relaxed_surface_targets(
        interface=interface,
        prototype_uid_full="proto:1",
        interface_uid_full="iface:1",
        interface_atoms_loader=lambda uid: final_interface,
        expected_surface_a=expected_a,
        expected_surface_b=expected_b,
        reconstructed_area_A2=6.0,
        shared={"formula_id": "work_of_adhesion_relaxed_surfaces"},
    )
    assert [target.reference_kind for target in targets] == [
        "relaxed_surface_a",
        "relaxed_surface_b",
    ]
    assert [len(target.atoms) for target in targets] == [1, 2]
    assert all(
        target.metadata["reference_area_A2"] == pytest.approx(6.0)
        for target in targets
    )
    assert targets[0].metadata["source_relaxation_run_uid_full"] == "run:relax"


def test_relaxed_reference_compatibility_persists_protocol_and_source() -> None:
    from calm.project.application.followups.thermodynamics import (
        _reference_calculator_compatibility,
    )

    raw = {
        "backend": {
            "name": "real",
            "identity": {"name": "real", "calculator": "shared"},
            "settings": {"mode": "single_point"},
        },
        "interface_area_A2": 6.0,
    }
    references = {
        "metadata": {
            "compatibility_source": "calculated_reference_workflow",
            "formula_id": "work_of_adhesion_relaxed_surfaces",
            "energy_backend": "real",
            "backend_identity": {"name": "real", "calculator": "shared"},
            "energy_settings": {"mode": "single_point"},
            "reference_area_A2": 6.0,
            "reference_protocol": RELAXED_SURFACE_PROTOCOL,
            "reference_relaxation": {
                "fmax": 0.05,
                "steps": 500,
                "relax_cell": False,
            },
            "reference_relaxation_engine": {
                "algorithm": "ase_bfgs_fixed_cell_surface_relaxation_v1",
                "optimizer": "ASE.BFGS",
                "software_versions": {
                    "ase": "test",
                    "numpy": "test",
                    "scipy": "test",
                },
            },
            "source_interface_structure_fingerprint": "sha256:source",
        }
    }
    result = _reference_calculator_compatibility(raw, references)
    assert result["status"] == "verified"
    relaxation = result["reference"]["relaxation"]
    assert relaxation["protocol"] == RELAXED_SURFACE_PROTOCOL
    assert relaxation["engine"]["optimizer"] == "ASE.BFGS"
    assert relaxation["source_interface_structure_fingerprint"] == "sha256:source"


def test_relaxed_reference_compatibility_rejects_missing_protocol() -> None:
    from calm.project.application.followups.thermodynamics import (
        _reference_calculator_compatibility,
    )

    raw = {
        "backend": {
            "name": "real",
            "identity": {"name": "real", "calculator": "shared"},
            "settings": {"mode": "single_point"},
        },
        "interface_area_A2": 6.0,
    }
    references = {
        "metadata": {
            "compatibility_source": "calculated_reference_workflow",
            "formula_id": "work_of_adhesion_relaxed_surfaces",
            "energy_backend": "real",
            "backend_identity": {"name": "real", "calculator": "shared"},
            "energy_settings": {"mode": "single_point"},
            "reference_area_A2": 6.0,
        }
    }
    with pytest.raises(ValueError, match="relaxation-protocol"):
        _reference_calculator_compatibility(raw, references)


def test_real_backend_identity_versions_relaxed_reference_engine(
    monkeypatch,
) -> None:
    from calm.project.application.followups.energy_backends import (
        RealEnergyBackend,
    )

    class _Spec:
        def to_dict(self):
            return {"kind": "test-calculator"}

    class _Uow:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "calm.project.application.followups.calculator_resolution."
        "require_calculator_from_prototype",
        lambda uow, prototype_uid: _Spec(),
    )
    monkeypatch.setattr(
        "calm.project.application.followups.relaxation_backends."
        "_installed_distribution_version",
        lambda name: f"version:{name}",
    )

    identity = RealEnergyBackend().identity(
        targets=[
            {
                "prototype_uid_full": "proto:1",
                "reference_kind": "relaxed_surface_a",
            }
        ],
        uow=_Uow(),
    )
    engine = identity["reference_relaxation_engine"]
    assert engine["algorithm"] == (
        "ase_bfgs_fixed_cell_surface_relaxation_v1"
    )
    assert engine["software_versions"] == {
        "ase": "version:ase",
        "numpy": "version:numpy",
        "scipy": "version:scipy",
    }


def test_deterministic_backend_rejects_relaxed_surface_references() -> None:
    from calm.project.application.followups.energy_backends import (
        DeterministicEnergyBackend,
    )

    with pytest.raises(RuntimeError, match="cannot create scientific"):
        DeterministicEnergyBackend().compute(
            run_uid="run:1",
            prototype_uid="proto:1",
            target_uid="reference:1",
            config={
                "reference_relaxation": {
                    "fmax": 0.05,
                    "steps": 10,
                    "relax_cell": False,
                }
            },
        )


def test_relaxed_surface_certificate_rejects_coercive_values() -> None:
    settings = {"fmax": 0.04, "steps": 12, "relax_cell": False}
    base = {
        "protocol": RELAXED_SURFACE_PROTOCOL,
        "scientific_authority": "calculator_backed",
        "optimizer": "ASE.BFGS",
        "converged": True,
        "relax_cell": False,
        "fmax": 0.04,
        "steps": 12,
        "n_steps": 8,
        "max_force_eV_per_A": 0.03,
        "termination_reason": "converged",
    }
    with pytest.raises(TypeError, match="finite positive real"):
        validate_relaxed_surface_summary(
            {**base, "fmax": "0.04"},
            settings=settings,
        )
    with pytest.raises(TypeError, match="finite nonnegative real"):
        validate_relaxed_surface_summary(
            {**base, "max_force_eV_per_A": "0.03"},
            settings=settings,
        )
    with pytest.raises(ValueError, match="termination reason"):
        validate_relaxed_surface_summary(
            {**base, "termination_reason": 1},
            settings=settings,
        )
