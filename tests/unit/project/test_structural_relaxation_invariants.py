from __future__ import annotations

import copy
import math
import sys
import types

import numpy as np
import pytest

from calm.project.domain.contracts.relaxation import (
    FIXED_CELL_PROTOCOL,
    INTERFACE_CELL_MASK,
    INTERFACE_CELL_PROTOCOL,
    PERSISTED_CELL_FACTOR_MODE,
    PERSISTED_CELL_FILTER,
    PERSISTED_OPTIMIZER,
    canonical_optimizer_name,
    canonical_relaxation_controls,
    validate_relaxation_result,
    validate_relaxed_structure_transition,
)
from calm.project.application.followups.relaxation import RelaxationOrchestrator
from calm.project.application.followups.relaxation_backends import (
    DeterministicRelaxationBackend,
    RealRelaxationBackend,
    RelaxationComputeResult,
)


def _structure() -> dict[str, object]:
    return {
        "positions": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
        "cell": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 8.0]],
        "numbers": [13, 29],
        "pbc": [True, True, True],
    }


def test_persisted_controls_define_fixed_and_interface_cell_spaces() -> None:
    fixed = canonical_relaxation_controls(
        protocol=FIXED_CELL_PROTOCOL,
        convergence={"force_tol": 0.03},
        max_steps=40,
        relax_cell=False,
    )
    assert fixed.optimizer == PERSISTED_OPTIMIZER
    assert fixed.cell_filter is None
    assert fixed.cell_mask is None

    cell = canonical_relaxation_controls(
        protocol=INTERFACE_CELL_PROTOCOL,
        convergence={"force_tol": 0.02},
        max_steps=50,
        relax_cell=True,
    )
    assert cell.optimizer == PERSISTED_OPTIMIZER
    assert cell.cell_filter == PERSISTED_CELL_FILTER
    assert cell.cell_mask == INTERFACE_CELL_MASK
    assert PERSISTED_CELL_FACTOR_MODE == "n_atoms"


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"protocol": FIXED_CELL_PROTOCOL, "max_steps": 2.0}, TypeError),
        ({"protocol": FIXED_CELL_PROTOCOL, "max_steps": True}, TypeError),
        (
            {
                "protocol": FIXED_CELL_PROTOCOL,
                "convergence": {"force_tol": math.nan},
            },
            ValueError,
        ),
        (
            {
                "protocol": FIXED_CELL_PROTOCOL,
                "convergence": {"stress_tol": 0.1},
            },
            ValueError,
        ),
        ({"protocol": INTERFACE_CELL_PROTOCOL, "relax_cell": False}, ValueError),
        ({"protocol": FIXED_CELL_PROTOCOL, "relax_cell": 1}, TypeError),
    ],
)
def test_persisted_controls_reject_coercive_or_inert_values(
    kwargs: dict[str, object],
    error: type[Exception],
) -> None:
    values = {
        "protocol": FIXED_CELL_PROTOCOL,
        "convergence": {"force_tol": 0.05},
        "max_steps": 10,
        "relax_cell": False,
    }
    values.update(kwargs)
    with pytest.raises(error):
        canonical_relaxation_controls(**values)


def test_optimizer_names_are_exact_and_supported() -> None:
    for name in ("BFGS", "LBFGS", "FIRE"):
        assert canonical_optimizer_name(name) == name

    for retired in ("bfgs", "L-BFGS", "fire", " LBFGS ", "unknown"):
        with pytest.raises(ValueError):
            canonical_optimizer_name(retired)


def test_fixed_cell_transition_preserves_cell_species_and_pbc() -> None:
    initial = _structure()
    final_positions = np.asarray(initial["positions"], dtype=float)
    final_positions[1, 0] += 0.1
    result = validate_relaxed_structure_transition(
        initial_positions=initial["positions"],
        final_positions=final_positions,
        initial_cell=initial["cell"],
        final_cell=initial["cell"],
        initial_numbers=initial["numbers"],
        final_numbers=initial["numbers"],
        initial_pbc=initial["pbc"],
        final_pbc=initial["pbc"],
        cell_mode="fixed",
    )
    assert result["max_cartesian_displacement_A"] == pytest.approx(0.1)
    assert result["cell_change_frobenius_A"] == 0.0

    changed = np.asarray(initial["cell"], dtype=float)
    changed[0, 0] += 0.1
    with pytest.raises(ValueError, match="changed the simulation cell"):
        validate_relaxed_structure_transition(
            initial_positions=initial["positions"],
            final_positions=initial["positions"],
            initial_cell=initial["cell"],
            final_cell=changed,
            initial_numbers=initial["numbers"],
            final_numbers=initial["numbers"],
            initial_pbc=initial["pbc"],
            final_pbc=initial["pbc"],
            cell_mode="fixed",
        )


def test_fixed_cell_transition_allows_nonperiodic_zero_cell() -> None:
    result = validate_relaxed_structure_transition(
        initial_positions=[[0.0, 0.0, 0.0]],
        final_positions=[[0.1, 0.0, 0.0]],
        initial_cell=np.zeros((3, 3)),
        final_cell=np.zeros((3, 3)),
        initial_numbers=[1],
        final_numbers=[1],
        initial_pbc=[False, False, False],
        final_pbc=[False, False, False],
        cell_mode="fixed",
    )

    assert result["initial_volume_A3"] == 0.0
    assert result["final_volume_A3"] == 0.0
    assert result["max_cartesian_displacement_A"] == pytest.approx(0.1)


def test_fixed_cell_transition_rejects_periodic_zero_cell() -> None:
    with pytest.raises(ValueError, match="right-handed and nonsingular"):
        validate_relaxed_structure_transition(
            initial_positions=[[0.0, 0.0, 0.0]],
            final_positions=[[0.0, 0.0, 0.0]],
            initial_cell=np.zeros((3, 3)),
            final_cell=np.zeros((3, 3)),
            initial_numbers=[1],
            final_numbers=[1],
            initial_pbc=[True, True, True],
            final_pbc=[True, True, True],
            cell_mode="fixed",
        )


def test_interface_cell_transition_allows_only_in_plane_cell_change() -> None:
    initial = _structure()
    allowed = np.asarray(initial["cell"], dtype=float)
    allowed[0, 0] *= 1.01
    allowed[1, 1] *= 0.99
    allowed[1, 0] += 0.05
    result = validate_relaxed_structure_transition(
        initial_positions=initial["positions"],
        final_positions=initial["positions"],
        initial_cell=initial["cell"],
        final_cell=allowed,
        initial_numbers=initial["numbers"],
        final_numbers=initial["numbers"],
        initial_pbc=initial["pbc"],
        final_pbc=initial["pbc"],
        cell_mode="interface_in_plane",
    )
    assert result["cell_change_frobenius_A"] > 0.0

    changed_normal = allowed.copy()
    changed_normal[2, 2] += 0.1
    with pytest.raises(ValueError, match="interface-normal cell vector"):
        validate_relaxed_structure_transition(
            initial_positions=initial["positions"],
            final_positions=initial["positions"],
            initial_cell=initial["cell"],
            final_cell=changed_normal,
            initial_numbers=initial["numbers"],
            final_numbers=initial["numbers"],
            initial_pbc=initial["pbc"],
            final_pbc=initial["pbc"],
            cell_mode="interface_in_plane",
        )

    coupled = allowed.copy()
    coupled[0, 2] = 0.2
    with pytest.raises(ValueError, match="out-of-plane coupling"):
        validate_relaxed_structure_transition(
            initial_positions=initial["positions"],
            final_positions=initial["positions"],
            initial_cell=initial["cell"],
            final_cell=coupled,
            initial_numbers=initial["numbers"],
            final_numbers=initial["numbers"],
            initial_pbc=initial["pbc"],
            final_pbc=initial["pbc"],
            cell_mode="interface_in_plane",
        )


def test_transition_rejects_empty_species_reordering_and_pbc_change() -> None:
    initial = _structure()
    with pytest.raises(ValueError, match="at least one atom"):
        validate_relaxed_structure_transition(
            initial_positions=[],
            final_positions=[],
            initial_cell=initial["cell"],
            final_cell=initial["cell"],
            initial_numbers=[],
            final_numbers=[],
            initial_pbc=initial["pbc"],
            final_pbc=initial["pbc"],
            cell_mode="fixed",
        )
    with pytest.raises(ValueError, match="species order"):
        validate_relaxed_structure_transition(
            initial_positions=initial["positions"],
            final_positions=initial["positions"],
            initial_cell=initial["cell"],
            final_cell=initial["cell"],
            initial_numbers=initial["numbers"],
            final_numbers=[29, 13],
            initial_pbc=initial["pbc"],
            final_pbc=initial["pbc"],
            cell_mode="fixed",
        )
    with pytest.raises(ValueError, match="periodic-boundary flags"):
        validate_relaxed_structure_transition(
            initial_positions=initial["positions"],
            final_positions=initial["positions"],
            initial_cell=initial["cell"],
            final_cell=initial["cell"],
            initial_numbers=initial["numbers"],
            final_numbers=initial["numbers"],
            initial_pbc=initial["pbc"],
            final_pbc=[True, True, False],
            cell_mode="fixed",
        )


def test_convergence_is_certified_from_recomputed_optimizer_residual() -> None:
    certificate = validate_relaxation_result(
        final_energy_eV=-3.0,
        n_steps=4,
        max_steps=5,
        converged=False,
        max_atomic_force_eV_per_A=0.02,
        max_optimizer_residual=0.02,
        force_tolerance_eV_per_A=0.03,
    )
    assert certificate["converged"] is True
    assert certificate["optimizer_reported_converged"] is False
    assert certificate["termination_reason"] == (
        "residual_satisfied_after_optimizer_stop"
    )

    nonconverged = validate_relaxation_result(
        final_energy_eV=-3.0,
        n_steps=5,
        max_steps=5,
        converged=False,
        max_atomic_force_eV_per_A=0.04,
        max_optimizer_residual=0.04,
        force_tolerance_eV_per_A=0.03,
    )
    assert nonconverged["converged"] is False
    assert nonconverged["residual_satisfied"] is False

    with pytest.raises(ValueError, match="reported convergence"):
        validate_relaxation_result(
            final_energy_eV=-3.0,
            n_steps=5,
            max_steps=5,
            converged=True,
            max_atomic_force_eV_per_A=0.04,
            max_optimizer_residual=0.04,
            force_tolerance_eV_per_A=0.03,
        )


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("final_energy_eV", math.nan, ValueError),
        ("n_steps", 1.0, TypeError),
        ("n_steps", 6, ValueError),
        ("max_atomic_force_eV_per_A", math.inf, ValueError),
        ("max_optimizer_residual", -1.0, ValueError),
    ],
)
def test_convergence_certificate_rejects_invalid_state(
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    kwargs = {
        "final_energy_eV": -1.0,
        "n_steps": 1,
        "max_steps": 5,
        "converged": True,
        "max_atomic_force_eV_per_A": 0.01,
        "max_optimizer_residual": 0.01,
        "force_tolerance_eV_per_A": 0.03,
    }
    kwargs[field] = value
    with pytest.raises(error):
        validate_relaxation_result(**kwargs)


def test_orchestrator_recomputes_custom_backend_certificate() -> None:
    controls = canonical_relaxation_controls(
        protocol=FIXED_CELL_PROTOCOL,
        convergence={"force_tol": 0.03},
        max_steps=5,
        relax_cell=False,
    )
    result = RelaxationComputeResult(
        final_energy=-2.0,
        n_steps=5,
        relaxed_params={},
        summary={},
        artifact_payloads=[],
        converged=False,
        max_force=0.04,
        max_optimizer_residual=0.04,
        optimizer_reported_converged=False,
    )
    certificate = RelaxationOrchestrator._compute_certificate(result, controls)
    assert certificate["converged"] is False


class _EmptyUnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        del exc_type, exc, tb


def test_real_backend_identity_versions_optimizer_environment() -> None:
    identity = RealRelaxationBackend().identity(
        targets=[],
        uow=_EmptyUnitOfWork(),
    )
    assert identity["scientific_authority"] == "calculator_backed"
    assert identity["optimizer"] == PERSISTED_OPTIMIZER
    assert set(identity["software_versions"]) == {"ase", "numpy", "scipy"}
    assert identity["software_versions"]["numpy"] is not None


def test_real_backend_identity_fails_on_calculator_resolution_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from calm.project.application.followups import calculator_resolution

    def fail_resolution(uow, prototype_uid):
        del uow, prototype_uid
        raise RuntimeError("calculator provenance is incomplete")

    monkeypatch.setattr(
        calculator_resolution,
        "require_calculator_from_prototype",
        fail_resolution,
    )
    with pytest.raises(RuntimeError, match="calculator provenance is incomplete"):
        RealRelaxationBackend().identity(
            targets=[{"prototype_uid_full": "proto:test"}],
            uow=_EmptyUnitOfWork(),
        )


def test_deterministic_backend_is_explicitly_synthetic() -> None:
    backend = DeterministicRelaxationBackend()
    assert backend.requires_target_atoms is False
    assert RealRelaxationBackend.requires_target_atoms is True
    assert backend.identity(targets=[], uow=None) == {
        "name": "deterministic",
        "algorithm": "sha256_unchanged_structure_v2",
        "scientific_authority": "synthetic_test_only",
        "optimizer": None,
    }
    result = backend.compute(
        run_uid="run:test",
        prototype_uid="proto:test",
        target_uid="iface:test",
        config={
            "target_atoms": _structure(),
            "protocol": FIXED_CELL_PROTOCOL,
            "max_steps": 2,
            "convergence": {"force_tol": 0.03},
            "relax_cell": False,
        },
    )
    assert result.summary["scientific_authority"] == "synthetic_test_only"
    assert result.summary["configuration_changed"] is False
    assert result.n_steps == 0


def test_synthetic_backend_does_not_load_missing_target_atoms() -> None:
    orchestrator = object.__new__(RelaxationOrchestrator)
    orchestrator._backend = DeterministicRelaxationBackend()

    def fail_loader(target_uid: str):
        raise AssertionError(f"unexpected atom load for {target_uid}")

    orchestrator._target_atoms_loader = fail_loader
    assert orchestrator._target_atoms_for_backend("iface:test", "interface") is None


def test_synthetic_backend_does_not_create_scientific_relaxed_interface() -> None:
    orchestrator = object.__new__(RelaxationOrchestrator)
    orchestrator._backend_name = "deterministic"
    orchestrator._artifact_store = None
    compute_result = RelaxationComputeResult(
        final_energy=1.0,
        n_steps=0,
        relaxed_params={"scientific_authority": "synthetic_test_only"},
        summary={},
        artifact_payloads=[],
        converged=True,
        max_force=0.0,
        max_optimizer_residual=0.0,
        optimizer_reported_converged=True,
    )

    interface_uid, artifact_refs = orchestrator._derive_relaxed_interface(
        uow=None,
        run=type("Run", (), {"uid_full": "run:test"})(),
        followup_uid="followup:test",
        prototype_uid_full="proto:test",
        target_uid_full="iface:test",
        target_kind="interface",
        compute_result=compute_result,
        user_payload={},
    )

    assert interface_uid is None
    assert artifact_refs == []

def test_real_backend_rejects_implicit_prototype_reconstruction() -> None:
    from calm.project.application.followups.relaxation_backends import (
        RealRelaxationBackend,
    )

    with pytest.raises(RuntimeError, match="persisted atomistic interface"):
        RealRelaxationBackend().compute(
            run_uid="run:test",
            prototype_uid="proto:test",
            target_uid="proto:test",
            config={
                "target_kind": "prototype",
                "protocol": FIXED_CELL_PROTOCOL,
                "convergence": {"force_tol": 0.03},
                "max_steps": 2,
                "relax_cell": False,
            },
            uow=None,
        )


def test_persisted_relaxation_protocol_rejects_legacy_or_normalized_tokens() -> None:
    common = {
        "convergence": {"force_tol": 0.05},
        "max_steps": 10,
        "relax_cell": False,
    }
    with pytest.raises(ValueError, match="expected 'ionic_positions_v1'"):
        canonical_relaxation_controls(protocol="dft_ionic_v1", **common)
    with pytest.raises(ValueError, match="surrounding whitespace"):
        canonical_relaxation_controls(protocol=" ionic_positions_v1", **common)


class _RelaxationAtoms:
    def __init__(self, *, cell: np.ndarray, info: dict[str, object]):
        self.positions = np.array([[0.0, 0.0, 0.0]], dtype=float)
        self.cell = np.asarray(cell, dtype=float).copy()
        self.numbers = np.array([1], dtype=int)
        self.pbc = np.array([True, True, True], dtype=bool)
        self.info = copy.deepcopy(info)
        self.calc = None

    def copy(self):
        copied = _RelaxationAtoms(cell=self.cell, info=self.info)
        copied.positions = self.positions.copy()
        return copied

    def __len__(self):
        return len(self.numbers)

    def get_positions(self):
        return self.positions.copy()

    def get_cell(self):
        return self.cell.copy()

    def get_atomic_numbers(self):
        return self.numbers.copy()

    def get_pbc(self):
        return self.pbc.copy()

    def get_potential_energy(self):
        return -1.25

    def get_forces(self):
        return np.zeros((len(self), 3), dtype=float)


def _source_deformation_accounting() -> dict[str, object]:
    identity = np.eye(3).tolist()
    return {
        "policy": "composed_slab_deformation",
        "version": 1,
        "lower": {
            "F_construction_slab": identity,
            "F_interface_slab": identity,
            "F_total_slab": identity,
        },
        "upper": {
            "F_construction_slab": identity,
            "F_interface_slab": identity,
            "F_total_slab": identity,
        },
    }


def test_real_fixed_cell_backend_preserves_and_persists_deformation_accounting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from calm.calculators import runtime as calculator_runtime
    from calm.project.application.followups import calculator_resolution
    from calm.slab.oriented.cell_contract import (
        INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
        INTERFACE_RELAXATION_DEFORMATION_INFO_KEY,
    )

    ase_module = types.ModuleType("ase")
    optimize_module = types.ModuleType("ase.optimize")

    class BFGS:
        def __init__(self, target, logfile=None):
            del logfile
            self.target = target
            self.nsteps = 1

        def run(self, *, fmax, steps):
            del fmax, steps
            return True

    optimize_module.BFGS = BFGS
    ase_module.optimize = optimize_module
    monkeypatch.setitem(sys.modules, "ase", ase_module)
    monkeypatch.setitem(sys.modules, "ase.optimize", optimize_module)
    monkeypatch.setattr(
        calculator_runtime,
        "construct_calculator",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(
        calculator_resolution,
        "require_calculator_from_prototype",
        lambda *a, **k: object(),
    )

    source = _source_deformation_accounting()
    atoms = _RelaxationAtoms(
        cell=np.diag([2.0, 2.0, 8.0]),
        info={INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY: source},
    )
    result = RealRelaxationBackend().compute(
        run_uid="run:test",
        prototype_uid="proto:test",
        target_uid="iface:test",
        config={
            "target_kind": "interface",
            "target_atoms": atoms,
            "protocol": FIXED_CELL_PROTOCOL,
            "convergence": {"force_tol": 0.03},
            "max_steps": 2,
            "relax_cell": False,
        },
        uow=_EmptyUnitOfWork(),
    )

    relaxed = result.relaxed_atoms
    assert relaxed is not None
    assert relaxed.info[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] == source
    relaxation = relaxed.info[INTERFACE_RELAXATION_DEFORMATION_INFO_KEY]
    assert relaxation["cell_mode"] == "fixed"
    assert np.allclose(relaxation["F_relaxation_interface"], np.eye(3))
    assert result.relaxed_params["deformation_accounting"] == relaxation
