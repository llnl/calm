from __future__ import annotations

import pytest

pytest.importorskip("ase")
from ase import Atoms

from test_helpers import make_test_interface_prototype
from calm.project.application.followups.energy_backends import EnergyComputeResult
from calm.public.project import open_project
from calm.public.inputs.settings import (
    EnergyConvention,
    EnergySettings,
    ReferenceEnergySettings,
)


class _IdentityEnergyBackend:
    name = "identity-test"

    def __init__(self, version: str) -> None:
        self.version = version

    def identity(self, *, targets, uow):
        del targets, uow
        return {"name": self.name, "version": self.version}

    def compute(self, *, run_uid, prototype_uid, target_uid, config, uow=None):
        del run_uid, prototype_uid, target_uid, config, uow
        return EnergyComputeResult(
            energy=-3.0,
            n_steps=1,
            summary={"energy": -3.0},
            artifact_payloads=[],
        )


def test_typed_energy_and_thermodynamic_roundtrip(tmp_path) -> None:
    project = open_project(tmp_path)
    mapping = project._workspace.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="energy_roundtrip", miller_a=(1, 0, 0), miller_b=(1, 0, 0), n_atoms_interface=2, interface_area_A2=10.0)
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]
    atoms = Atoms(
        "H2",
        positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        cell=[[2.0, 0.0, 0.0], [0.0, 5.0, 0.0], [0.0, 0.0, 8.0]],
        pbc=True,
    )
    relaxed = project._workspace.create_derived_interface(
        prototype_uid,
        label="energy_relaxed",
        stage="relaxed",
        params={"search_name": "energy_search"},
        atoms=atoms,
    )

    convention = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=2,
    )
    references = ReferenceEnergySettings(
        bulk_a_eV_per_formula_unit=-1.0,
        bulk_b_eV_per_formula_unit=-2.0,
        n_formula_units_a=2,
        n_formula_units_b=1,
    )
    first = project.evaluate_energies(
        [relaxed.uid_full],
        settings=EnergySettings(),
        backend="deterministic",
        convention=convention,
        references=references,
    )

    assert first.ok
    assert first.energy_run.run_type == "energy_stage"
    assert first.thermodynamic_run.run_type == "thermodynamic_derivation"
    assert len(first.energy_results) == 1
    assert len(first.thermodynamic_results) == 1
    raw = first.energy_results.records()[0]
    derived = first.thermodynamic_results.records()[0]
    expected = (raw.energy_eV - (-4.0)) / 20.0
    assert raw.payload["interface_area_A2"] == pytest.approx(10.0)
    assert raw.payload["area_source"] == "authoritative_interface_cell"
    assert derived.value_eV_per_A2 == pytest.approx(expected)
    assert (
        derived.normalization_area_source_status
        == "authoritative_interface_cell"
    )
    assert derived.raw_energy_followup_uid == raw.uid_full
    assert derived.target_uid_full == relaxed.uid_full

    reopened = open_project(tmp_path)
    resumed = reopened.evaluate_energies(
        [relaxed.uid_full],
        settings=EnergySettings(),
        backend="deterministic",
        convention=convention,
        references=references,
    )
    assert resumed.energy_run.uid_full == first.energy_run.uid_full
    assert resumed.thermodynamic_run.uid_full == first.thermodynamic_run.uid_full
    assert resumed.energy_results.records()[0].uid_full == raw.uid_full
    assert resumed.thermodynamic_results.records()[0].uid_full == derived.uid_full

    relabeled = reopened.evaluate_energies(
        [relaxed.uid_full],
        settings=EnergySettings(),
        backend="deterministic",
        convention=convention,
        references=references,
        search_name="reporting-label-only",
    )
    assert relabeled.energy_run.uid_full == first.energy_run.uid_full
    assert relabeled.thermodynamic_run.uid_full == first.thermodynamic_run.uid_full

    changed_references = ReferenceEnergySettings(
        bulk_a_eV_per_formula_unit=-1.5,
        bulk_b_eV_per_formula_unit=-2.0,
        n_formula_units_a=2,
        n_formula_units_b=1,
    )
    changed = reopened.evaluate_energies(
        [relaxed.uid_full],
        settings=EnergySettings(),
        backend="deterministic",
        convention=convention,
        references=changed_references,
    )
    assert changed.energy_run.uid_full == first.energy_run.uid_full
    assert changed.thermodynamic_run.uid_full != first.thermodynamic_run.uid_full
    assert len(reopened.energy_runs()) == 1
    assert len(reopened.thermodynamic_runs()) == 2


def test_custom_backend_identity_changes_raw_run_identity(tmp_path) -> None:
    project = open_project(tmp_path)
    mapping = project._workspace.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="energy_backend_identity", miller_a=(1, 0, 0), miller_b=(1, 0, 0), n_atoms_interface=2, interface_area_A2=8.0)
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]
    atoms = Atoms(
        "H2",
        positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        cell=[[2.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 8.0]],
        pbc=True,
    )
    relaxed = project._workspace.create_derived_interface(
        prototype_uid,
        label="energy_backend_relaxed",
        stage="relaxed",
        atoms=atoms,
    )

    first = project.evaluate_energies(
        [relaxed.uid_full],
        backend=_IdentityEnergyBackend("v1"),
    )
    repeated = project.evaluate_energies(
        [relaxed.uid_full],
        backend=_IdentityEnergyBackend("v1"),
    )
    changed = project.evaluate_energies(
        [relaxed.uid_full],
        backend=_IdentityEnergyBackend("v2"),
    )

    assert repeated.energy_run.uid_full == first.energy_run.uid_full
    assert changed.energy_run.uid_full != first.energy_run.uid_full
    assert first.energy_results.records()[0].backend_identity["version"] == "v1"
    assert changed.energy_results.records()[0].backend_identity["version"] == "v2"
