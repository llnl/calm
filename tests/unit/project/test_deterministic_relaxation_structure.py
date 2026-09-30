from __future__ import annotations

import pytest

from calm.project.application.followups.relaxation_backends import (
    DeterministicRelaxationBackend,
)


def test_deterministic_relaxation_returns_unchanged_target_structure() -> None:
    target_atoms = {
        "numbers": [3, 9],
        "positions": [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]],
        "cell": [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
        "pbc": [True, True, True],
    }

    result = DeterministicRelaxationBackend().compute(
        run_uid="run:test",
        prototype_uid="proto:test",
        target_uid="iface:test",
        config={
            "target_atoms": target_atoms,
            "max_steps": 5,
            "convergence": {"force_tol": 0.03},
            "relax_cell": False,
        },
    )

    assert result.relaxed_atoms == target_atoms
    assert result.relaxed_atoms is not target_atoms
    assert result.summary["relaxation_backend"] == "deterministic"


def test_deterministic_relaxation_records_synthetic_nonoptimization() -> None:
    result = DeterministicRelaxationBackend().compute(
        run_uid="run:test",
        prototype_uid="proto:test",
        target_uid="iface:test",
        config={
            "max_steps": 5,
            "convergence": {"force_tol": 0.03},
            "relax_cell": False,
        },
    )

    assert result.n_steps == 0
    assert result.summary["scientific_authority"] == "synthetic_test_only"
    assert result.summary["configuration_changed"] is False
    assert result.max_optimizer_residual == 0.0


def test_deterministic_relaxation_copy_failure_propagates() -> None:
    class BrokenTarget:
        def copy(self):
            raise RuntimeError("target copy failed")

    with pytest.raises(RuntimeError, match="target copy failed"):
        DeterministicRelaxationBackend().compute(
            run_uid="run:test",
            prototype_uid="proto:test",
            target_uid="iface:test",
            config={"target_atoms": BrokenTarget()},
        )
